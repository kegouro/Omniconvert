"""Adversarial tests for OmniConvert format converters and CLI batch engine."""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path
from types import ModuleType
import numpy as np
import pytest

from omni_convert.core.converter import ConversionError, MissingDependencyError
from omni_convert.converters.data.sqlite_to_csv import SqliteToCsv
from omni_convert.converters.data.hdf5_to_parquet import Hdf5ToParquet
from omni_convert.converters.document.docx_to_md import DocxToMd
from omni_convert.converters.image.avif_to_png import AvifToPng
from omni_convert.converters.image.image_to_latex import PngToTex
from omni_convert.converters.document.pdf_to_md import PdfToMd
from typer.testing import CliRunner
from omni_convert.cli import app


@pytest.fixture(autouse=True)
def reset_module_caches():
    """Resetea el cache de los modelos OCR antes/después de cada test."""
    import omni_convert.converters.document.pdf_to_md as pdf_mod
    import omni_convert.converters.image.image_to_latex as img_mod

    pdf_mod._OCR_MODEL = None
    img_mod._LATEX_MODEL = None
    yield
    pdf_mod._OCR_MODEL = None
    img_mod._LATEX_MODEL = None


class TestSqliteToCsvAdversarial:
    def test_sqlite_to_csv_table_name_with_quotes(self, tmp_path):
        """Test how SqliteToCsv handles table names containing double quotes."""
        db_path = tmp_path / "quotes.db"
        output_dir = tmp_path / "csv_out"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Create a table name with double quotes
        cursor.execute('CREATE TABLE "bad""table" (id INTEGER PRIMARY KEY, name TEXT);')
        cursor.execute('INSERT INTO "bad""table" (name) VALUES (\'Alice\');')
        conn.commit()
        conn.close()

        # The converter executes SELECT * FROM "bad"table", which causes a sqlite3.OperationalError.
        # It must be caught and raised as a ConversionError.
        with pytest.raises(ConversionError) as exc_info:
            SqliteToCsv().convert(db_path, output_dir, lambda p: None)
        
        assert "Error al exportar la tabla" in str(exc_info.value)

    def test_sqlite_to_csv_locked_database(self, tmp_path, monkeypatch):
        """Test database connection or operational failure during fetch."""
        db_path = tmp_path / "locked.db"
        output_dir = tmp_path / "csv_out"

        # Create normal database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
        cursor.execute("INSERT INTO users (name) VALUES ('Alice');")
        conn.commit()
        conn.close()

        orig_connect = sqlite3.connect
        close_called = False

        class MockCursor:
            def execute(self, query):
                if "sqlite_master" in query:
                    # Allow schema inspection query to succeed
                    pass
                else:
                    raise sqlite3.OperationalError("database is locked")
            
            def fetchall(self):
                return [("users", "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")]

            @property
            def description(self):
                return [("id", None, None, None, None, None, None), ("name", None, None, None, None, None, None)]

        class MockConnection:
            def cursor(self):
                return MockCursor()
            def close(self):
                nonlocal close_called
                close_called = True

        def mock_connect(database, *args, **kwargs):
            if Path(database) == db_path:
                return MockConnection()
            return orig_connect(database, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", mock_connect)

        with pytest.raises(ConversionError) as exc_info:
            SqliteToCsv().convert(db_path, output_dir, lambda p: None)

        assert "database is locked" in str(exc_info.value)
        assert close_called, "Connection was not closed during failure"


class TestHdf5ToParquetAdversarial:
    def test_hdf5_to_parquet_complex_unsupported_type(self, tmp_path, monkeypatch):
        """Test Hdf5ToParquet with zero-dimensional dataset containing unsupported/complex objects."""
        mock_h5py = ModuleType("h5py")

        class MockDataset:
            def __init__(self, name, data):
                self.name = name
                self.data = data
                self.ndim = 0
                self.shape = ()

            def __getitem__(self, item):
                return self.data

            def item(self):
                raise TypeError("Cannot convert complex object to primitive")

        mock_h5py.Dataset = MockDataset

        class MockFile:
            def __init__(self, path, mode):
                self.datasets = {
                    "ds_complex": MockDataset("ds_complex", object())
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

        input_h5 = tmp_path / "complex.h5"
        input_h5.write_text("dummy", encoding="utf-8")
        output_dir = tmp_path / "parquet_out"

        with pytest.raises(ConversionError) as exc_info:
            Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)

        assert "Error al convertir HDF5" in str(exc_info.value)

    def test_hdf5_to_parquet_high_dimensions(self, tmp_path, monkeypatch):
        """Test Hdf5ToParquet with high dimensional datasets (5D) to check reshaping."""
        mock_h5py = ModuleType("h5py")

        class MockDataset:
            def __init__(self, name, shape):
                self.name = name
                self.shape = shape
                self.ndim = len(shape)
                self.data = np.arange(np.prod(shape)).reshape(shape)

            def __getitem__(self, item):
                return self.data

        mock_h5py.Dataset = MockDataset

        class MockFile:
            def __init__(self, path, mode):
                # 5D dataset with shape (2, 3, 2, 2, 2)
                self.datasets = {
                    "ds_5d": MockDataset("ds_5d", (2, 3, 2, 2, 2))
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

        input_h5 = tmp_path / "high_dim.h5"
        input_h5.write_text("dummy", encoding="utf-8")
        output_dir = tmp_path / "parquet_out"

        Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)

        import pandas as pd
        # Reshaped to (2, 3*2*2*2) = (2, 24)
        df = pd.read_parquet(output_dir / "ds_5d.parquet")
        assert df.shape == (2, 24)
        assert list(df.columns) == [f"col_{i}" for i in range(24)]

    def test_hdf5_to_parquet_missing_pandas(self, tmp_path, monkeypatch):
        """Test Hdf5ToParquet raises MissingDependencyError when pandas fails to import."""
        monkeypatch.setitem(sys.modules, "h5py", ModuleType("h5py"))
        monkeypatch.setitem(sys.modules, "pandas", None)

        input_h5 = tmp_path / "test.h5"
        input_h5.write_text("dummy", encoding="utf-8")
        output_dir = tmp_path / "parquet_out"

        with pytest.raises(MissingDependencyError) as exc_info:
            Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)
        assert "pandas" in str(exc_info.value)


