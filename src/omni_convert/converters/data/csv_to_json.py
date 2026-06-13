"""CSV -> JSON (lista de objetos, una entrada por fila)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from omni_convert.core.converter import Converter, ProgressCallback
from omni_convert.core.registry import register

PROGRESS_EVERY = 1000


@register
class CsvToJson(Converter):
    source_format = "csv"
    target_format = "json"

    def convert(self, input_path: Path, output_path: Path, progress: ProgressCallback) -> None:
        with open(input_path, encoding="utf-8", newline="") as handle:
            total_rows = max(1, sum(1 for _ in handle) - 1)

        rows: list[dict[str, str]] = []
        with open(input_path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for count, row in enumerate(reader, start=1):
                rows.append(row)
                if count % PROGRESS_EVERY == 0:
                    progress(count / total_rows)

        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False, indent=2)
        progress(1.0)
