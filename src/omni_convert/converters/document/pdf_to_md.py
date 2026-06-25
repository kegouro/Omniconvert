"""Conversor de PDF a Markdown con fallback de OCR interno para fórmulas e imágenes."""

from __future__ import annotations

from pathlib import Path

from omni_convert.core.converter import (
    ConversionError,
    Converter,
    MissingDependencyError,
    ProgressCallback,
)
from omni_convert.core.registry import register

_OCR_MODEL = None


def get_ocr_model():
    """Inicializa y cachea el modelo LatexOCR a nivel de módulo."""
    global _OCR_MODEL
    if _OCR_MODEL is None:
        try:
            from pix2tex.cli import LatexOCR
        except ImportError as exc:
            raise MissingDependencyError("pix2tex", "ocr") from exc
        _OCR_MODEL = LatexOCR()
    return _OCR_MODEL


@register
class PdfToMd(Converter):
    """Conversor de PDF a Markdown con fallback de OCR para fórmulas matemáticas."""

    source_format = "pdf"
    target_format = "md"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        if not input_path.is_file():
            raise ConversionError(f"El archivo de entrada no existe: {input_path}")

        try:
            import pdfplumber
        except ImportError as exc:
            raise MissingDependencyError("pdfplumber", "extended") from exc

        pdf = None
        try:
            try:
                pdf = pdfplumber.open(input_path)
            except Exception as exc:
                raise ConversionError(f"Error al abrir el archivo PDF: {exc}") from exc

            total_pages = len(pdf.pages)
            if total_pages == 0:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("", encoding="utf-8")
                progress(1.0)
                return

            markdown_pages = []
            model = None

            for idx, page in enumerate(pdf.pages):
                text = page.extract_text()

                if not text or not text.strip():
                    # Scanned image page - Full OCR Fallback
                    if model is None:
                        model = get_ocr_model()

                    try:
                        pil_img = page.to_image(resolution=150).original
                        formula = model(pil_img)
                        markdown_pages.append(f"$$\n{formula}\n$$")
                    except Exception as exc:
                        markdown_pages.append(f"<!-- OCR falló en la página {idx + 1}: {exc} -->")
                else:
                    # Hybrid page - Merge Text & Images chronologically by coordinates
                    words = page.extract_words()
                    images = page.images
                    items = []

                    for word in words:
                        items.append({
                            "type": "word",
                            "text": word["text"],
                            "x0": word["x0"],
                            "x1": word["x1"],
                            "top": word["top"],
                            "bottom": word["bottom"],
                        })

                    for img in images:
                        x0 = img.get("x0", 0)
                        top = img.get("top", 0)
                        x1 = img.get("x1", x0)
                        bottom = img.get("bottom", top)
                        items.append({
                            "type": "image",
                            "x0": x0,
                            "x1": x1,
                            "top": top,
                            "bottom": bottom,
                        })

                    # Sort elements by top offset
                    items.sort(key=lambda x: x["top"])

                    # Group elements into lines
                    lines = []
                    if items:
                        current_line = [items[0]]
                        baseline_top = items[0]["top"]
                        for item in items[1:]:
                            if abs(item["top"] - baseline_top) <= 5.0:
                                current_line.append(item)
                            else:
                                lines.append(current_line)
                                current_line = [item]
                                baseline_top = item["top"]
                        lines.append(current_line)

                    # Process each line and build line markdown
                    markdown_lines = []
                    for line in lines:
                        line.sort(key=lambda x: x["x0"])
                        line_parts = []
                        for item in line:
                            if item["type"] == "word":
                                line_parts.append(item["text"])
                            elif item["type"] == "image":
                                if model is None:
                                    model = get_ocr_model()

                                try:
                                    # Crop the page bounding box directly in points coordinates
                                    bbox = (item["x0"], item["top"], item["x1"], item["bottom"])
                                    cropped = page.crop(bbox)
                                    cropped_img = cropped.to_image(resolution=150).original
                                    formula = model(cropped_img)
                                    if formula:
                                        if len(line) == 1:
                                            line_parts.append(f"$$\n{formula}\n$$")
                                        else:
                                            line_parts.append(f"${formula}$")
                                except Exception:
                                    # Skip failed OCR elements on hybrid pages
                                    pass

                        if line_parts:
                            markdown_lines.append(" ".join(line_parts))

                    markdown_pages.append("\n".join(markdown_lines))

                progress((idx + 1) / total_pages)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("\n\n---\n\n".join(markdown_pages) + "\n", encoding="utf-8")

        except Exception as exc:
            if not isinstance(exc, ConversionError):
                raise ConversionError(f"Error durante la conversión de PDF a Markdown: {exc}") from exc
            raise
        finally:
            if pdf is not None:
                pdf.close()
