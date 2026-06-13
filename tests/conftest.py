"""Utilidades compartidas por los tests."""

from __future__ import annotations

import pytest

from omni_convert.core.converter import Converter
from omni_convert.core.registry import ConverterRegistry


def make_text_converter(source: str, target: str) -> type[Converter]:
    """Conversor falso que copia el texto añadiendo la traza '->destino'."""

    class TextConverter(Converter):
        source_format = source
        target_format = target

        def convert(self, input_path, output_path, progress):
            output_path.write_text(input_path.read_text() + f"->{target}")
            progress(1.0)

    TextConverter.__name__ = f"Fake{source.capitalize()}To{target.capitalize()}"
    return TextConverter


@pytest.fixture
def fake_registry() -> ConverterRegistry:
    """Registro aislado con el grafo a->b->c->d (sin atajos)."""
    reg = ConverterRegistry()
    for source, target in [("a", "b"), ("b", "c"), ("c", "d"), ("a", "x"), ("x", "d")]:
        reg.register(make_text_converter(source, target))
    return reg