class TestDocxToMdAdversarial:
    def test_docx_to_md_corrupted_image_blob(self, tmp_path, monkeypatch):
        """Test DOCX conversion where image part blob raises an exception."""
        m_docx = ModuleType("docx")
        m_doc_doc = ModuleType("docx.document")
        m_oxml_tbl = ModuleType("docx.oxml.table")
        m_oxml_p = ModuleType("docx.oxml.text.paragraph")
        m_tbl = ModuleType("docx.table")
        m_p = ModuleType("docx.text.paragraph")

        class MockCT_P: pass
        class MockCT_Tbl: pass

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
            def __init__(self, text, blips=None):
                self.text = text
                self.bold = False
                self.italic = False
                self._r = MockR(blips or [])

        class MockParagraph:
            def __init__(self, element, doc):
                self.runs = element.runs
                self.style = element.style

        m_p.Paragraph = MockParagraph

        class MockPart:
            @property
            def blob(self):
                raise OSError("Zipfile CRC error - corrupted blob")
            @property
            def content_type(self):
                return "image/png"

        class MockDocument:
            def __init__(self, input_path):
                p = MockCT_P()
                p.runs = [MockRun("", blips=[MockBlip("rId1")])]
                p.style = MockStyle("Normal")

                class Element:
                    def __init__(self, body):
                        self.body = body
                self.element = Element([p])

                class Part:
                    def __init__(self):
                        self.related_parts = {"rId1": MockPart()}
                self.part = Part()

        m_docx.Document = MockDocument

        monkeypatch.setitem(sys.modules, "docx", m_docx)
        monkeypatch.setitem(sys.modules, "docx.document", m_doc_doc)
        monkeypatch.setitem(sys.modules, "docx.oxml.table", m_oxml_tbl)
        monkeypatch.setitem(sys.modules, "docx.oxml.text.paragraph", m_oxml_p)
        monkeypatch.setitem(sys.modules, "docx.table", m_tbl)
        monkeypatch.setitem(sys.modules, "docx.text.paragraph", m_p)

        input_docx = tmp_path / "corrupt_img.docx"
        input_docx.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "output.md"

        with pytest.raises(ConversionError) as exc_info:
            DocxToMd().convert(input_docx, output_md, lambda p: None)

        assert "Error al convertir DOCX a Markdown" in str(exc_info.value)

    def test_docx_to_md_none_style_name(self, tmp_path, monkeypatch):
        """Test DOCX conversion when paragraph style name is None."""
        m_docx = ModuleType("docx")
        m_doc_doc = ModuleType("docx.document")
        m_oxml_tbl = ModuleType("docx.oxml.table")
        m_oxml_p = ModuleType("docx.oxml.text.paragraph")
        m_tbl = ModuleType("docx.table")
        m_p = ModuleType("docx.text.paragraph")

        class MockCT_P: pass
        class MockCT_Tbl: pass

        m_oxml_p.CT_P = MockCT_P
        m_oxml_tbl.CT_Tbl = MockCT_Tbl

        class MockStyle:
            def __init__(self):
                self.name = None

        class MockRun:
            def __init__(self, text):
                self.text = text
                self.bold = False
                self.italic = False
                class MockR:
                    def xpath(self, path): return []
                self._r = MockR()

        class MockParagraph:
            def __init__(self, element, doc):
                self.runs = element.runs
                self.style = element.style

        m_p.Paragraph = MockParagraph

        class MockDocument:
            def __init__(self, input_path):
                p = MockCT_P()
                p.runs = [MockRun("Paragraph with None style name")]
                p.style = MockStyle()

                class Element:
                    def __init__(self, body):
                        self.body = body
                self.element = Element([p])
                class Part:
                    def __init__(self):
                        self.related_parts = {}
                self.part = Part()

        m_docx.Document = MockDocument

        monkeypatch.setitem(sys.modules, "docx", m_docx)
        monkeypatch.setitem(sys.modules, "docx.document", m_doc_doc)
        monkeypatch.setitem(sys.modules, "docx.oxml.table", m_oxml_tbl)
        monkeypatch.setitem(sys.modules, "docx.oxml.text.paragraph", m_oxml_p)
        monkeypatch.setitem(sys.modules, "docx.table", m_tbl)
        monkeypatch.setitem(sys.modules, "docx.text.paragraph", m_p)

        input_docx = tmp_path / "none_style.docx"
        input_docx.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "output.md"

        DocxToMd().convert(input_docx, output_md, lambda p: None)
        assert output_md.exists()
        assert "Paragraph with None style name" in output_md.read_text(encoding="utf-8")


