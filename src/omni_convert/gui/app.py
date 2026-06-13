"""Arranque de la ventana de OmniConvert."""

from __future__ import annotations

from importlib.resources import files

from omni_convert.core.converter import MissingDependencyError
from omni_convert.gui.api import GuiApi

PAPER = "#F6F3EC"


def launch() -> None:
    """Abre la ventana de la aplicación (bloquea hasta que se cierra)."""
    try:
        import webview
    except ImportError as exc:
        raise MissingDependencyError("pywebview", "gui") from exc

    html = (files("omni_convert.gui") / "static" / "index.html").read_text(encoding="utf-8")
    api = GuiApi()
    window = webview.create_window(
        "OmniConvert",
        html=html,
        js_api=api,
        width=720,
        height=680,
        min_size=(580, 560),
        background_color=PAPER,
    )
    api._bind(window)
    webview.start()
