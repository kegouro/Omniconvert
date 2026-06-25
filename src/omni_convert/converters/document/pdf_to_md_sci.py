"""Conversor avanzado de PDF a Markdown Científico usando marker-pdf."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from omni_convert.core.converter import (
    ConversionError,
    Converter,
    MissingDependencyError,
    ProgressCallback,
)
from omni_convert.core.registry import register

# Opciones para reducir el uso de GPU/LLM pesados durante OCR si es necesario
os.environ["MARKER_USE_LLM"] = "0"

_MARKER_MODELS = None


def get_marker_models():
    """Inicializa y cachea los modelos de marker a nivel de módulo."""
    global _MARKER_MODELS
    if _MARKER_MODELS is None:
        try:
            from marker.models import create_model_dict
        except ImportError as exc:
            raise MissingDependencyError("marker-pdf", "ocr") from exc

        # Silenciamos algunos logs innecesarios de marker
        logging.getLogger("surya").setLevel(logging.ERROR)
        logging.getLogger("marker").setLevel(logging.WARNING)

        _MARKER_MODELS = create_model_dict()
    return _MARKER_MODELS


@register
class PdfToMdScientific(Converter):
    """Conversor de PDF a Markdown estructurado con alta fidelidad para ecuaciones utilizando marker-pdf.
    Recomendado para documentos científicos y artículos de arXiv."""

    source_format = "pdf"
    target_format = "md-sci"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        if not input_path.is_file():
            raise ConversionError(f"El archivo de entrada no existe: {input_path}")

        try:
            from marker.converters.pdf import PdfConverter
        except ImportError as exc:
            raise MissingDependencyError("marker-pdf", "ocr") from exc

        progress(0.1)
        model_dict = get_marker_models()
        progress(0.4)

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Instanciar el convertidor con los modelos cacheados en memoria
            converter = PdfConverter(artifact_dict=model_dict)
            
            import threading
            import time

            stop_heartbeat = threading.Event()
            def heartbeat():
                current_p = 0.4
                while not stop_heartbeat.is_set():
                    time.sleep(1)
                    # Asymptotically approach 0.95
                    current_p = current_p + (0.95 - current_p) * 0.05
                    progress(current_p)

            hb_thread = threading.Thread(target=heartbeat, daemon=True)
            hb_thread.start()

            # Convertir el PDF (bloqueante)
            try:
                rendered = converter(str(input_path))
            finally:
                stop_heartbeat.set()
                hb_thread.join()
            progress(0.8)

            # Obtener el markdown. En versiones recientes (1.x) de marker, rendered tiene markdown.
            if hasattr(rendered, "markdown"):
                full_text = rendered.markdown
            else:
                from marker.output import text_from_rendered
                full_text, _, _ = text_from_rendered(rendered)

            output_path.write_text(full_text, encoding="utf-8")
            progress(1.0)
        except Exception as exc:
            raise ConversionError(f"Error en la conversión Marker-PDF: {exc}") from exc
