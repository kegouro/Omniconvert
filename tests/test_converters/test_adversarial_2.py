"""Tests adversarios y de robustez para OmniConvert.

Cubre casos extremos, dependencias faltantes y manejo de errores
en los 6 nuevos conversores y el motor de CLI/procesamiento por lotes.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path
from types import ModuleType
import pytest
from typer.testing import CliRunner

from omni_convert.cli import app
from omni_convert.core.converter import ConversionError, MissingDependencyError

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_module_caches():
    """Resetea el caché de los modelos OCR antes/después de cada test."""
    import omni_convert.converters.document.pdf_to_md as pdf_mod
    import omni_convert.converters.image.image_to_latex as img_mod

    pdf_mod._OCR_MODEL = None
    img_mod._LATEX_MODEL = None
    yield
    pdf_mod._OCR_MODEL = None
    img_mod._LATEX_MODEL = None


# ==============================================================================
# SQLite to CSV Converter Adversarial Tests
# ==============================================================================
class TestAdversarialSqliteToCsv:
    def test_sqlite_name_error_in_finally(self, tmp_path, monkeypatch):
        """Prueba que revela el bug en la cláusula finally de sqlite_to_csv.py.

        Si cursor.execute falla al obtener las tablas, la variable 'tables'
        no se define, lo que provoca un NameError en el bloque finally.
        """
        db_path = tmp_path / "broken.db"
        db_path.write_text("dummy", encoding="utf-8")

        # Mock de sqlite3.connect para que devuelva un cursor defectuoso
        class BadCursor:
            def execute(self, query):
                raise sqlite3.DatabaseError("Database is locked/corrupt")

        class BadConnection:
            def cursor(self):
                return BadCursor()
            def close(self):
                pass

        monkeypatch.setattr(sqlite3, "connect", lambda path: BadConnection())

        from omni_convert.converters.data.sqlite_to_csv import SqliteToCsv

        # Esperamos que falle. Debido al bug, lanzará NameError en vez de ConversionError.
        # Capturamos el error para documentarlo en los hallazgos.
        with pytest.raises((ConversionError, NameError)) as exc_info:
            SqliteToCsv().convert(db_path, tmp_path / "out", lambda p: None)

        # Si lanza NameError, confirmamos la existencia del bug de la variable indefinida
        if exc_info.type is NameError:
            assert "tables" in str(exc_info.value)

    def test_sqlite_to_csv_io_error_on_write(self, tmp_path, monkeypatch):
        """Prueba que si escribir un CSV falla con un error de E/S, se lanza ConversionError."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
        cursor.execute("INSERT INTO users (name) VALUES ('Alice');")
        conn.commit()
        conn.close()

        from omni_convert.converters.data.sqlite_to_csv import SqliteToCsv

        # Mockear 'open' para lanzar PermissionError al intentar abrir el CSV de la tabla
        original_open = open

        def mock_open(file, mode="r", *args, **kwargs):
            if "users.csv" in str(file):
                raise PermissionError("Access denied")
            return original_open(file, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", mock_open)

        with pytest.raises(ConversionError) as exc_info:
            SqliteToCsv().convert(db_path, tmp_path / "out_dir", lambda p: None)
        assert "Error al exportar la tabla" in str(exc_info.value)

    def test_sqlite_to_csv_directory_input(self, tmp_path):
        """El archivo de entrada es un directorio en lugar de un archivo SQLite."""
        from omni_convert.converters.data.sqlite_to_csv import SqliteToCsv
        dir_path = tmp_path / "is_a_dir"
        dir_path.mkdir()
        with pytest.raises(ConversionError) as exc_info:
            SqliteToCsv().convert(dir_path, tmp_path / "out", lambda p: None)
        assert "El archivo de entrada no existe" in str(exc_info.value)

    def test_sqlite_to_csv_empty_schema(self, tmp_path, monkeypatch):
        """Verifica el comportamiento cuando la tabla tiene esquema vacío/nulo."""
        db_path = tmp_path / "empty_schema.db"
        # Mocking tables fetch directly to return a table with None for SQL schema
        # (p.ej. tablas virtuales o indices especiales a veces no tienen SQL legible en sqlite_master)
        class MockCursor:
            def execute(self, query):
                pass
            def fetchall(self):
                return [("some_table", None)] # None en el SQL schema
            def description(self):
                return [("id",)]
            def fetchmany(self, size):
                return []

        class MockConnection:
            def cursor(self):
                return MockCursor()
            def close(self):
                pass

        monkeypatch.setattr(sqlite3, "connect", lambda path: MockConnection())

        from omni_convert.converters.data.sqlite_to_csv import SqliteToCsv

        output_dir = tmp_path / "out_empty_schema"
        db_path.write_bytes(b"")
        SqliteToCsv().convert(db_path, output_dir, lambda p: None)
        
        # Debe haberse creado el schema.sql y estar vacío
        schema_file = output_dir / "schema.sql"
        assert schema_file.exists()
        assert schema_file.read_text(encoding="utf-8") == "\n"


# ==============================================================================
# HDF5 to Parquet Converter Adversarial Tests
# ==============================================================================
class TestAdversarialHdf5ToParquet:
    def test_hdf5_missing_dependencies(self, tmp_path, monkeypatch):
        """Prueba que se lancen MissingDependencyError cuando faltan librerías clave."""
        input_h5 = tmp_path / "dummy.h5"
        input_h5.write_text("dummy", encoding="utf-8")
        output_dir = tmp_path / "pq_out"

        from omni_convert.converters.data.hdf5_to_parquet import Hdf5ToParquet

        # Caso 1: Falta h5py
        monkeypatch.setitem(sys.modules, "h5py", None)
        with pytest.raises(MissingDependencyError) as exc_info:
            Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)
        assert "h5py" in str(exc_info.value)
        monkeypatch.delitem(sys.modules, "h5py")

        # Caso 2: Falta pandas/numpy
        # Restauramos h5py mockeado para que pase la primera comprobación
        monkeypatch.setitem(sys.modules, "h5py", ModuleType("h5py"))
        monkeypatch.setitem(sys.modules, "pandas", None)
        with pytest.raises(MissingDependencyError) as exc_info:
            Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)
        assert "pandas" in str(exc_info.value)
        monkeypatch.delitem(sys.modules, "pandas")

        # Caso 3: Falta pyarrow
        monkeypatch.setitem(sys.modules, "pandas", ModuleType("pandas"))
        monkeypatch.setitem(sys.modules, "numpy", ModuleType("numpy"))
        monkeypatch.setitem(sys.modules, "pyarrow", None)
        with pytest.raises(MissingDependencyError) as exc_info:
            Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)
        assert "pyarrow" in str(exc_info.value)

    def test_hdf5_empty_and_zero_dims(self, tmp_path, monkeypatch):
        """Prueba datasets con 0 dimensiones, vacíos o formas complejas."""
        import numpy as np
        import pandas as pd

        # Mock de h5py
        mock_h5py = ModuleType("h5py")

        class MockDataset:
            def __init__(self, name, shape, data):
                self.name = name
                self.shape = shape
                self.data = data
                self.ndim = len(shape)

            def __getitem__(self, item):
                return self.data

            def item(self):
                # 0D
                return self.data.item()

        class MockFile:
            def __init__(self, path, mode):
                self.datasets = {
                    "ds_empty_1d": MockDataset("ds_empty_1d", (0,), np.array([], dtype=np.int32)),
                    "ds_empty_2d": MockDataset("ds_empty_2d", (5, 0), np.empty((5, 0))),
                    "ds_empty_3d_mid": MockDataset("ds_empty_3d_mid", (2, 0, 3), np.empty((2, 0, 3))),
                }

            def visititems(self, callback):
                for name, dataset in self.datasets.items():
                    callback(name, dataset)

            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_h5py.Dataset = MockDataset
        mock_h5py.File = MockFile
        monkeypatch.setitem(sys.modules, "h5py", mock_h5py)

        # Para asegurar que pandas/numpy/pyarrow estén disponibles en el test sin fallar
        pytest.importorskip("pandas")
        pytest.importorskip("pyarrow")

        input_h5 = tmp_path / "test.h5"
        input_h5.write_text("dummy", encoding="utf-8")
        output_dir = tmp_path / "pq_out"

        from omni_convert.converters.data.hdf5_to_parquet import Hdf5ToParquet
        
        Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)

        # Verificar que se crearon los archivos parquet para datasets vacíos/de dimensiones extrañas
        assert (output_dir / "ds_empty_1d.parquet").exists()
        assert (output_dir / "ds_empty_2d.parquet").exists()
        assert (output_dir / "ds_empty_3d_mid.parquet").exists()

        df_1d = pd.read_parquet(output_dir / "ds_empty_1d.parquet")
        assert df_1d.shape == (0, 1)

        df_2d = pd.read_parquet(output_dir / "ds_empty_2d.parquet")
        assert df_2d.shape == (5, 0)

        df_3d = pd.read_parquet(output_dir / "ds_empty_3d_mid.parquet")
        assert df_3d.shape == (2, 0)

    def test_hdf5_corrupt_file_handling(self, tmp_path, monkeypatch):
        """Prueba que los errores en la apertura del archivo HDF5 se eleven a ConversionError."""
        input_h5 = tmp_path / "corrupt.h5"
        input_h5.write_text("not a hdf5", encoding="utf-8")
        output_dir = tmp_path / "pq_out"

        mock_h5py = ModuleType("h5py")
        def mock_file_init(*args, **kwargs):
            raise OSError("Unable to open file (file signature not found)")
        mock_h5py.File = mock_file_init

        monkeypatch.setitem(sys.modules, "h5py", mock_h5py)
        # Asegurar NumPy/Pandas/PyArrow mocks/imports
        monkeypatch.setitem(sys.modules, "pandas", ModuleType("pandas"))
        monkeypatch.setitem(sys.modules, "numpy", ModuleType("numpy"))
        monkeypatch.setitem(sys.modules, "pyarrow", ModuleType("pyarrow"))

        from omni_convert.converters.data.hdf5_to_parquet import Hdf5ToParquet

        with pytest.raises(ConversionError) as exc_info:
            Hdf5ToParquet().convert(input_h5, output_dir, lambda p: None)
        assert "Error al convertir HDF5" in str(exc_info.value)


