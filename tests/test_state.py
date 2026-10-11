# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: tests de la persistencia de estado (JSON) con degradación limpia.

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from equalinux.core.state import StateStore  # noqa: E402


def test_load_default_when_missing():
    with tempfile.TemporaryDirectory() as td:
        store = StateStore(os.path.join(td, "state.json"))
        state = store.load()
        assert state["enabled"] is False
        assert state["bands"] == [0.0] * 15
        assert state["preset"] == "flat"


def test_save_load_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "state.json")
        store = StateStore(path)
        state = {"preset": "rock", "bands": [1.0] * 15,
                 "master": "alsa_out", "enabled": True}
        store.save(state)
        loaded = StateStore(path).load()
        assert loaded["preset"] == "rock"
        assert loaded["enabled"] is True
        assert loaded["bands"] == [1.0] * 15


def test_load_corrupt_returns_defaults():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "state.json")
        with open(path, "w") as fh:
            fh.write("{broken")
        loaded = StateStore(path).load()
        assert loaded["preset"] == "flat"  # degradación limpia
        assert len(loaded["bands"]) == 15
