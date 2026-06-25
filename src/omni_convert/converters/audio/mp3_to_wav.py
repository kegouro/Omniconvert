"""MP3 -> WAV usando pydub (requiere ffmpeg en el sistema)."""

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
class Mp3ToWav(Converter):
    source_format = "mp3"
    target_format = "wav"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        try:
            from pydub import AudioSegment
        except ImportError as exc:
            raise MissingDependencyError("pydub", "extended") from exc

        progress(0.1)
        try:
            audio = AudioSegment.from_mp3(str(input_path))
        except FileNotFoundError as exc:
            raise ConversionError(
                "pydub necesita ffmpeg para decodificar MP3 y no se encontró en el "
                "PATH. Instálalo con: brew install ffmpeg (macOS) o apt install ffmpeg"
            ) from exc
        except Exception as exc:  # CouldntDecodeError y similares de pydub
            raise ConversionError(f"No se pudo decodificar {input_path}: {exc}") from exc

        progress(0.7)
        audio.export(str(output_path), format="wav")
        progress(1.0)
