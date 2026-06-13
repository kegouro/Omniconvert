"""Registro dinámico de conversores con auto-descubrimiento."""

from __future__ import annotations

import importlib
import pkgutil

from omni_convert.core.converter import Converter

DEFAULT_PACKAGE = "omni_convert.converters"


class ConverterRegistry:
    """Mapa ``(formato_origen, formato_destino) -> clase de conversor``."""

    def __init__(self) -> None:
        self._converters: dict[tuple[str, str], type[Converter]] = {}
        self._discovered: set[str] = set()

    def register(self, cls: type[Converter]) -> type[Converter]:
        """Decorador: registra una subclase de Converter.

        Lanza ``ValueError`` si ya existe un conversor para el mismo par,
        salvo que sea exactamente la misma clase (re-import inocuo).
        """
        key = cls.key()
        existing = self._converters.get(key)
        if existing is not None and existing is not cls:
            raise ValueError(
                f"Ya existe un conversor para {key[0]} -> {key[1]}: {existing.__name__}"
            )
        self._converters[key] = cls
        return cls

    def get(self, source: str, target: str) -> type[Converter] | None:
        return self._converters.get((source, target))

    def items(self) -> list[tuple[tuple[str, str], type[Converter]]]:
        return sorted(self._converters.items())

    def formats(self) -> set[str]:
        return {fmt for key in self._converters for fmt in key}

    def targets_from(self, source: str) -> list[str]:
        return sorted(dst for (src, dst) in self._converters if src == source)

    def discover(self, package: str = DEFAULT_PACKAGE) -> None:
        """Importa todos los módulos de ``package`` para que se auto-registren.

        Los módulos de conversores solo importan stdlib a nivel de módulo, por
        lo que el descubrimiento no falla aunque falten extras opcionales.
        """
        if package in self._discovered:
            return
        pkg = importlib.import_module(package)
        for module_info in pkgutil.walk_packages(pkg.__path__, prefix=f"{pkg.__name__}."):
            importlib.import_module(module_info.name)
        self._discovered.add(package)


registry = ConverterRegistry()
register = registry.register
