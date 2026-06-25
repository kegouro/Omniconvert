"""Tests de los conversores implementados en el Milestone 3 (SQLite, HDF5, DOCX, AVIF)."""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from omni_convert.core.converter import ConversionError, MissingDependencyError


class TestSqliteToCsv:
    def test_sqlite_to_csv_basico(self, tmp_path):
        db_path = tmp_path / "test.db"
        output_dir = tmp_path / "csv_out"

        # Crear base de datos temporal
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
        cursor.execute("INSERT INTO users (name) VALUES ('Alice'), ('Bob');")
        # Tabla del sistema
        cursor.execute("CREATE TABLE sqlite_sequence (name, seq);")
        conn.commit()
        conn.close()

        from omni_convert.converters.data.sqlite_to_csv import SqliteToCsv

        progress_values = []
        SqliteToCsv().convert(db_path, output_dir, progress_values.append)

        assert (output_dir / "users.csv").exists()
        assert not (output_dir / "sqlite_sequence.csv").exists()
        assert (output_dir / "schema.sql").exists()

        # Verificar contenido CSV
        with open(output_dir / "users.csv", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows == [["id", "name"], ["1", "Alice"], ["2", "Bob"]]

        # Verificar schema.sql
        schema_content = (output_dir / "schema.sql").read_text(encoding="utf-8")
        assert "CREATE TABLE users" in schema_content
        assert "CREATE TABLE sqlite_sequence" not in schema_content
        assert progress_values[-1] == 1.0

    def test_sqlite_to_csv_sin_tablas(self, tmp_path):
        db_path = tmp_path / "empty.db"
        output_dir = tmp_path / "empty_csv_out"

        conn = sqlite3.connect(db_path)
        conn.close()

        from omni_convert.converters.data.sqlite_to_csv import SqliteToCsv

        SqliteToCsv().convert(db_path, output_dir, lambda p: None)

        assert (output_dir / "schema.sql").exists()
        assert (output_dir / "schema.sql").read_text(encoding="utf-8") == ""

    def test_sqlite_to_csv_error_archivo_inexistente(self, tmp_path):
        from omni_convert.converters.data.sqlite_to_csv import SqliteToCsv

        with pytest.raises(ConversionError):
            SqliteToCsv().convert(tmp_path / "nonexistent.db", tmp_path / "out", lambda p: None)


class TestHdf5ToParquet:
    def test_hdf5_to_parquet_dimensions(self, tmp_path, monkeypatch):
        # Mock de h5py
        mock_h5py = ModuleType("h5py")

        class MockDataset:
            def __init__(self, name, data):
                self.name = name
                self.data = np.asarray(data)
                self.ndim = self.data.ndim
                self.shape = self.data.shape

            def __getitem__(self, item):
                return self.data

            def item(self):
                return self.data.item()

        mock_h5py.Dataset = MockDataset

        class MockFile:
            def __init__(self, path, mode):
                self.path = path
                self.mode = mode
                self.datasets = {
                    "ds_0d": MockDataset("ds_0d", 42),
                    "ds_1d": MockDataset("ds_1d", [10, 20, 30]),
                    "group/ds_2d": MockDataset("group/ds_2d", [[1, 2], [3, 4]]),
                    "group/sub/ds_3d": MockDataset("group/sub/ds_3d", np.arange(24).reshape(2, 3, 4)),
                }

            def visititems(self, callback):
                for name, dataset in self.datasets.items():
                    callback(name, dataset)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_h5py.File = MockFile
        monkeypatch.setitem(sys.modules, "h5py", mock_h5py)

        # Crear archivo vacío para evitar error de archivo inexistente
        input_h5 = tmp_path / "test.h5"
        input_h5.write_text("dummy", encoding="utf-8")
        output_dir = tmp_path / "parquet_out"

        from omni_convert.converters.data.hdf5_to_parquet import Hdf5ToParquet

        Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)

        import pandas as pd

        # 0D
        df_0d = pd.read_parquet(output_dir / "ds_0d.parquet")
        assert list(df_0d.columns) == ["value"]
        assert df_0d.shape == (1, 1)
        assert df_0d.loc[0, "value"] == 42

        # 1D
        df_1d = pd.read_parquet(output_dir / "ds_1d.parquet")
        assert list(df_1d.columns) == ["value"]
        assert df_1d.shape == (3, 1)
        assert list(df_1d["value"]) == [10, 20, 30]

        # 2D
        df_2d = pd.read_parquet(output_dir / "group_ds_2d.parquet")
        assert list(df_2d.columns) == ["col_0", "col_1"]
        assert df_2d.shape == (2, 2)
        assert list(df_2d["col_0"]) == [1, 3]

        # 3D
        df_3d = pd.read_parquet(output_dir / "group_sub_ds_3d.parquet")
        assert df_3d.shape == (2, 12)
        assert list(df_3d.columns) == [f"col_{i}" for i in range(12)]

    def test_hdf5_to_parquet_missing_dependency(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "h5py", None)
        input_h5 = tmp_path / "test.h5"
        input_h5.write_text("dummy", encoding="utf-8")
        output_dir = tmp_path / "parquet_out"

        from omni_convert.converters.data.hdf5_to_parquet import Hdf5ToParquet

        with pytest.raises(MissingDependencyError) as exc_info:
            Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)
        assert "h5py" in str(exc_info.value)


