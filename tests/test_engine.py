# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: tests del motor sin alterar el audio del usuario: se simula su
# salida de `pactl list sinks` y su lista de módulos.

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import equalinux.core.engine_pulse as eng  # noqa: E402

FAKE_SINKS = """\
Destino #8
	Estado: RUNNING
	Nombre: alsa_output.usb-CM.analog-stereo
	Descripción: USB Audio Estéreo

Destino #9
	Estado: SUSPENDED
	Nombre: equalinux_eq
	Descripción: LADSPA Plugin Multiband EQ on USB Audio Estéreo
	Especificación de muestra: float32le 2ch 44100Hz
"""

ENGLISH_FAKE_SINKS = """\
Sink #8
	State: RUNNING
	Name: alsa_output.usb-CM.analog-stereo
	Description: USB Audio Estéreo

Sink #9
	State: SUSPENDED
	Name: equalinux_eq
	Description: LADSPA Plugin Multiband EQ on USB Audio Estéreo
	Sample Specification: float32le 2ch 44100Hz
"""

FAKE_MODULES = "36\tmodule-ladspa-sink\tsink_name=equalinux_eq\n"


def _stub_run(monkeypatch, sinks=FAKE_SINKS, modules=FAKE_MODULES,
              default="alsa_output.usb-CM.analog-stereo"):
    monkeypatch.setattr(eng, "_run", lambda args: (
        modules if "modules" in args else
        sinks if "sinks" in args else
        default if "get-default-sink" in args else ""))


def test_list_sinks_parse_es(monkeypatch):
    _stub_run(monkeypatch)
    sinks = eng._list_sinks()
    assert len(sinks) == 2
    assert sinks[1]["name"] == "equalinux_eq"
    assert sinks[1]["index"] == 9


def test_list_sinks_parse_en(monkeypatch, ):
    _stub_run(monkeypatch, sinks=ENGLISH_FAKE_SINKS)
    sinks = eng._list_sinks()
    names = [s["name"] for s in sinks]
    assert "equalinux_eq" in names


def test_loaded_master_resolved(monkeypatch):
    # Regla E4: el maestro se lee de los args del módulo (sink_master=)
    fake_modules = ("36\tmodule-ladspa-sink\tsink_name=equalinux_eq "
                    "sink_master=alsa_output.usb-CM.analog-stereo\n")
    _stub_run(monkeypatch, modules=fake_modules)
    eng_engine = eng.PulseLadspaEngine()
    assert eng_engine._loaded_master_name() ==         "alsa_output.usb-CM.analog-stereo"


def test_list_masters_excludes_ladspa_sinks(monkeypatch):
    _stub_run(monkeypatch)
    eng_engine = eng.PulseLadspaEngine()
    masters = eng_engine.list_masters()
    assert "equalinux_eq" not in masters
    assert "alsa_output.usb-CM.analog-stereo" in masters


def test_unload_when_missing_is_noop(monkeypatch):
    _stub_run(monkeypatch, modules="0\tno-ma-hash\targs\n")
    eng_engine = eng.PulseLadspaEngine()
    eng_engine.unload()  # no explota, no intenta unload del EQ inexistente


def test_set_bands_guard_length(monkeypatch):
    eng_engine = eng.PulseLadspaEngine()
    try:
        eng_engine.set_bands([0.0] * 3)
    except eng.EngineError as exc:
        assert "15" in str(exc)
        return
    raise AssertionError("debería rechazar longitud incorrecta")


def test_algorithm_payload_flags_false():
    payload = eng._algorithm_payload([1.0] * 15)
    # estructura (d: 15 valores, b: 15 False): solo validamos la creación
    assert payload is not None


def test_move_streams_skips_internal_and_moves_the_rest(monkeypatch):
    calls = []
    fake_out = ("7\t8\t14\tprotocol-native.c\tfloat32le\n"
                "14\t9\t-\tmodule-ladspa-sink.c\tfloat32le\n")

    def fake_run(args):
        calls.append(args)
        if "sink-inputs" in args:
            return fake_out
        return ""

    monkeypatch.setattr(eng, "_run", fake_run)
    count = eng.PulseLadspaEngine().move_streams("equalinux_eq")
    assert count == 1  # solo el stream externo; el interno del EQ se excluye
    assert calls[-1] == ["pactl", "move-sink-input", "7", "equalinux_eq"]
