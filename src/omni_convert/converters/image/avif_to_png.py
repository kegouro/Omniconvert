"""Conversor de AVIF a PNG (decodificación) y stub de PNG a AVIF."""

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
class AvifToPng(Converter):
    source_format = "avif"
    target_format = "png"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        if not input_path.is_file():
            raise ConversionError(f"El archivo de entrada no existe: {input_path}")

        try:
            from PIL import Image
        except ImportError as exc:
            raise MissingDependencyError("pillow", "extended") from exc

        try:
            import pillow_avif  # noqa: F401
        except ImportError as exc:
            raise MissingDependencyError("pillow-avif-plugin", "extended") from exc

        try:
            progress(0.1)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(input_path) as img:
                progress(0.5)
                img.save(output_path, format="PNG")
            progress(1.0)
        except Exception as exc:
            raise ConversionError(f"Error al decodificar AVIF a PNG: {exc}") from exc


@register
class PngToAvif(Converter):
    source_format = "png"
    target_format = "avif"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        raise NotImplementedError("La codificación AVIF no está implementada")