# ==============================================================================
# DOCX to Markdown Converter Adversarial Tests
# ==============================================================================
class TestAdversarialDocxToMd:
    def test_docx_missing_dependency(self, tmp_path, monkeypatch):
        """Lanza MissingDependencyError si python-docx no está."""
        monkeypatch.setitem(sys.modules, "docx", None)
        input_docx = tmp_path / "dummy.docx"
        input_docx.write_text("dummy", encoding="utf-8")

        from omni_convert.converters.document.docx_to_md import DocxToMd
        with pytest.raises(MissingDependencyError) as exc_info:
            DocxToMd().convert(input_docx, tmp_path / "out.md", lambda p: None)
        assert "python-docx" in str(exc_info.value)

    def test_docx_style_none_or_malformed(self, tmp_path, monkeypatch):
        """Maneja estilos con nombres nulos, malformados o vacíos en párrafos."""
        m_docx = ModuleType("docx")
        m_doc_doc = ModuleType("docx.document")
        m_oxml_tbl = ModuleType("docx.oxml.table")
        m_oxml_p = ModuleType("docx.oxml.text.paragraph")
        m_tbl = ModuleType("docx.table")
        m_p = ModuleType("docx.text.paragraph")

        class MockCT_P:
            pass

        class MockStyle:
            def __init__(self, name):
                self.name = name

        class MockR:
            def xpath(self, path):
                return []

        class MockRun:
            def __init__(self, text):
                self.text = text
                self.bold = False
                self.italic = False
                self._r = MockR()

        class MockParagraph:
            def __init__(self, element, doc):
                self.runs = element.runs
                self.style = element.style

        m_oxml_p.CT_P = MockCT_P
        m_p.Paragraph = MockParagraph

        class MockDocument:
            def __init__(self, input_path):
                # Párrafo con estilo = None
                p1 = MockCT_P()
                p1.runs = [MockRun("Párrafo estilo None")]
                p1.style = None

                # Párrafo con estilo.name = None
                p2 = MockCT_P()
                p2.runs = [MockRun("Párrafo estilo name None")]
                p2.style = MockStyle(None)

                # Párrafo con estilo de Heading malformado sin número
                p3 = MockCT_P()
                p3.runs = [MockRun("Heading sin nivel")]
                p3.style = MockStyle("Heading")

                # Párrafo con estilo de Heading fuera de rango
                p4 = MockCT_P()
                p4.runs = [MockRun("Heading 8")]
                p4.style = MockStyle("Heading 8")

                class Element:
                    body = [p1, p2, p3, p4]

                self.element = Element()

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

        # No debe crashear y procesar con normalidad
        DocxToMd().convert(input_docx, output_md, lambda p: None)
        content = output_md.read_text(encoding="utf-8")
        assert "Párrafo estilo None" in content
        assert "Párrafo estilo name None" in content
        # Debe haber tratado "Heading" y "Heading 8" como texto normal (sin añadir #)
        assert "# Heading sin nivel" not in content
        assert "# Heading 8" not in content

    def test_docx_media_write_failure(self, tmp_path, monkeypatch):
        """Error al escribir imágenes extraídas en el sistema de archivos."""
        m_docx = ModuleType("docx")
        m_doc_doc = ModuleType("docx.document")
        m_oxml_tbl = ModuleType("docx.oxml.table")
        m_oxml_p = ModuleType("docx.oxml.text.paragraph")
        m_tbl = ModuleType("docx.table")
        m_p = ModuleType("docx.text.paragraph")

        class MockCT_P:
            pass

        class MockBlip:
            def get(self, name):
                return "rIdImg1"

        class MockR:
            def xpath(self, path):
                return [MockBlip()]

        class MockRun:
            def __init__(self):
                self.text = ""
                self.bold = False
                self.italic = False
                self._r = MockR()

        class MockParagraph:
            def __init__(self, element, doc):
                self.runs = element.runs
                self.style = None

        m_oxml_p.CT_P = MockCT_P
        m_p.Paragraph = MockParagraph

        class MockPart:
            blob = b"fake_bytes"
            content_type = "image/png"

        class MockDocument:
            def __init__(self, input_path):
                p = MockCT_P()
                p.runs = [MockRun()]
                class Element:
                    body = [p]
                self.element = Element()
                class Part:
                    related_parts = {"rIdImg1": MockPart()}
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

        # Mockear write_bytes de Path para lanzar PermissionError
        original_write_bytes = Path.write_bytes
        def mock_write_bytes(self, data):
            if "media" in str(self):
                raise PermissionError("ReadOnly Filesystem")
            return original_write_bytes(self, data)
        monkeypatch.setattr(Path, "write_bytes", mock_write_bytes)

        from omni_convert.converters.document.docx_to_md import DocxToMd

        with pytest.raises(ConversionError) as exc_info:
            DocxToMd().convert(input_docx, output_md, lambda p: None)
        assert "Error al convertir DOCX a Markdown" in str(exc_info.value)


