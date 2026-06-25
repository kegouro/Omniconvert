"""Tests de los conversores de datos."""

from __future__ import annotations

import csv
import json

import pytest

from omni_convert.converters.data.csv_to_json import CsvToJson
from omni_convert.converters.data.json_to_csv import JsonToCsv
from omni_convert.converters.data.root_to_csv import RootToCsv
from omni_convert.core.converter import ConversionError

NOOP = lambda fraction: None  # noqa: E731


class TestCsvToJson:
    def test_conversion_basica(self, tmp_path):
        entrada = tmp_path / "datos.csv"
        entrada.write_text("nombre,edad\nAna,30\nJosé,25\n", encoding="utf-8")
        salida = tmp_path / "datos.json"

        CsvToJson().convert(entrada, salida, NOOP)

        assert json.loads(salida.read_text(encoding="utf-8")) == [
            {"nombre": "Ana", "edad": "30"},
            {"nombre": "José", "edad": "25"},
        ]

    def test_csv_vacio_produce_lista_vacia(self, tmp_path):
        entrada = tmp_path / "vacio.csv"
        entrada.write_text("col_a,col_b\n", encoding="utf-8")
        salida = tmp_path / "vacio.json"

        CsvToJson().convert(entrada, salida, NOOP)

        assert json.loads(salida.read_text(encoding="utf-8")) == []

    def test_progreso_termina_en_uno(self, tmp_path):
        entrada = tmp_path / "datos.csv"
        entrada.write_text("x\n" + "\n".join(str(i) for i in range(50)), encoding="utf-8")
        salida = tmp_path / "datos.json"

        fracciones: list[float] = []
        CsvToJson().convert(entrada, salida, fracciones.append)
        assert fracciones[-1] == 1.0


class TestJsonToCsv:
    def test_round_trip(self, tmp_path):
        original = [
            {"nombre": "Ana", "edad": "30"},
            {"nombre": "José", "edad": "25"},
        ]
        json_path = tmp_path / "datos.json"
        json_path.write_text(json.dumps(original), encoding="utf-8")
        csv_path = tmp_path / "datos.csv"

        JsonToCsv().convert(json_path, csv_path, NOOP)

        with open(csv_path, encoding="utf-8", newline="") as handle:
            assert list(csv.DictReader(handle)) == original

    def test_claves_heterogeneas_se_rellenan(self, tmp_path):
        json_path = tmp_path / "datos.json"
        json_path.write_text(json.dumps([{"a": 1}, {"b": 2}]), encoding="utf-8")
        csv_path = tmp_path / "datos.csv"

        JsonToCsv().convert(json_path, csv_path, NOOP)

        with open(csv_path, encoding="utf-8", newline="") as handle:
            filas = list(csv.DictReader(handle))
        assert filas == [{"a": "1", "b": ""}, {"a": "", "b": "2"}]

    def test_json_no_tabular_es_error(self, tmp_path):
        json_path = tmp_path / "datos.json"
        json_path.write_text(json.dumps({"no": "es una lista"}), encoding="utf-8")

        with pytest.raises(ConversionError, match="lista de objetos"):
            JsonToCsv().convert(json_path, tmp_path / "salida.csv", NOOP)

    def test_json_invalido_es_error(self, tmp_path):
        json_path = tmp_path / "roto.json"
        json_path.write_text("{esto no es json", encoding="utf-8")

        with pytest.raises(ConversionError, match="JSON inválido"):
            JsonToCsv().convert(json_path, tmp_path / "salida.csv", NOOP)


class TestRootToCsv:
    def test_conversion_basica(self, tmp_path):
        uproot = pytest.importorskip("uproot")
        np = pytest.importorskip("numpy")

        root_path = tmp_path / "eventos.root"
        with uproot.recreate(root_path) as root_file:
            root_file["eventos"] = {
                "id": np.array([1, 2, 3], dtype=np.int64),
                "energia": np.array([10.5, 20.25, 30.0]),
            }
        csv_path = tmp_path / "eventos.csv"

        RootToCsv().convert(root_path, csv_path, NOOP)

        with open(csv_path, encoding="utf-8", newline="") as handle:
            filas = list(csv.DictReader(handle))
        assert [fila["id"] for fila in filas] == ["1", "2", "3"]
        assert [float(fila["energia"]) for fila in filas] == [10.5, 20.25, 30.0]

    def test_sin_ttree_es_error(self, tmp_path):
        uproot = pytest.importorskip("uproot")

        root_path = tmp_path / "vacio.root"
        with uproot.recreate(root_path):
            pass  # archivo ROOT válido pero sin TTree

        with pytest.raises(ConversionError, match="ningún TTree"):
            RootToCsv().convert(root_path, tmp_path / "salida.csv", NOOP)

    def test_sin_uproot_pide_extra(self, tmp_path, monkeypatch):
        import sys

        from omni_convert.core.converter import MissingDependencyError

        monkeypatch.setitem(sys.modules, "uproot", None)
        with pytest.raises(MissingDependencyError, match=r"omniconvert\[extended\]"):
            RootToCsv().convert(tmp_path / "x.root", tmp_path / "x.csv", NOOP)
