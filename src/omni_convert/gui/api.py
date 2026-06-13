"""Puente Python <-> JavaScript de la GUI.

Esta clase no importa pywebview a nivel de módulo: solo los métodos que abren
diálogos nativos lo necesitan. Así la lógica es testeable sin GUI instalada.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from omni_convert.core.converter import ConversionError
from omni_convert.core.pipeline import NoConversionPathError, build_pipeline, find_path
from omni_convert.core.registry import registry


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f}".replace(".", ",") + f" {unit}"
        size /= 1024
    return f"{int(size)} GB"


class GuiApi:
    """Métodos expuestos a JavaScript como ``pywebview.api.*``.

    Los métodos con guion bajo no se exponen (convención de pywebview).
    """

    def __init__(self) -> None:
        self._window = None

    def _bind(self, window) -> None:
        self._window = window

    def _notify(self, fraction: float) -> None:
        if self._window is not None:
            self._window.evaluate_js(f"omni.onProgress({fraction:.4f})")

    def known_formats(self) -> list[str]:
        """Formatos que aparecen en algún conversor registrado."""
        registry.discover()
        return sorted(registry.formats())

    def source_info(self, path: str) -> dict:
        """Describe un archivo de entrada y los formatos alcanzables desde él."""
        registry.discover()
        source = Path(path)
        fmt = source.suffix.lstrip(".").lower()
        targets = []
        if fmt:
            for candidate in sorted(registry.formats()):
                if candidate == fmt:
                    continue
                try:
                    steps = find_path(registry, fmt, candidate)
                except NoConversionPathError:
                    continue
                chain = [steps[0].source_format] + [s.target_format for s in steps]
                targets.append({"format": candidate, "chain": chain, "steps": len(steps)})
        return {
            "path": str(source),
            "name": source.name,
            "size": _human_size(source.stat().st_size) if source.exists() else "",
            "format": fmt or "?",
            "targets": targets,
        }

    def choose_input(self) -> dict | None:
        import webview

        selection = self._window.create_file_dialog(webview.OPEN_DIALOG)
        if not selection:
            return None
        path = selection if isinstance(selection, str) else selection[0]
        return self.source_info(path)

    def default_output(self, input_path: str, target: str) -> str:
        """Ruta de salida propuesta: misma carpeta y nombre, nueva extensión.

        Si ya existe un archivo así, propone un nombre alternativo para no
        pisar nada sin que el usuario lo decida.
        """
        source = Path(input_path)
        candidate = source.with_suffix(f".{target}")
        if candidate.exists():
            candidate = candidate.with_name(f"{source.stem} (convertido).{target}")
        return str(candidate)

    def choose_output(self, suggested: str) -> str | None:
        import webview

        proposed = Path(suggested)
        selection = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=str(proposed.parent),
            save_filename=proposed.name,
        )
        if not selection:
            return None
        return selection if isinstance(selection, str) else selection[0]

    def convert(self, input_path: str, source: str, target: str, output_path: str) -> dict:
        registry.discover()
        try:
            pipeline = build_pipeline(registry, source, target)
            pipeline.run(Path(input_path), Path(output_path), self._notify)
        except ConversionError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "output": output_path}

    def reveal(self, path: str) -> None:
        """Muestra el archivo en el gestor de archivos del sistema."""
        target = Path(path)
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(target)], check=False)
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", "/select,", str(target)], check=False)
        else:
            subprocess.run(["xdg-open", str(target.parent)], check=False)
