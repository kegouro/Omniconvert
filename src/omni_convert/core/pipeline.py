"""Encadenamiento de conversiones: búsqueda de rutas y ejecución."""

from __future__ import annotations

import tempfile
from collections import deque
from collections.abc import Sequence
from pathlib import Path

from omni_convert.core.converter import ConversionError, Converter, ProgressCallback
from omni_convert.core.registry import ConverterRegistry


class NoConversionPathError(ConversionError):
    """No existe ninguna cadena de conversores entre dos formatos."""

    def __init__(self, source: str, target: str, known_formats: set[str]) -> None:
        known = ", ".join(sorted(known_formats)) or "(ninguno)"
        super().__init__(
            f"No hay ruta de conversión de '{source}' a '{target}'. Formatos conocidos: {known}"
        )


def find_path(registry: ConverterRegistry, source: str, target: str) -> list[type[Converter]]:
    """Ruta más corta (BFS) de conversores entre dos formatos."""
    if source == target:
        return []
    previous: dict[str, str] = {}
    visited = {source}
    queue = deque([source])
    while queue:
        current = queue.popleft()
        if current == target:
            break
        for nxt in registry.targets_from(current):
            if nxt not in visited:
                visited.add(nxt)
                previous[nxt] = current
                queue.append(nxt)
    if target not in visited:
        raise NoConversionPathError(source, target, registry.formats())

    chain = [target]
    while chain[-1] != source:
        chain.append(previous[chain[-1]])
    chain.reverse()
    steps = []
    for src, dst in zip(chain, chain[1:], strict=False):
        cls = registry.get(src, dst)
        assert cls is not None  # BFS solo recorre aristas existentes
        steps.append(cls)
    return steps


def build_pipeline(
    registry: ConverterRegistry,
    source: str,
    target: str,
    via: Sequence[str] = (),
) -> Pipeline:
    """Construye la pipeline source -> [via...] -> target."""
    waypoints = [source, *via, target]
    steps: list[Converter] = []
    for src, dst in zip(waypoints, waypoints[1:], strict=False):
        steps.extend(cls() for cls in find_path(registry, src, dst))
    if not steps:
        raise ConversionError(f"El formato de origen y destino son el mismo: '{source}'")
    return Pipeline(steps)


class Pipeline:
    """Secuencia de conversores que se ejecutan con archivos intermedios."""

    def __init__(self, steps: Sequence[Converter]) -> None:
        if not steps:
            raise ValueError("Una pipeline necesita al menos un conversor")
        self.steps = list(steps)

    @property
    def formats(self) -> list[str]:
        """Cadena de formatos recorrida, p. ej. ['root', 'csv', 'json']."""
        return [step.source_format for step in self.steps] + [self.steps[-1].target_format]

    def run(
        self,
        input_path: Path,
        output_path: Path,
        progress: ProgressCallback | None = None,
    ) -> None:
        report = progress or (lambda fraction: None)
        total = len(self.steps)
        with tempfile.TemporaryDirectory(prefix="omniconvert-") as tmp_dir:
            current = Path(input_path)
            for index, step in enumerate(self.steps):
                is_last = index == total - 1
                destination = (
                    Path(output_path)
                    if is_last
                    else Path(tmp_dir) / f"paso_{index}.{step.target_format}"
                )

                def step_progress(fraction: float, base: int = index) -> None:
                    report((base + min(max(fraction, 0.0), 1.0)) / total)

                step.convert(current, destination, step_progress)
                current = destination
        report(1.0)
