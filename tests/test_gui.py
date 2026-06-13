"""Tests de la lógica de la GUI (GuiApi), sin pywebview ni ventana."""

from __future__ import annotations

import json

from omni_convert.gui.api import GuiApi, _human_size


class FakeWindow:
    """Captura las llamadas evaluate_js que la API envía a la ventana."""

    def __init__(self) -> None:
        self.scripts: list[str] = []

    def evaluate_js(self, script: str) -> None:
        self.scripts.append(script)


class TestHumanSize:
    def test_unidades(self):
        assert _human_size(512) == "512 B"
        assert _human_size(2458) == "2,4 KB"
        assert _human_size(5 * 1024 * 1024) == "5,0 MB"


class TestSourceInfo:
    def test_csv_alcanza_json(self, tmp_path):
        archivo = tmp_path / "datos.csv"
        archivo.write_text("a,b\n1,2\n", encoding="utf-8")

        info = GuiApi().source_info(str(archivo))

        assert info["format"] == "csv"
        assert info["name"] == "datos.csv"
        destinos = {t["format"]: t for t in info["targets"]}
        assert destinos["json"]["chain"] == ["csv", "json"]
        assert destinos["json"]["steps"] == 1

    def test_root_alcanza_json_encadenado(self, tmp_path):
        archivo = tmp_path / "eventos.root"
        archivo.write_bytes(b"")

        info = GuiApi().source_info(str(archivo))

        destinos = {t["format"]: t for t in info["targets"]}
        assert destinos["json"]["chain"] == ["root", "csv", "json"]
        assert destinos["json"]["steps"] == 2

    def test_extension_desconocida_sin_destinos(self, tmp_path):
        archivo = tmp_path / "raro.xyz"
        archivo.write_bytes(b"")

        info = GuiApi().source_info(str(archivo))

        assert info["targets"] == []


class TestDefaultOutput:
    def test_misma_carpeta_nueva_extension(self, tmp_path):
        entrada = tmp_path / "datos.csv"
        salida = GuiApi().default_output(str(entrada), "json")
        assert salida == str(tmp_path / "datos.json")

    def test_evita_pisar_archivos_existentes(self, tmp_path):
        entrada = tmp_path / "datos.csv"
        (tmp_path / "datos.json").write_text("[]", encoding="utf-8")

        salida = GuiApi().default_output(str(entrada), "json")

        assert salida == str(tmp_path / "datos (convertido).json")


class TestConvert:
    def test_conversion_con_progreso(self, tmp_path):
        entrada = tmp_path / "datos.csv"
        entrada.write_text("a\n1\n2\n", encoding="utf-8")
        salida = tmp_path / "datos.json"

        api = GuiApi()
        window = FakeWindow()
        api._bind(window)
        resultado = api.convert(str(entrada), "csv", "json", str(salida))

        assert resultado == {"ok": True, "output": str(salida)}
        assert json.loads(salida.read_text(encoding="utf-8")) == [{"a": "1"}, {"a": "2"}]
        assert window.scripts[-1] == "omni.onProgress(1.0000)"

    def test_error_devuelve_mensaje(self, tmp_path):
        entrada = tmp_path / "datos.csv"
        entrada.write_text("a\n1\n", encoding="utf-8")

        resultado = GuiApi().convert(str(entrada), "csv", "wav", str(tmp_path / "x.wav"))

        assert resultado["ok"] is False
        assert "No hay ruta de conversión" in resultado["error"]
