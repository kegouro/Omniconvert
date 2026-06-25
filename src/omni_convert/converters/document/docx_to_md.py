"""Conversor de DOCX a Markdown."""

from __future__ import annotations

from pathlib import Path

from omni_convert.core.converter import (
    ConversionError,
    Converter,
    MissingDependencyError,
    ProgressCallback,
)
from omni_convert.core.registry import register


@register
class DocxToMd(Converter):
    source_format = "docx"
    target_format = "md"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        if not input_path.is_file():
            raise ConversionError(f"El archivo de entrada no existe: {input_path}")

        try:
            import docx
            from docx import Document  # noqa: F401
            from docx.oxml.table import CT_Tbl
            from docx.oxml.text.paragraph import CT_P
            from docx.table import Table
            from docx.text.paragraph import Paragraph
        except ImportError as exc:
            raise MissingDependencyError("python-docx", "extended") from exc

        try:
            doc = docx.Document(input_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            media_dir = output_path.parent / f"{output_path.stem}_media"
            media_rel = f"{output_path.stem}_media"
            img_counter = 0
            markdown_parts = []

            elements = doc.element.body
            total_elements = len(elements)

            for index, el in enumerate(elements):
                if isinstance(el, CT_P):
                    p = Paragraph(el, doc)
                    text = ""
                    for run in p.runs:
                        run_text = run.text or ""
                        # Buscar imágenes incrustadas en este run
                        blips = run._r.xpath('.//*[local-name()="blip"]')
                        for blip in blips:
                            embed_id = blip.get(
                                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                            )
                            if embed_id and embed_id in doc.part.related_parts:
                                img_counter += 1
                                part = doc.part.related_parts[embed_id]
                                content_type = part.content_type or ""
                                ext = ".png"
                                if "jpeg" in content_type or "jpg" in content_type:
                                    ext = ".jpg"
                                elif "gif" in content_type:
                                    ext = ".gif"
                                elif "svg" in content_type:
                                    ext = ".svg"
                                elif "webp" in content_type:
                                    ext = ".webp"

                                media_name = f"image_{img_counter}{ext}"
                                media_dir.mkdir(parents=True, exist_ok=True)
                                (media_dir / media_name).write_bytes(part.blob)
                                run_text += f"![image]({media_rel}/{media_name})"

                        # Formatear el texto del run
                        if run_text.strip():
                            # Separar espacios iniciales y finales para formatear correctamente en markdown
                            l_space = run_text[: len(run_text) - len(run_text.lstrip())]
                            r_space = run_text[len(run_text.rstrip()) :]
                            stripped = run_text.strip()
                            if run.bold and run.italic:
                                stripped = f"***{stripped}***"
                            elif run.bold:
                                stripped = f"**{stripped}**"
                            elif run.italic:
                                stripped = f"*{stripped}*"
                            run_text = f"{l_space}{stripped}{r_space}"

                        text += run_text

                    # Solo procesamos si el párrafo contiene texto
                    if text.strip():
                        style = p.style.name if p.style else "Normal"
                        if style and style.startswith("Heading"):
                            try:
                                level = int(style.split()[-1])
                                if 1 <= level <= 6:
                                    text = "#" * level + " " + text
                            except ValueError:
                                pass
                        elif style and style.startswith("List Bullet"):
                            text = "* " + text
                        elif style and style.startswith("List Number"):
                            text = "1. " + text

                        markdown_parts.append(text)

                elif isinstance(el, CT_Tbl):
                    tbl = Table(el, doc)
                    tbl_lines = []
                    for i, row in enumerate(tbl.rows):
                        cells = []
                        for cell in row.cells:
                            cleaned = cell.text.strip().replace("|", "\\|").replace("\n", "<br>")
                            cells.append(cleaned)
                        tbl_lines.append("| " + " | ".join(cells) + " |")
                        if i == 0:
                            tbl_lines.append("| " + " | ".join("---" for _ in cells) + " |")
                    if tbl_lines:
                        markdown_parts.append("\n".join(tbl_lines))

                progress((index + 1) / total_elements)

            output_path.write_text("\n\n".join(markdown_parts) + "\n", encoding="utf-8")
        except Exception as exc:
            raise ConversionError(f"Error al convertir DOCX a Markdown: {exc}") from exc
