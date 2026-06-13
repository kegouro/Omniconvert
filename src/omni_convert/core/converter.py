"""Clase base y errores comunes para todos los conversores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

# Recibe la fracción completada de la conversión, entre 0.0 y 1.0.
ProgressCallback = Callable[[float], None]


class ConversionError(Exception):
    """Error producido durante una conversión."""


class MissingDependencyError(ConversionError):
    """Falta una dependencia opcional necesaria para este conversor."""

    def __init__(self, package: str, extra: str) -> None:
        self.package = package
        self.extra = extra
        super().__init__(
            f"Falta la dependencia opcional '{package}'. "
            f"Instálala con: pip install 'omniconvert[{extra}]'"
        )


class Converter(ABC):
    """Transforma un archivo de ``source_format`` a ``target_format``.

    Cada subclase es una arista del grafo de conversiones. Las dependencias
    pesadas deben importarse dentro de ``convert`` para que el registro de
    conversores funcione aunque los extras no estén instalados.
    """

    source_format: str
    target_format: str

    @abstractmethod
    def convert(
        self,
        input_path: Path,
        output_path: Path,
        progress: ProgressCallback,
    ) -> None:
        """Convierte ``input_path`` y escribe el resultado en ``output_path``."""

    @classmethod
    def key(cls) -> tuple[str, str]:
        return (cls.source_format, cls.target_format)
