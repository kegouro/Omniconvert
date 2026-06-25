"""Conversor de imágenes (PNG, JPG, JPEG) a fórmulas LaTeX usando pix2tex."""

from __future__ import annotations

from pathlib import Path

from omni_convert.core.converter import (
    ConversionError,
    Converter,
    MissingDependencyError,
    ProgressCallback,
)
from omni_convert.core.registry import register

_LATEX_MODEL = None


def get_latex_ocr_model():
    """Inicializa y cachea el modelo LatexOCR a nivel de módulo."""
    global _LATEX_MODEL
    if _LATEX_MODEL is None:
        try:
            from pix2tex.cli import LatexOCR
        except ImportError as exc:
            raise MissingDependencyError("pix2tex", "ocr") from exc
        _LATEX_MODEL = LatexOCR()
    return _LATEX_MODEL


@register
class PngToTex(Converter):
    """Conversor de imágenes PNG a fórmulas LaTeX."""

    source_format = "png"
    target_format = "latex"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        if not input_path.is_file():
            raise ConversionError(f"El archivo de entrada no existe: {input_path}")

        try:
            from PIL import Image
        except ImportError as exc:
            raise MissingDependencyError("pillow", "ocr") from exc

        progress(0.1)
        model = get_latex_ocr_model()
        progress(0.4)

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(input_path) as img:
                formula = model(img)
                progress(0.8)
                output_path.write_text(formula, encoding="utf-8")
            progress(1.0)
        except Exception as exc:
            raise ConversionError(f"Error en la conversión LaTeX OCR: {exc}") from exc


@register
class PdfToLatex(Converter):
    """Conversor de PDFs a fórmulas LaTeX."""

    source_format = "pdf"
    target_format = "latex"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        if not input_path.is_file():
            raise ConversionError(f"El archivo de entrada no existe: {input_path}")

        try:
            import pdfplumber
        except ImportError as exc:
            raise MissingDependencyError("pdfplumber", "extended") from exc

        progress(0.1)
        model = get_latex_ocr_model()
        progress(0.4)

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with pdfplumber.open(input_path) as pdf:
                formulas = []
                for idx, page in enumerate(pdf.pages):
                    img = page.to_image(resolution=150).original
                    try:
                        formula = model(img)
                        formulas.append(formula)
                    except Exception as page_exc:
                        formulas.append(f"% OCR failed for page {idx + 1}: {page_exc}")
                progress(0.8)
                output_path.write_text("\n\n".join(formulas), encoding="utf-8")
            progress(1.0)
        except Exception as exc:
            raise ConversionError(f"Error en la conversión LaTeX OCR desde PDF: {exc}") from exc


@register
class JpgToTex(PngToTex):
    """Conversor de imágenes JPG a fórmulas LaTeX."""

    source_format = "jpg"


@register
class JpegToTex(PngToTex):
    """Conversor de imágenes JPEG a fórmulas LaTeX."""

    source_format = "jpeg"
