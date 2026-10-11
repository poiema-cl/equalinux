# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: estado persistente del usuario (último preset, sliders, maestro y
# si el EC estaba activo), guardado en JSON en ~/.config/equalinux/.

from __future__ import annotations

import json
import os

DEFAULT_STATE_PATH = os.path.join(
    os.path.expanduser("~"), ".config", "equalinux", "state.json")
DEFAULT_PRESETS_DIR = os.path.join(
    os.path.expanduser("~"), ".config", "equalinux", "presets")

STATE_KEYS = ("preset", "bands", "master", "enabled", "maximized")
DEFAULT_BANDS = [0.0] * 15


class StateStore:
    """Lee/guarda el estado del EQ con degradación limpia ante JSON inválido."""

    def __init__(self, path: str = DEFAULT_STATE_PATH) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def load(self) -> dict:
        state = {
            "preset": "flat",
            "bands": list(DEFAULT_BANDS),
            "master": "",
            "enabled": False,
            "maximized": False,
        }
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return state
        for key in STATE_KEYS:
            if key in data:
                state[key] = data[key]
        return state

    def save(self, state: dict) -> None:
        payload = {key: state.get(key) for key in STATE_KEYS}
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
        except OSError:
            # Sin permisos o disco lleno: la app sigue; no interfiere el audio.
            pass