class TestDocxToMd:
    def test_docx_to_md_conversion(self, tmp_path, monkeypatch):
        m_docx = ModuleType("docx")
        m_doc_doc = ModuleType("docx.document")
        m_oxml_tbl = ModuleType("docx.oxml.table")
        m_oxml_p = ModuleType("docx.oxml.text.paragraph")
        m_tbl = ModuleType("docx.table")
        m_p = ModuleType("docx.text.paragraph")

        class MockCT_P:
            pass

        class MockCT_Tbl:
            pass

        m_oxml_p.CT_P = MockCT_P
        m_oxml_tbl.CT_Tbl = MockCT_Tbl

        class MockStyle:
            def __init__(self, name):
                self.name = name

        class MockBlip:
            def __init__(self, embed_id):
                self.embed_id = embed_id

            def get(self, name):
                return self.embed_id

        class MockR:
            def __init__(self, blips):
                self.blips = blips

            def xpath(self, path):
                return self.blips

        class MockRun:
            def __init__(self, text, bold=False, italic=False, blips=None):
                self.text = text
                self.bold = bold
                self.italic = italic
                self._r = MockR(blips or [])

        class MockParagraph:
            def __init__(self, element, doc):
                self.runs = element.runs
                self.style = element.style

        class MockCell:
            def __init__(self, text):
                self.text = text

        class MockRow:
            def __init__(self, cells):
                self.cells = [MockCell(c) for c in cells]

        class MockTable:
            def __init__(self, element, doc):
                self.rows = [MockRow(r) for r in element.rows_data]

        m_p.Paragraph = MockParagraph
        m_tbl.Table = MockTable

        class MockPart:
            def __init__(self, blob, content_type):
                self.blob = blob
                self.content_type = content_type

        class MockDocument:
            def __init__(self, input_path):
                # Crear algunos elementos
                p1 = MockCT_P()
                p1.runs = [MockRun("Hello ", bold=True), MockRun("world!", italic=True)]
                p1.style = MockStyle("Normal")

                p2 = MockCT_P()
                p2.runs = [MockRun("Section title")]
                p2.style = MockStyle("Heading 1")

                p3 = MockCT_P()
                p3.runs = [MockRun("Bullet item")]
                p3.style = MockStyle("List Bullet")

                p4 = MockCT_P()
                p4.runs = [MockRun("Number item")]
                p4.style = MockStyle("List Number")

                tbl = MockCT_Tbl()
                tbl.rows_data = [
                    ["Header 1", "Header 2"],
                    ["Value 1 | with pipe", "Value 2\nwith newline"],
                ]

                p_img = MockCT_P()
                p_img.runs = [MockRun("", blips=[MockBlip("rIdImg1")])]
                p_img.style = MockStyle("Normal")

                class Element:
                    def __init__(self, body):
                        self.body = body

                self.element = Element([p1, p2, p3, p4, tbl, p_img])

                class Part:
                    def __init__(self):
                        self.related_parts = {"rIdImg1": MockPart(b"fake_image_bytes", "image/png")}

                self.part = Part()

        m_docx.Document = MockDocument

        monkeypatch.setitem(sys.modules, "docx", m_docx)
        monkeypatch.setitem(sys.modules, "docx.document", m_doc_doc)
        monkeypatch.setitem(sys.modules, "docx.oxml.table", m_oxml_tbl)
        monkeypatch.setitem(sys.modules, "docx.oxml.text.paragraph", m_oxml_p)
        monkeypatch.setitem(sys.modules, "docx.table", m_tbl)
        monkeypatch.setitem(sys.modules, "docx.text.paragraph", m_p)

        input_docx = tmp_path / "test.docx"
        input_docx.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "test.md"

        from omni_convert.converters.document.docx_to_md import DocxToMd

        DocxToMd().convert(input_docx, output_md, lambda p: None)

        markdown_content = output_md.read_text(encoding="utf-8")

        # Verificar formato de texto
        assert "**Hello** *world!*" in markdown_content
        # Verificar Heading
        assert "# Section title" in markdown_content
        # Verificar Listas
        assert "* Bullet item" in markdown_content
        assert "1. Number item" in markdown_content
        # Verificar Tablas
        assert "| Header 1 | Header 2 |" in markdown_content
        assert "| --- | --- |" in markdown_content
        assert "| Value 1 \\| with pipe | Value 2<br>with newline |" in markdown_content
        # Verificar Imagen
        assert "![image](media/image_1.png)" in markdown_content
        assert (tmp_path / "media" / "image_1.png").read_bytes() == b"fake_image_bytes"

    def test_docx_to_md_missing_dependency(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "docx", None)
        input_docx = tmp_path / "test.docx"
        input_docx.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "test.md"

        from omni_convert.converters.document.docx_to_md import DocxToMd

        with pytest.raises(MissingDependencyError) as exc_info:
            DocxToMd().convert(input_docx, output_md, lambda p: None)
        assert "python-docx" in str(exc_info.value)