class TestAvifToPngAdversarial:
    def test_avif_to_png_pil_save_failure(self, tmp_path, monkeypatch):
        """Test AVIF conversion when image save raises an OSError."""
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")

        class MockImage:
            def __init__(self, path):
                self.path = path
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            def save(self, output_path, format=None):
                raise OSError("Disk full or permission denied")

        m_pil_image.Image = MockImage
        m_pil_image.open = MockImage
        m_pil.Image = m_pil_image

        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)
        monkeypatch.setitem(sys.modules, "pillow_avif", ModuleType("pillow_avif"))

        input_avif = tmp_path / "test.avif"
        input_avif.write_text("dummy", encoding="utf-8")
        output_png = tmp_path / "test.png"

        with pytest.raises(ConversionError) as exc_info:
            AvifToPng().convert(input_avif, output_png, lambda p: None)

        assert "Error al decodificar AVIF a PNG" in str(exc_info.value)


class TestImageToLatexAdversarial:
    def test_image_to_latex_model_init_exception_escapes(self, tmp_path, monkeypatch):
        """Verify the exception boundary gap where model initialization exceptions escape convert()."""
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")
        class MockImage:
            def __init__(self, path): pass
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb): pass
        m_pil_image.open = MockImage
        m_pil.Image = m_pil_image
        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)

        m_pix2tex = ModuleType("pix2tex")
        m_pix2tex_cli = ModuleType("pix2tex.cli")

        def mock_latex_ocr_init(*args, **kwargs):
            raise RuntimeError("CUDA Out of Memory during LatexOCR model loading")

        m_pix2tex_cli.LatexOCR = mock_latex_ocr_init
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_png = tmp_path / "formula.png"
        input_png.write_text("dummy", encoding="utf-8")
        output_tex = tmp_path / "formula.tex"

        # Since model initialization is outside the try block in image_to_latex.py,
        # a RuntimeError escapes instead of being caught and wrapped in ConversionError.
        with pytest.raises(RuntimeError) as exc_info:
            PngToTex().convert(input_png, output_tex, lambda p: None)

        assert "CUDA Out of Memory" in str(exc_info.value)


