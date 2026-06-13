"""Tests del conversor MP3 -> WAV.

El test unitario inyecta un módulo pydub falso en sys.modules, así que no
necesita pydub ni ffmpeg. La integración real solo corre si ambos existen.
"""

from __future__ import annotations

import shutil
import sys
import types
from pathlib import Path

import pytest

from omni_convert.converters.audio.mp3_to_wav import Mp3ToWav
from omni_convert.core.converter import ConversionError, MissingDependencyError

NOOP = lambda fraction: None  # noqa: E731


def _fake_pydub(decoded: dict) -> types.ModuleType:
    class FakeSegment:
        def export(self, out_path, format):
            assert format == "wav"
            Path(out_path).write_bytes(b"RIFF-fake-wav")

    class FakeAudioSegment:
        @classmethod
        def from_mp3(cls, path):
            decoded["path"] = path
            return FakeSegment()

    module = types.ModuleType("pydub")
    module.AudioSegment = FakeAudioSegment
    return module


class TestMp3ToWav:
    def test_conversion_con_pydub_falso(self, tmp_path, monkeypatch):
        decoded: dict = {}
        monkeypatch.setitem(sys.modules, "pydub", _fake_pydub(decoded))

        mp3_path = tmp_path / "cancion.mp3"
        mp3_path.write_bytes(b"ID3-fake-mp3")
        wav_path = tmp_path / "cancion.wav"

        fracciones: list[float] = []
        Mp3ToWav().convert(mp3_path, wav_path, fracciones.append)

        assert wav_path.read_bytes() == b"RIFF-fake-wav"
        assert decoded["path"] == str(mp3_path)
        assert fracciones[-1] == 1.0

    def test_sin_pydub_pide_extra(self, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "pydub", None)
        with pytest.raises(MissingDependencyError, match=r"omniconvert\[audio\]"):
            Mp3ToWav().convert(tmp_path / "x.mp3", tmp_path / "x.wav", NOOP)

    def test_error_de_decodificacion_es_conversion_error(self, tmp_path, monkeypatch):
        module = types.ModuleType("pydub")

        class FakeAudioSegment:
            @classmethod
            def from_mp3(cls, path):
                raise RuntimeError("datos corruptos")

        module.AudioSegment = FakeAudioSegment
        monkeypatch.setitem(sys.modules, "pydub", module)

        mp3_path = tmp_path / "roto.mp3"
        mp3_path.write_bytes(b"basura")
        with pytest.raises(ConversionError, match="No se pudo decodificar"):
            Mp3ToWav().convert(mp3_path, tmp_path / "roto.wav", NOOP)


def _audio_real_disponible() -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    try:
        import pydub  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(not _audio_real_disponible(), reason="requiere pydub + ffmpeg")
def test_integracion_mp3_real(tmp_path):
    from pydub import AudioSegment

    mp3_path = tmp_path / "silencio.mp3"
    AudioSegment.silent(duration=300).export(mp3_path, format="mp3")
    wav_path = tmp_path / "silencio.wav"

    Mp3ToWav().convert(mp3_path, wav_path, NOOP)

    assert wav_path.read_bytes()[:4] == b"RIFF"