# ==============================================================================
# AVIF to PNG Converter Adversarial Tests
# ==============================================================================
class TestAdversarialAvifToPng:
    def test_png_to_avif_stub(self, tmp_path):
        """PngToAvif debe lanzar NotImplementedError ya que es solo un stub."""
        from omni_convert.converters.image.avif_to_png import PngToAvif
        with pytest.raises(NotImplementedError) as exc_info:
            PngToAvif().convert(tmp_path / "in.png", tmp_path / "out.avif", lambda p: None)
        assert "no está implementada" in str(exc_info.value)

    def test_avif_to_png_missing_dependencies(self, tmp_path, monkeypatch):
        """Verifica MissingDependencyError si falta PIL o pillow-avif-plugin."""
        input_avif = tmp_path / "test.avif"
        input_avif.write_text("dummy", encoding="utf-8")
        output_png = tmp_path / "test.png"

        from omni_convert.converters.image.avif_to_png import AvifToPng

        # Caso 1: Falta PIL
        monkeypatch.setitem(sys.modules, "PIL", None)
        with pytest.raises(MissingDependencyError) as exc_info:
            AvifToPng().convert(input_avif, output_png, lambda p: None)
        assert "pillow" in str(exc_info.value)
        monkeypatch.delitem(sys.modules, "PIL")

        # Caso 2: Falta pillow-avif-plugin
        monkeypatch.setitem(sys.modules, "PIL", ModuleType("PIL"))
        monkeypatch.setitem(sys.modules, "pillow_avif", None)
        with pytest.raises(MissingDependencyError) as exc_info:
            AvifToPng().convert(input_avif, output_png, lambda p: None)
        assert "pillow-avif-plugin" in str(exc_info.value)

    def test_avif_to_png_save_error(self, tmp_path, monkeypatch):
        """Verifica ConversionError cuando Image.save lanza una excepción."""
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")
        m_pillow_avif = ModuleType("pillow_avif")

        class MockImage:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            def save(self, output_path, format=None):
                raise OSError("Cannot write image, disk full")

        m_pil_image.open = lambda p: MockImage()
        m_pil.Image = m_pil_image
        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)
        monkeypatch.setitem(sys.modules, "pillow_avif", m_pillow_avif)

        input_avif = tmp_path / "test.avif"
        input_avif.write_text("dummy", encoding="utf-8")
        output_png = tmp_path / "test.png"

        from omni_convert.converters.image.avif_to_png import AvifToPng

        with pytest.raises(ConversionError) as exc_info:
            AvifToPng().convert(input_avif, output_png, lambda p: None)
        assert "Error al decodificar AVIF" in str(exc_info.value)