class TestPdfToMdAdversarial:
    def test_pdf_to_md_inverted_bounding_box(self, tmp_path, monkeypatch):
        """Test PDF hybrid mode conversion with inverted/negative bounding box coordinates."""
        m_pdfplumber = ModuleType("pdfplumber")

        class MockCroppedPage:
            def to_image(self, resolution=150):
                raise ValueError("Cannot render page with negative/invalid dimensions")

        class MockPage:
            def __init__(self):
                self.height = 800
                self.width = 600
            def extract_text(self):
                return "Hybrid text line"
            def extract_words(self):
                return [
                    {"text": "Hybrid", "x0": 10, "x1": 50, "top": 10, "bottom": 20},
                    {"text": "text", "x0": 60, "x1": 90, "top": 10, "bottom": 20},
                ]
            @property
            def images(self):
                # Inverted coordinates: x1 < x0, bottom < top
                return [{"x0": 100, "x1": 50, "top": 15, "bottom": 5}]
            def crop(self, bbox):
                return MockCroppedPage()

        class MockPDF:
            def __init__(self, path):
                self.pages = [MockPage()]
            def close(self): pass

        m_pdfplumber.open = MockPDF
        monkeypatch.setitem(sys.modules, "pdfplumber", m_pdfplumber)

        m_pix2tex = ModuleType("pix2tex")
        m_pix2tex_cli = ModuleType("pix2tex.cli")
        class MockLatexOCR:
            def __call__(self, img): return "formula"
        m_pix2tex_cli.LatexOCR = MockLatexOCR
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_pdf = tmp_path / "inverted.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "output.md"

        # The converter should successfully execute because cropping/rendering exceptions on hybrid page elements
        # are caught and silently ignored.
        PdfToMd().convert(input_pdf, output_md, lambda p: None)

        assert output_md.exists()
        content = output_md.read_text(encoding="utf-8")
        assert "Hybrid text" in content
        assert "formula" not in content

    def test_pdf_to_md_ocr_page_image_failure(self, tmp_path, monkeypatch):
        """Test PDF scanned mode conversion when to_image fails during full OCR fallback."""
        m_pdfplumber = ModuleType("pdfplumber")

        class MockPage:
            def extract_text(self):
                return ""  # Empty text triggers OCR fallback
            def to_image(self, resolution=150):
                raise RuntimeError("Ghostscript rendering failed: segmentation fault")

        class MockPDF:
            def __init__(self, path):
                self.pages = [MockPage()]
            def close(self): pass

        m_pdfplumber.open = MockPDF
        monkeypatch.setitem(sys.modules, "pdfplumber", m_pdfplumber)

        m_pix2tex = ModuleType("pix2tex")
        m_pix2tex_cli = ModuleType("pix2tex.cli")
        class MockLatexOCR:
            def __call__(self, img): return "formula"
        m_pix2tex_cli.LatexOCR = MockLatexOCR
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_pdf = tmp_path / "scanned_fail.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "output.md"

        # Should raise ConversionError because the page image render failed in scanned page mode
        with pytest.raises(ConversionError) as exc_info:
            PdfToMd().convert(input_pdf, output_md, lambda p: None)

        assert "Error al renderizar u OCR en página 1" in str(exc_info.value)


class TestCliAdversarial:
    def test_cli_batch_output_dir_is_file(self, tmp_path):
        """Test CLI batch mode fails when --output-dir is an existing file."""
        csv_file = tmp_path / "file1.csv"
        csv_file.write_text("a,b\n1,2\n", encoding="utf-8")

        bad_output_dir = tmp_path / "output_file.json"
        bad_output_dir.write_text("{}", encoding="utf-8")

        runner = CliRunner()
        pattern = str(tmp_path / "*.csv")
        result = runner.invoke(app, [
            "convert",
            "--batch", pattern,
            "--to", "json",
            "--output-dir", str(bad_output_dir)
        ])

        assert result.exit_code != 0
        assert "Resumen de errores" in result.output

    def test_cli_batch_fail_fast_cancels_pending(self, tmp_path, monkeypatch):
        """Test CLI batch mode with --fail-fast terminates immediately and cancels pending tasks."""
        f1 = tmp_path / "file1.csv"
        f2 = tmp_path / "file2.csv"
        f3 = tmp_path / "file3.csv"
        f1.write_text("a,b\n1,2\n", encoding="utf-8")
        f2.write_text("a,b\n3,4\n", encoding="utf-8")
        f3.write_text("a,b\n5,6\n", encoding="utf-8")

        from omni_convert.core.pipeline import Pipeline
        from omni_convert.core.converter import ConversionError

        class MockPipeline(Pipeline):
            def __init__(self, registry, source, target, via=None):
                self.formats = [source, target]
            def run(self, input_path, output_path, progress=None):
                if "file1" in str(input_path):
                    raise ConversionError("Simulated pipeline failure")
                else:
                    output_path.write_text("{}", encoding="utf-8")

        monkeypatch.setattr("omni_convert.cli.build_pipeline", MockPipeline)

        runner = CliRunner()
        pattern = str(tmp_path / "file*.csv")
        result = runner.invoke(app, [
            "convert",
            "--batch", pattern,
            "--to", "json",
            "--fail-fast"
        ])

        assert result.exit_code != 0
        assert "Fail-fast" in result.output

    def test_cli_infer_format_no_extension(self, tmp_path):
        """Test CLI convert fails when input file has no extension and formats are not specified."""
        no_ext_file = tmp_path / "no_extension"
        no_ext_file.write_text("some data", encoding="utf-8")
        output_file = tmp_path / "output.json"

        runner = CliRunner()
        result = runner.invoke(app, ["convert", str(no_ext_file), str(output_file)])
        assert result.exit_code != 0
        assert "No se puede inferir el formato" in result.output
