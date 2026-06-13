"""JSON (lista de objetos) -> CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from omni_convert.core.converter import ConversionError, Converter, ProgressCallback
from omni_convert.core.registry import register

PROGRESS_EVERY = 1000


@register
class JsonToCsv(Converter):
    source_format = "json"
    target_format = "csv"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        with open(input_path, encoding="utf-8") as handle:
            try:
                data = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ConversionError(f"JSON inválido en {input_path}: {exc}") from exc

        if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
            raise ConversionError(
                "Para convertir a CSV, el JSON debe ser una lista de objetos "
                '(p. ej. [{"col": "valor"}, ...])'
            )

        # Unión de claves preservando el orden de aparición.
        fieldnames: dict[str, None] = {}
        for row in data:
            for key in row:
                fieldnames.setdefault(key, None)

        total_rows = max(1, len(data))
        with open(output_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fieldnames), restval="")
            writer.writeheader()
            for count, row in enumerate(data, start=1):
                writer.writerow(row)
                if count % PROGRESS_EVERY == 0:
                    progress(count / total_rows)
        progress(1.0)
