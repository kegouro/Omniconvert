"""Tests del registro y de la pipeline."""

from __future__ import annotations

import pytest

from omni_convert.core.converter import ConversionError
from omni_convert.core.pipeline import NoConversionPathError, build_pipeline, find_path
from omni_convert.core.registry import ConverterRegistry, registry
from tests.conftest import make_text_converter


class TestRegistry:
    def test_register_y_get(self):
        reg = ConverterRegistry()
        cls = make_text_converter("foo", "bar")
        assert reg.register(cls) is cls
        assert reg.get("foo", "bar") is cls
        assert reg.get("bar", "foo") is None

    def test_duplicado_rechazado(self):
        reg = ConverterRegistry()
        reg.register(make_text_converter("foo", "bar"))
        with pytest.raises(ValueError, match="Ya existe un conversor"):
            reg.register(make_text_converter("foo", "bar"))

    def test_reregistro_de_la_misma_clase_es_inocuo(self):
        reg = ConverterRegistry()
        cls = make_text_converter("foo", "bar")
        reg.register(cls)
        assert reg.register(cls) is cls

    def test_formats_y_targets(self, fake_registry):
        assert fake_registry.formats() == {"a", "b", "c", "d", "x"}
        assert fake_registry.targets_from("a") == ["b", "x"]
        assert fake_registry.targets_from("zzz") == []

    def test_discover_registra_los_integrados(self):
        registry.discover()
        registrados = {key for key, _ in registry.items()}
        assert {("csv", "json"), ("json", "csv"), ("root", "csv"), ("mp3", "wav")} <= (registrados)

    def test_discover_es_idempotente(self):
        registry.discover()
        antes = registry.items()
        registry.discover()
        assert registry.items() == antes


class TestFindPath:
    def test_ruta_directa(self, fake_registry):
        steps = find_path(fake_registry, "a", "b")
        assert [cls.key() for cls in steps] == [("a", "b")]

    def test_ruta_mas_corta(self, fake_registry):
        # a->d puede ser a->b->c->d (3 pasos) o a->x->d (2 pasos): BFS elige la corta.
        steps = find_path(fake_registry, "a", "d")
        assert [cls.key() for cls in steps] == [("a", "x"), ("x", "d")]

    def test_mismo_formato_ruta_vacia(self, fake_registry):
        assert find_path(fake_registry, "a", "a") == []

    def test_sin_ruta(self, fake_registry):
        with pytest.raises(NoConversionPathError, match="de 'd' a 'a'"):
            find_path(fake_registry, "d", "a")


class TestPipeline:
    def test_ejecucion_encadenada(self, fake_registry, tmp_path):
        entrada = tmp_path / "datos.a"
        entrada.write_text("inicio")
        salida = tmp_path / "datos.d"

        pipeline = build_pipeline(fake_registry, "a", "d")
        fracciones: list[float] = []
        pipeline.run(entrada, salida, fracciones.append)

        assert salida.read_text() == "inicio->x->d"
        assert fracciones == sorted(fracciones), "el progreso debe ser monótono"
        assert fracciones[-1] == 1.0

    def test_via_fuerza_ruta_larga(self, fake_registry, tmp_path):
        entrada = tmp_path / "datos.a"
        entrada.write_text("inicio")
        salida = tmp_path / "datos.d"

        pipeline = build_pipeline(fake_registry, "a", "d", via=["b", "c"])
        assert pipeline.formats == ["a", "b", "c", "d"]
        pipeline.run(entrada, salida)
        assert salida.read_text() == "inicio->b->c->d"

    def test_mismo_formato_es_error(self, fake_registry):
        with pytest.raises(ConversionError, match="el mismo"):
            build_pipeline(fake_registry, "a", "a")
