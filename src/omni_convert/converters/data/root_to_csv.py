"""ROOT (CERN) -> CSV usando uproot.

Convierte el primer TTree o RNTuple del archivo. Solo se exportan ramas planas
(escalares por evento); las ramas jagged (longitud variable) se omiten porque
no tienen representación tabular directa.
"""

from __future__ import annotations

import csv
from pathlib import Path

from omni_convert.core.converter import (
    ConversionError,
    Converter,
    MissingDependencyError,
    ProgressCallback,
)
from omni_convert.core.registry import register

PROGRESS_EVERY = 1000


def _is_flat(array) -> bool:
    if getattr(array, "ndim", 0) != 1:
        return False
    if array.dtype != object:
        return True
    # dtype=object: aceptamos solo escalares (p. ej. strings), no sub-arrays.
    return len(array) == 0 or isinstance(array[0], (str, bytes, int, float, bool))


@register
class RootToCsv(Converter):
    source_format = "root"
    target_format = "csv"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        try:
            import uproot
        except ImportError as exc:
            raise MissingDependencyError("uproot", "root") from exc

        with uproot.open(input_path) as root_file:
            tree_names = [
                name
                for name, classname in root_file.classnames().items()
                if classname.startswith("TTree") or "RNTuple" in classname
            ]
            if not tree_names:
                raise ConversionError(f"No se encontró ningún TTree ni RNTuple en {input_path}")
            tree = root_file[tree_names[0]]
            arrays = tree.arrays(library="np")

        # TTree devuelve un dict de arrays; RNTuple, un array estructurado.
        if not isinstance(arrays, dict):
            arrays = {name: arrays[name] for name in arrays.dtype.names or ()}

        columns = {name: arr for name, arr in arrays.items() if _is_flat(arr)}
        skipped = sorted(set(arrays) - set(columns))
        if not columns:
            raise ConversionError(
                "El TTree no tiene ramas planas convertibles a CSV "
                f"(ramas omitidas: {', '.join(skipped)})"
            )

        total_rows = max(1, len(next(iter(columns.values()))))
        with open(output_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(list(columns))
            for index in range(total_rows):
                writer.writerow([columns[name][index] for name in columns])
                if (index + 1) % PROGRESS_EVERY == 0:
                    progress((index + 1) / total_rows)
        progress(1.0)