class TestAvifToPng:
    def test_avif_to_png_conversion(self, tmp_path, monkeypatch):
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")
        m_pillow_avif = ModuleType("pillow_avif")

        class MockImage:
            def __init__(self, path):
                self.path = path

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

            def save(self, output_path, format=None):
                Path(output_path).write_bytes(b"mock_png_data")

        m_pil_image.Image = MockImage
        m_pil_image.open = MockImage
        m_pil.Image = m_pil_image

        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)
        monkeypatch.setitem(sys.modules, "pillow_avif", m_pillow_avif)

        input_avif = tmp_path / "test.avif"
        input_avif.write_text("dummy", encoding="utf-8")
        output_png = tmp_path / "test.png"

        from omni_convert.converters.image.avif_to_png import AvifToPng

        progress_values = []
        AvifToPng().convert(input_avif, output_png, progress_values.append)

        assert output_png.exists()
        assert output_png.read_bytes() == b"mock_png_data"
        assert 1.0 in progress_values

    def test_png_to_avif_stub(self, tmp_path):
        from omni_convert.converters.image.avif_to_png import PngToAvif

        with pytest.raises(NotImplementedError):
            PngToAvif().convert(tmp_path / "in.png", tmp_path / "out.avif", lambda p: None)

    def test_avif_to_png_missing_dependency_pillow(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "PIL", None)
        input_avif = tmp_path / "test.avif"
        input_avif.write_text("dummy", encoding="utf-8")
        output_png = tmp_path / "test.png"

        from omni_convert.converters.image.avif_to_png import AvifToPng

        with pytest.raises(MissingDependencyError) as exc_info:
            AvifToPng().convert(input_avif, output_png, lambda p: None)
        assert "pillow" in str(exc_info.value)

    def test_avif_to_png_missing_dependency_plugin(self, tmp_path, monkeypatch):
        # Dejar PIL como módulo pero hacer que pillow_avif lance ImportError
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")
        m_pil.Image = m_pil_image
        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)

        monkeypatch.setitem(sys.modules, "pillow_avif", None)
        input_avif = tmp_path / "test.avif"
        input_avif.write_text("dummy", encoding="utf-8")
        output_png = tmp_path / "test.png"

        from omni_convert.converters.image.avif_to_png import AvifToPng

        with pytest.raises(MissingDependencyError) as exc_info:
            AvifToPng().convert(input_avif, output_png, lambda p: None)
        assert "pillow-avif-plugin" in str(exc_info.value)
