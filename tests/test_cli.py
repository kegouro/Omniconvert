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


class TestBatchConvert:
    def test_batch_convert_csv_to_json(self, tmp_path):
        # Create mock csv files
        f1 = tmp_path / "data1.csv"
        f1.write_text("name,val\nA,1\n", encoding="utf-8")
        f2 = tmp_path / "data2.csv"
        f2.write_text("name,val\nB,2\n", encoding="utf-8")

        # Run batch conversion
        pattern = str(tmp_path / "*.csv")
        result = runner.invoke(app, ["convert", "--batch", pattern, "--to", "json"])

        assert result.exit_code == 0, result.output
        assert (tmp_path / "data1.json").exists()
        assert (tmp_path / "data2.json").exists()
        assert json.loads((tmp_path / "data1.json").read_text(encoding="utf-8")) == [{"name": "A", "val": "1"}]
        assert json.loads((tmp_path / "data2.json").read_text(encoding="utf-8")) == [{"name": "B", "val": "2"}]

    def test_batch_convert_missing_to_fails(self, tmp_path):
        pattern = str(tmp_path / "*.csv")
        result = runner.invoke(app, ["convert", "--batch", pattern])
        assert result.exit_code != 0
        assert "obligatoria" in result.output or "to" in result.output

    def test_batch_convert_with_output_dir(self, tmp_path):
        f1 = tmp_path / "data1.csv"
        f1.write_text("name,val\nA,1\n", encoding="utf-8")
        out_dir = tmp_path / "output_dir"

        pattern = str(tmp_path / "*.csv")
        result = runner.invoke(app, ["convert", "--batch", pattern, "--to", "json", "--output-dir", str(out_dir)])

        assert result.exit_code == 0, result.output
        assert (out_dir / "data1.json").exists()

    def test_batch_convert_no_match(self, tmp_path):
        pattern = str(tmp_path / "nonexistent*.csv")
        result = runner.invoke(app, ["convert", "--batch", pattern, "--to", "json"])
        assert result.exit_code != 0
        assert "No se encontraron archivos" in result.output

    def test_batch_convert_fail_fast(self, tmp_path):
        f1 = tmp_path / "data1.csv"
        f1.write_text("name,val\nA,1\n", encoding="utf-8")
        f2 = tmp_path / "data2.invalid"
        f2.write_text("bad data", encoding="utf-8")

        pattern = str(tmp_path / "data*")
        result = runner.invoke(app, ["convert", "--batch", pattern, "--to", "json", "--fail-fast"])
        assert result.exit_code == 1
        assert "Error" in result.output or "Fail-fast" in result.output

    def test_batch_convert_continue_on_error(self, tmp_path):
        f1 = tmp_path / "data1.csv"
        f1.write_text("name,val\nA,1\n", encoding="utf-8")
        f2 = tmp_path / "data2.txt"
        f2.write_text("bad data", encoding="utf-8")

        pattern = str(tmp_path / "data*")
        result = runner.invoke(app, ["convert", "--batch", pattern, "--to", "json"])
        assert result.exit_code == 1
        assert "Resumen de errores" in result.output
        assert (tmp_path / "data1.json").exists()