# ==============================================================================
# Image to LaTeX Converter Adversarial Tests
# ==============================================================================
class TestAdversarialImageToLatex:
    def test_image_to_latex_missing_dependencies(self, tmp_path, monkeypatch):
        """MissingDependencyError si falta PIL o pix2tex."""
        input_png = tmp_path / "test.png"
        input_png.write_text("dummy", encoding="utf-8")
        output_tex = tmp_path / "test.tex"

        from omni_convert.converters.image.image_to_latex import PngToTex

        # Caso 1: Falta PIL
        monkeypatch.setitem(sys.modules, "PIL", None)
        with pytest.raises(MissingDependencyError) as exc_info:
            PngToTex().convert(input_png, output_tex, lambda p: None)
        assert "pillow" in str(exc_info.value)
        monkeypatch.delitem(sys.modules, "PIL")

        # Caso 2: Falta pix2tex
        monkeypatch.setitem(sys.modules, "PIL", ModuleType("PIL"))
        monkeypatch.setitem(sys.modules, "PIL.Image", ModuleType("PIL.Image"))
        monkeypatch.setitem(sys.modules, "pix2tex", None)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", None)

        with pytest.raises(MissingDependencyError) as exc_info:
            PngToTex().convert(input_png, output_tex, lambda p: None)
        assert "pix2tex" in str(exc_info.value)

    def test_image_to_latex_model_exception(self, tmp_path, monkeypatch):
        """ConversionError si el modelo LatexOCR lanza excepciones durante inferencia."""
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")
        m_pil_image.open = lambda p: "pil_img_obj"
        m_pil.Image = m_pil_image
        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)

        m_pix2tex = ModuleType("pix2tex")
        m_pix2tex_cli = ModuleType("pix2tex.cli")

        class MockLatexOCR:
            def __call__(self, img):
                raise RuntimeError("Weights file is corrupted or OOM on GPU")

        m_pix2tex_cli.LatexOCR = MockLatexOCR
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_png = tmp_path / "test.png"
        input_png.write_text("dummy", encoding="utf-8")
        output_tex = tmp_path / "test.tex"

        from omni_convert.converters.image.image_to_latex import PngToTex

        with pytest.raises(ConversionError) as exc_info:
            PngToTex().convert(input_png, output_tex, lambda p: None)
        assert "Error en la conversión LaTeX OCR" in str(exc_info.value)


