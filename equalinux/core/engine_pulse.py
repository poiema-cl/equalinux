# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: motor del ecualizador sobre PulseAudio: carga module-ladspa-sink con
# mbeq_1197 y controla las 15 bandas en caliente via D-Bus privado de PulseAudio.

from __future__ import annotations

import os
import subprocess

import dbus

# --- Constantes del motor ---
EQ_SINK_NAME = "equalinux_eq"
EQ_SINK_DESC = "Equalinux"
EQ_SINK_DESCRIPTION_PROP = "device.description='%s'" % EQ_SINK_DESC
LADSPA_PLUGIN_FILE = "mbeq_1197.so"
# Bandas y límite viven en presets (una sola fuente de datos del dominio: el
# EQ de 15 bandas); este módulo los consume.
from .presets import BAND_HZ, BAND_LIMIT_DB  # noqa: E402
LADSPA_LABEL = "mbeq"
LADSPA_BYPASS_GAIN = 0.0
MODULE_LADSPA_SINK = "module-ladspa-sink"
MODULE_DBUS_PROTOCOL = "module-dbus-protocol"

# D-Bus privado de PulseAudio (peer; sin Hello, probado con libdbus/py-dbus)
PA_DBUS_SOCKET = "/run/user/1000/pulse/dbus-socket"
PA_DBUS_ADDRESS = "unix:path=%s" % PA_DBUS_SOCKET
DBUS_SINK_PATH_FMT = "/org/pulseaudio/core1/sink%d"
DBUS_IFACE_LADSPA = "org.PulseAudio.Ext.Ladspa1"
DBUS_PROP_ALGORITHM = "AlgorithmParameters"
DBUS_IFACE_PROPS = "org.freedesktop.DBus.Properties"
# Semántica verificada del par (adab) en la propiedad: flags True anulan el
# valor asociado; con flags False los 15 dobles se aplican tal cual.
DBUS_FLAGS_ALL_FALSE = False

# Líneas de la salida de `pactl list sinks` (adaptadas a salida en es/en).
PACTL_SINK_INDEX_PREFIXES = ("Destino #", "Sink #")
PACTL_KEY_NAME = "name"
PACTL_FIELD_MAP = {
    "nombre": "name", "name:": "name",
    "descripción": "description", "description": "description",
    "estado": "state", "state": "state",
    "controlador": "driver", "driver": "driver",
}


class EngineError(RuntimeError):
    """Error del motor listo para ser mostrado al usuario."""


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise EngineError(details_cmd(args[0], detail))
    return proc.stdout


def details_cmd(cmd: str, detail: str) -> str:
    if detail:
        return "%s falló: %s" % (cmd, detail)
    return "%s falló sin salida de error." % cmd


def _list_sinks() -> list[dict]:
    """Lista de sinks de PulseAudio con índice interno, nombre y descripción."""
    out = _run(["pactl", "list", "sinks"])
    sinks: list[dict] = []
    cur: dict = {}
    for raw in out.splitlines():
        line = raw.strip()
        if any(pfx in line for pfx in PACTL_SINK_INDEX_PREFIXES):
            if cur.get("index") is not None:
                sinks.append(cur)
            cur = {"index": int(line.rstrip().split("#")[-1])}
        elif not cur:
            continue
        else:
            if line.startswith("Nombre:") or ":" in line:
                key_raw, _, val = line.partition(":")
            else:
                continue
            translated = PACTL_FIELD_MAP.get(key_raw.strip().lower())
            if translated:
                cur[translated] = val.strip()
    if cur.get("index") is not None:
        sinks.append(cur)
    return sinks


