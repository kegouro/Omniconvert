"""Tests end-to-end de la CLI con Typer."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from omni_convert.cli import app

runner = CliRunner()


class TestConvert:
    def test_csv_a_json(self, tmp_path):
        entrada = tmp_path / "datos.csv"
        entrada.write_text("nombre,edad\nAna,30\n", encoding="utf-8")
        salida = tmp_path / "datos.json"

        result = runner.invoke(app, ["convert", str(entrada), str(salida)])

        assert result.exit_code == 0, result.output
        assert json.loads(salida.read_text(encoding="utf-8")) == [{"nombre": "Ana", "edad": "30"}]

    def test_formato_sin_ruta_falla_con_mensaje(self, tmp_path):
        entrada = tmp_path / "datos.csv"
        entrada.write_text("a\n1\n", encoding="utf-8")

        result = runner.invoke(app, ["convert", str(entrada), str(tmp_path / "x.mp3")])

        assert result.exit_code == 1
        assert "No hay ruta de conversión" in result.output

    def test_entrada_inexistente_falla(self, tmp_path):
        result = runner.invoke(
            app, ["convert", str(tmp_path / "no_existe.csv"), str(tmp_path / "x.json")]
        )
        assert result.exit_code != 0

    def test_cadena_root_a_json(self, tmp_path):
        uproot = pytest.importorskip("uproot")
        np = pytest.importorskip("numpy")

        root_path = tmp_path / "eventos.root"
        with uproot.recreate(root_path) as root_file:
            root_file["eventos"] = {"id": np.array([7, 8], dtype=np.int64)}
        salida = tmp_path / "eventos.json"

        result = runner.invoke(app, ["convert", str(root_path), str(salida)])

        assert result.exit_code == 0, result.output
        assert "root → csv → json" in result.output
        assert json.loads(salida.read_text(encoding="utf-8")) == [
            {"id": "7"},
            {"id": "8"},
        ]


class TestFormats:
    def test_lista_los_integrados(self):
        result = runner.invoke(app, ["formats"])
        assert result.exit_code == 0
        for nombre in ["CsvToJson", "JsonToCsv", "RootToCsv", "Mp3ToWav"]:
            assert nombre in result.output


class TestPath:
    def test_ruta_encadenada_sin_extras(self):
        # root->csv está registrado aunque uproot no esté instalado (import perezoso).
        result = runner.invoke(app, ["path", "root", "json"])
        assert result.exit_code == 0
        assert "root → csv → json" in result.output

    def test_sin_ruta(self):
        result = runner.invoke(app, ["path", "wav", "csv"])
        assert result.exit_code == 1
        assert "No hay ruta de conversión" in result.output