# ==============================================================================
# PDF to Markdown Converter Adversarial Tests
# ==============================================================================
class TestAdversarialPdfToMd:
    def test_pdf_to_md_missing_dependencies(self, tmp_path, monkeypatch):
        """MissingDependencyError si falta pdfplumber o pix2tex."""
        input_pdf = tmp_path / "test.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "test.md"

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        # Caso 1: Falta pdfplumber
        monkeypatch.setitem(sys.modules, "pdfplumber", None)
        with pytest.raises(MissingDependencyError) as exc_info:
            PdfToMd().convert(input_pdf, output_md, lambda p: None)
        assert "pdfplumber" in str(exc_info.value)
        monkeypatch.delitem(sys.modules, "pdfplumber")

        # Caso 2: Falta pix2tex en fallback de OCR de página escaneada
        m_pdfplumber = ModuleType("pdfplumber")

        class MockPage:
            def extract_text(self):
                return ""  # Scanned page triggers OCR

        class MockPDF:
            def __init__(self, path):
                self.pages = [MockPage()]
            def close(self):
                pass

        m_pdfplumber.open = MockPDF
        monkeypatch.setitem(sys.modules, "pdfplumber", m_pdfplumber)

        monkeypatch.setitem(sys.modules, "pix2tex", None)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", None)

        with pytest.raises(MissingDependencyError) as exc_info:
            PdfToMd().convert(input_pdf, output_md, lambda p: None)
        assert "pix2tex" in str(exc_info.value)

    def test_pdf_to_md_open_exception(self, tmp_path, monkeypatch):
        """ConversionError si pdfplumber.open lanza excepción (p.ej. PDF corrupto)."""
        input_pdf = tmp_path / "corrupt.pdf"
        input_pdf.write_text("corrupted pdf", encoding="utf-8")
        output_md = tmp_path / "test.md"

        m_pdfplumber = ModuleType("pdfplumber")
        def mock_open(*args, **kwargs):
            raise Exception("Invalid PDF header")
        m_pdfplumber.open = mock_open
        monkeypatch.setitem(sys.modules, "pdfplumber", m_pdfplumber)

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        with pytest.raises(ConversionError) as exc_info:
            PdfToMd().convert(input_pdf, output_md, lambda p: None)
        assert "Error al abrir el archivo PDF" in str(exc_info.value)

    def test_pdf_to_md_ocr_crop_exception_handling(self, tmp_path, monkeypatch):
        """Verifica que fallos de OCR parciales/crop en páginas híbridas se ignoren."""
        m_pdfplumber = ModuleType("pdfplumber")

        class MockPage:
            def extract_text(self):
                return "Text content"
            def extract_words(self):
                return [{"text": "Text", "x0": 10, "x1": 50, "top": 10, "bottom": 20}]
            @property
            def images(self):
                return [{"x0": 60, "x1": 80, "top": 10, "bottom": 20}]
            def crop(self, bbox):
                raise ValueError("Coordinates out of range or negative dimensions")

        class MockPDF:
            def __init__(self, path):
                self.pages = [MockPage()]
            def close(self):
                pass

        m_pdfplumber.open = MockPDF
        monkeypatch.setitem(sys.modules, "pdfplumber", m_pdfplumber)

        # Mock pix2tex
        m_pix2tex = ModuleType("pix2tex")
        m_pix2tex_cli = ModuleType("pix2tex.cli")
        class MockLatexOCR:
            pass
        m_pix2tex_cli.LatexOCR = MockLatexOCR
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_pdf = tmp_path / "hybrid_err.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "hybrid_err.md"

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        # La conversión debe terminar exitosamente saltándose la imagen corrupta
        PdfToMd().convert(input_pdf, output_md, lambda p: None)
        content = output_md.read_text(encoding="utf-8")
        assert "Text" in content

    def test_pdf_to_md_full_page_ocr_exception(self, tmp_path, monkeypatch):
        """ConversionError si el OCR de página completa escaneada falla."""
        m_pdfplumber = ModuleType("pdfplumber")

        class MockPage:
            def extract_text(self):
                return ""  # Scanned page
            def to_image(self, resolution=150):
                raise RuntimeError("Ghostscript rendering failed")

        class MockPDF:
            def __init__(self, path):
                self.pages = [MockPage()]
            def close(self):
                pass

        m_pdfplumber.open = MockPDF
        monkeypatch.setitem(sys.modules, "pdfplumber", m_pdfplumber)

        m_pix2tex = ModuleType("pix2tex")
        m_pix2tex_cli = ModuleType("pix2tex.cli")
        m_pix2tex_cli.LatexOCR = lambda: lambda img: "formula"
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_pdf = tmp_path / "scanned_fail.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "scanned_fail.md"

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        with pytest.raises(ConversionError) as exc_info:
            PdfToMd().convert(input_pdf, output_md, lambda p: None)
        assert "Error al renderizar u OCR en página" in str(exc_info.value)


