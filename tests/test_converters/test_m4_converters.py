"""Tests de los conversores implementados en el Milestone 4 (Image to LaTeX y PDF to Markdown)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from omni_convert.core.converter import ConversionError, MissingDependencyError


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


class TestImageToLatex:
    def test_image_to_latex_conversion(self, tmp_path, monkeypatch):
        # Mock PIL
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")

        class MockImage:
            def __init__(self, path_or_fp):
                self.path_or_fp = path_or_fp

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        m_pil_image.open = MockImage
        m_pil.Image = m_pil_image
        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)

        # Mock pix2tex
        m_pix2tex = ModuleType("pix2tex")
        m_pix2tex_cli = ModuleType("pix2tex.cli")

        class MockLatexOCR:
            def __call__(self, img):
                return r"\alpha + \beta = \gamma"

        m_pix2tex_cli.LatexOCR = MockLatexOCR
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        # Crear archivos dummy
        input_png = tmp_path / "formula.png"
        input_png.write_text("dummy", encoding="utf-8")
        output_tex = tmp_path / "formula.tex"

        from omni_convert.converters.image.image_to_latex import PngToTex

        progress_values = []
        PngToTex().convert(input_png, output_tex, progress_values.append)

        assert output_tex.exists()
        assert output_tex.read_text(encoding="utf-8") == r"\alpha + \beta = \gamma"
        assert progress_values[-1] == 1.0

        # Verificar alias classes
        from omni_convert.converters.image.image_to_latex import JpegToTex, JpgToTex

        assert JpgToTex.source_format == "jpg"
        assert JpegToTex.source_format == "jpeg"

    def test_image_to_latex_missing_pix2tex(self, tmp_path, monkeypatch):
        # Mock PIL
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")
        m_pil_image.open = lambda path: None
        m_pil.Image = m_pil_image
        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)

        # Hacer que pix2tex lance ImportError
        monkeypatch.setitem(sys.modules, "pix2tex", None)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", None)

        input_png = tmp_path / "formula.png"
        input_png.write_text("dummy", encoding="utf-8")
        output_tex = tmp_path / "formula.tex"

        from omni_convert.converters.image.image_to_latex import PngToTex

        with pytest.raises(MissingDependencyError) as exc_info:
            PngToTex().convert(input_png, output_tex, lambda p: None)
        assert "pix2tex" in str(exc_info.value)

    def test_image_to_latex_missing_pillow(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "PIL", None)
        monkeypatch.setitem(sys.modules, "PIL.Image", None)

        input_png = tmp_path / "formula.png"
        input_png.write_text("dummy", encoding="utf-8")
        output_tex = tmp_path / "formula.tex"

        from omni_convert.converters.image.image_to_latex import PngToTex

        with pytest.raises(MissingDependencyError) as exc_info:
            PngToTex().convert(input_png, output_tex, lambda p: None)
        assert "pillow" in str(exc_info.value)

    def test_image_to_latex_conversion_error(self, tmp_path, monkeypatch):
        # Mock PIL
        m_pil = ModuleType("PIL")
        m_pil_image = ModuleType("PIL.Image")

        def open_error(path):
            raise OSError("Invalid image file")

        m_pil_image.open = open_error
        m_pil.Image = m_pil_image
        monkeypatch.setitem(sys.modules, "PIL", m_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", m_pil_image)

        # Mock pix2tex
        m_pix2tex = ModuleType("pix2tex")
        m_pix2tex_cli = ModuleType("pix2tex.cli")

        class MockLatexOCR:
            pass

        m_pix2tex_cli.LatexOCR = MockLatexOCR
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_png = tmp_path / "formula.png"
        input_png.write_text("dummy", encoding="utf-8")
        output_tex = tmp_path / "formula.tex"

        from omni_convert.converters.image.image_to_latex import PngToTex

        with pytest.raises(ConversionError) as exc_info:
            PngToTex().convert(input_png, output_tex, lambda p: None)
        assert "LaTeX OCR" in str(exc_info.value)


class TestPdfToMd:
    def test_pdf_to_md_missing_pdfplumber(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "pdfplumber", None)
        input_pdf = tmp_path / "test.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "test.md"

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        with pytest.raises(MissingDependencyError) as exc_info:
            PdfToMd().convert(input_pdf, output_md, lambda p: None)
        assert "pdfplumber" in str(exc_info.value)

    def test_pdf_to_md_empty(self, tmp_path, monkeypatch):
        m_pdfplumber = ModuleType("pdfplumber")

        class MockPDF:
            def __init__(self, path):
                self.pages = []

            def close(self):
                pass

        m_pdfplumber.open = MockPDF
        monkeypatch.setitem(sys.modules, "pdfplumber", m_pdfplumber)

        input_pdf = tmp_path / "empty.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "empty.md"

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        progress_values = []
        PdfToMd().convert(input_pdf, output_md, progress_values.append)

        assert output_md.exists()
        assert output_md.read_text(encoding="utf-8") == ""
        assert progress_values[-1] == 1.0

    def test_pdf_to_md_full_page_ocr(self, tmp_path, monkeypatch):
        # Mock pdfplumber
        m_pdfplumber = ModuleType("pdfplumber")

        class MockPageImage:
            def __init__(self, original):
                self.original = original

        class MockPage:
            def __init__(self):
                pass

            def extract_text(self):
                return ""  # No text -> OCR Fallback

            def to_image(self, resolution=150):
                return MockPageImage("dummy_full_page_pil_image")

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
            def __call__(self, img):
                assert img == "dummy_full_page_pil_image"
                return r"\int_a^b f(x) dx"

        m_pix2tex_cli.LatexOCR = MockLatexOCR
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_pdf = tmp_path / "scanned.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "scanned.md"

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        PdfToMd().convert(input_pdf, output_md, lambda p: None)

        expected = "$$\n\\int_a^b f(x) dx\n$$\n"
        assert output_md.read_text(encoding="utf-8") == expected

    def test_pdf_to_md_hybrid_merging(self, tmp_path, monkeypatch):
        # Mock pdfplumber
        m_pdfplumber = ModuleType("pdfplumber")

        class MockPageImage:
            def __init__(self, original):
                self.original = original

        class MockCroppedPage:
            def __init__(self, bbox):
                self.bbox = bbox

            def to_image(self, resolution=150):
                return MockPageImage(f"crop_pil_{self.bbox}")

        class MockPage:
            def __init__(self):
                self.height = 800
                self.width = 600

            def extract_text(self):
                return "Hello world"  # Has text -> hybrid mode

            def extract_words(self):
                return [
                    {"text": "Hello", "x0": 10, "x1": 50, "top": 10, "bottom": 20},
                    {"text": "world", "x0": 60, "x1": 100, "top": 10, "bottom": 20},
                    {"text": "below", "x0": 10, "x1": 50, "top": 30, "bottom": 40},
                ]

            @property
            def images(self):
                return [
                    {"x0": 55, "x1": 75, "top": 29, "bottom": 39},  # On line 2
                    {"x0": 10, "x1": 100, "top": 100, "bottom": 150},  # On line 3
                ]

            def crop(self, bbox):
                return MockCroppedPage(bbox)

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
            def __call__(self, img):
                if img == "crop_pil_(55, 29, 75, 39)":
                    return "img1_formula"
                elif img == "crop_pil_(10, 100, 100, 150)":
                    return "img2_formula"
                return "unknown"

        m_pix2tex_cli.LatexOCR = MockLatexOCR
        m_pix2tex.cli = m_pix2tex_cli
        monkeypatch.setitem(sys.modules, "pix2tex", m_pix2tex)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", m_pix2tex_cli)

        input_pdf = tmp_path / "hybrid.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "hybrid.md"

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        PdfToMd().convert(input_pdf, output_md, lambda p: None)

        expected = (
            "Hello world\n"
            "below $img1_formula$\n"
            "$$\n"
            "img2_formula\n"
            "$$\n"
        )
        assert output_md.read_text(encoding="utf-8") == expected

    def test_pdf_to_md_missing_pix2tex_on_fallback(self, tmp_path, monkeypatch):
        # Mock pdfplumber to trigger OCR fallback
        m_pdfplumber = ModuleType("pdfplumber")

        class MockPage:
            def extract_text(self):
                return ""

            def to_image(self, resolution=150):
                class MockPageImage:
                    original = "dummy_pil"
                return MockPageImage()

        class MockPDF:
            def __init__(self, path):
                self.pages = [MockPage()]

            def close(self):
                pass

        m_pdfplumber.open = MockPDF
        monkeypatch.setitem(sys.modules, "pdfplumber", m_pdfplumber)

        # Make pix2tex missing
        monkeypatch.setitem(sys.modules, "pix2tex", None)
        monkeypatch.setitem(sys.modules, "pix2tex.cli", None)

        input_pdf = tmp_path / "scanned.pdf"
        input_pdf.write_text("dummy", encoding="utf-8")
        output_md = tmp_path / "scanned.md"

        from omni_convert.converters.document.pdf_to_md import PdfToMd

        with pytest.raises(MissingDependencyError) as exc_info:
            PdfToMd().convert(input_pdf, output_md, lambda p: None)
        assert "pix2tex" in str(exc_info.value)