class PulseLadspaEngine:
    """Motor: sink de EC (module-ladspa-sink + mbeq) y control por D-Bus."""

    def __init__(self) -> None:
        self._props = None
        self._props_owner = None

    # --- infraestructura D-Bus ---

    def _dbus_conn(self):
        if not os.path.exists(PA_DBUS_SOCKET):
            try:
                _run(["pactl", "load-module", MODULE_DBUS_PROTOCOL])
            except EngineError:
                pass
        if not os.path.exists(PA_DBUS_SOCKET):
            raise EngineError(
                "El socket D-Bus %s no existe: carga %s."
                % (PA_DBUS_SOCKET, MODULE_DBUS_PROTOCOL)
            )
        try:
            return dbus.connection.Connection(PA_DBUS_ADDRESS)
        except Exception as exc:
            raise EngineError(
                "No se pudo conectar al D-Bus de PulseAudio: %s" % exc
            ) from exc

    def _find_eq_sink(self) -> dict | None:
        for s in _list_sinks():
            if s.get("name") == EQ_SINK_NAME:
                return s
        return None

    def _sink_props(self):
        s = self._find_eq_sink()
        if not s:
            raise EngineError("El sink del ecualizador no está cargado.")
        if self._props is None or self._props_owner != s["index"]:
            path = DBUS_SINK_PATH_FMT % s["index"]
            obj = self._dbus_conn().get_object("org.PulseAudio.Core1", path)
            self._props = dbus.Interface(obj, DBUS_IFACE_PROPS)
            self._props_owner = s["index"]
        return self._props

    def _invalidate_props(self) -> None:
        self._props = None
        self._props_owner = None

    # --- ciclo de vida del sink de EC ---

    def ensure_loaded(self, master: str) -> str:
        """Garantiza el sink EQ y devuelve su nombre. Si la configuración difiere
        del maestro pedido, lo recarga."""
        s = self._find_eq_sink()
        if s is None or self._loaded_master_name() != master:
            if s is not None:
                self.unload()
            self._load(master)
        return EQ_SINK_NAME

    def _load(self, master: str) -> None:
        flat = ",".join(str(LADSPA_BYPASS_GAIN) for _ in BAND_HZ)
        args = [
            "pactl", "load-module", MODULE_LADSPA_SINK,
            "sink_name=%s" % EQ_SINK_NAME,
            "sink_properties=%s" % EQ_SINK_DESCRIPTION_PROP,
            "sink_master=%s" % master,
            "plugin=%s" % LADSPA_PLUGIN_FILE,
            "label=%s" % LADSPA_LABEL,
            "control=%s" % flat,
        ]
        try:
            _run(args)
        except EngineError as exc:
            raise EngineError(
                "No se pudo crear el sink del equalizador: %s. Revisá que "
                "swh-plugins esté instalado (mbeq_1197.so) y que el sink "
                "maestro '%s' exista." % (exc, master)
            ) from exc
        self._invalidate_props()

    def _loaded_master_name(self) -> str | None:
        """Maestro del sink EQ leído de los argumentos de su módulo (fuente
        fiel: `pactl list short modules` incluye sink_master=<maestro>)."""
        module = self._find_eq_module()
        if not module:
            return None
        for token in module.get("args", "").split():
            if token.startswith("sink_master="):
                return token.split("=", 1)[1]
        return None

    def _find_eq_module(self) -> dict | None:
        """Línea del módulo del EQ: {'index': str, 'name': str, 'args': str}."""
        out = _run(["pactl", "list", "short", "modules"])
        for line in out.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3 and cols[0].isdigit() \
                    and MODULE_LADSPA_SINK in line and EQ_SINK_NAME in line:
                return {"index": cols[0], "name": cols[1], "args": cols[2]}
        return None

    def is_loaded(self) -> bool:
        return self._find_eq_sink() is not None

    def unload(self) -> None:
        module = self._find_eq_module()
        if module:
            try:
                _run(["pactl", "unload-module", module["index"]])
            except EngineError:
                pass
        self._invalidate_props()

    def get_master(self) -> str | None:
        return self._loaded_master_name()

    def list_masters(self) -> list[str]:
        """Sinks reales utilizables como maestro (sin los sinks virtuales de
        EQ, reconocidos por driver module-ladspa-sink.c)."""
        return [
            s["name"] for s in _list_sinks()
            if s.get("name") and s["name"] != EQ_SINK_NAME
            and not (s.get("driver", "") or "").startswith("module-ladspa-sink")
        ]

    # --- bandas ---

    def get_bands(self) -> list[float]:
        v = self._sink_props().Get(DBUS_IFACE_LADSPA, DBUS_PROP_ALGORITHM)
        return [float(x) for x in list(v[0])]

    def set_bands(self, values: list[float]) -> None:
        if len(values) != len(BAND_HZ):
            raise EngineError(
                "El EC requiere %d bandas; se recibieron %d."
                % (len(BAND_HZ), len(values))
            )
        payload = _algorithm_payload(values)
        try:
            self._sink_props().Set(
                DBUS_IFACE_LADSPA, DBUS_PROP_ALGORITHM, payload)
        except EngineError:
            raise
        except Exception as exc:
            # El índice del sink pudo cambiar: reintento con propiedades nuevas.
            self._invalidate_props()
            try:
                self._sink_props().Set(
                    DBUS_IFACE_LADSPA, DBUS_PROP_ALGORITHM, payload)
            except Exception:
                raise EngineError(
                    "No se pudo aplicar el EC: %s" % exc
                ) from exc

    # --- enrutado por defecto ---

    def get_default_sink(self) -> str:
        return _run(["pactl", "get-default-sink"]).strip()

    def set_default_sink(self, name: str) -> None:
        _run(["pactl", "set-default-sink", name])

    def is_active(self) -> bool:
        return self.get_default_sink() == EQ_SINK_NAME

    def move_streams(self, target_name: str) -> int:
        """Mueve los streams ya sonando hacia el sink indicado (el EC o el
        maestro). Los inputs internos del propio EQ se excluyen. Devuelve
        cuántos se movieron; los fallos individuales se degraden en silencio."""
        count = 0
        try:
            out = _run(["pactl", "list", "short", "sink-inputs"])
        except EngineError:
            return 0
        eq_input_driver = "module-ladspa-sink.c"
        for line in out.splitlines():
            cols = line.split("\t")
            if len(cols) < 4 or not cols[0].isdigit():
                continue
            if cols[3] == eq_input_driver:
                continue  # loop interno del propio EQ
            try:
                _run(["pactl", "move-sink-input", cols[0], target_name])
                count += 1
            except EngineError:
                pass
        return count

    def route_streams_to_eq(self) -> int:
        return self.move_streams(EQ_SINK_NAME)

    def route_streams_back_to_master(self) -> int:
        master = self._loaded_master_name() or ""
        if not master:
            return 0
        return self.move_streams(master)

    def state(self) -> dict:
        """Foto del estado leíble: nombre, cargado, activo, maestro y bandas."""
        loaded = self._find_eq_sink() is not None
        return {
            "loaded": loaded,
            "active": self.is_active(),
            "master": self.get_master(),
            "bands": self.get_bands() if loaded else list(),
        }


def _algorithm_payload(values: list[float]):
    from dbus.types import Array, Boolean, Double, Struct
    return Struct(
        (
            Array([Double(v) for v in values], signature="d"),
            Array([Boolean(DBUS_FLAGS_ALL_FALSE)] * len(BAND_HZ), signature="b"),
        ),
        signature="(adab)",
    )