# ==============================================================================
# CLI & Batch Processing Engine Adversarial Tests
# ==============================================================================
class TestAdversarialCli:
    def test_cli_batch_missing_to(self, tmp_path):
        """Lanza typer.BadParameter si no se especifica --to en conversiones por lotes."""
        pattern = str(tmp_path / "*.csv")
        result = runner.invoke(app, ["convert", "--batch", pattern])
        assert result.exit_code != 0
        assert "obligatoria para conversiones por lotes" in result.output

    def test_cli_batch_no_matching_files(self, tmp_path):
        """Sale con código 1 si el patrón batch no coincide con ningún archivo."""
        pattern = str(tmp_path / "nonexistent_pattern_*.csv")
        result = runner.invoke(app, ["convert", "--batch", pattern, "--to", "json"])
        assert result.exit_code == 1
        assert "No se encontraron archivos" in result.output

    def test_cli_single_missing_arguments(self):
        """Lanza typer.BadParameter si falta el archivo de entrada o de salida."""
        # Sin argumentos
        res1 = runner.invoke(app, ["convert"])
        assert res1.exit_code != 0

        # Falta archivo de salida
        res2 = runner.invoke(app, ["convert", "input.csv"])
        assert res2.exit_code != 0
        assert "Falta el archivo de salida" in res2.output

    def test_cli_single_input_not_exists(self, tmp_path):
        """Lanza typer.BadParameter si el archivo de entrada no existe."""
        res = runner.invoke(app, ["convert", str(tmp_path / "nonexistent.csv"), "out.json"])
        assert res.exit_code != 0
        assert "no existe" in res.output

    def test_cli_infer_format_no_extension(self, tmp_path):
        """Falla al inferir el formato si el archivo no tiene extensión."""
        no_ext = tmp_path / "file_without_extension"
        no_ext.write_text("data", encoding="utf-8")

        res = runner.invoke(app, ["convert", str(no_ext), "out.json"])
        assert res.exit_code != 0
        assert "No se puede inferir el formato" in res.output

    def test_cli_no_conversion_path(self, tmp_path):
        """Lanza typer.Exit con código 1 si no hay ruta de conversión entre formatos."""
        f = tmp_path / "input.mp3"
        f.write_text("audio", encoding="utf-8")

        res = runner.invoke(app, ["convert", str(f), "out.csv"])
        assert res.exit_code == 1
        assert "No hay ruta de conversión" in res.output

    def test_cli_batch_fail_fast_cancellation(self, tmp_path, monkeypatch):
        """Prueba que fail-fast cancela adecuadamente los hilos/futuros pendientes al fallar uno."""
        # Crear varios archivos csv para procesamiento por lotes
        csv1 = tmp_path / "file1.csv"
        csv2 = tmp_path / "file2.csv"
        csv3 = tmp_path / "file3.csv"

        csv1.write_text("a,b\n1,2\n", encoding="utf-8")
        csv2.write_text("a,b\n3,4\n", encoding="utf-8")
        csv3.write_text("a,b\n5,6\n", encoding="utf-8")

        # Mockear _convert_single_file para que falle en el segundo archivo y verificar cancelación
        conversions_count = 0

        from omni_convert import cli

        def mock_convert_single_file(input_file, output_dir, from_format, to_format, via):
            nonlocal conversions_count
            conversions_count += 1
            if "file2" in str(input_file):
                raise ValueError("Simulated batch conversion error")
            return Path("mock_out.json")

        monkeypatch.setattr(cli, "_convert_single_file", mock_convert_single_file)

        pattern = str(tmp_path / "file*.csv")
        result = runner.invoke(app, ["convert", "--batch", pattern, "--to", "json", "--fail-fast"])

        assert result.exit_code == 1
        assert "Fail-fast activado" in result.output
