# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: tests de presets y del estado (sin tocar el audio real).

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from equalinux.core.presets import (  # noqa: E402
    BAND_HZ, BUILTIN_PRESETS, PresetStore, validate_values)


def test_builtin_presets_shape():
    for name, values in BUILTIN_PRESETS.items():
        assert len(values) == len(BAND_HZ), name
        for v in values:
            assert -20.0 <= float(v) <= 20.0, name


def test_flat_is_all_zero():
    assert all(v == 0 for v in BUILTIN_PRESETS["flat"])


def test_validate_rejects_bad_length():
    try:
        validate_values([0] * 3)
    except ValueError:
        return
    raise AssertionError("debería rechazar listas incompletas")


def test_preset_store_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        store = PresetStore(os.path.join(td, "presets"))
        names_before = set(store.user_names())
        path = store.save_user("mi_preset", [1.0] * 15)
        assert os.path.exists(path)
        assert "mi_preset" in store.user_names()
        assert store.get("mi_preset") == [1.0] * 15
        assert store.builtin_names() != names_before
        assert store.delete_user("mi_preset")
        assert store.get("mi_preset") is None
        assert "mi_preset" not in store.user_names()


def test_preset_store_corrupt_file_degrades():
    with tempfile.TemporaryDirectory() as td:
        pdir = os.path.join(td, "presets")
        os.makedirs(pdir)
        with open(os.path.join(pdir, "roto.json"), "w") as fh:
            fh.write("{not-json")
        store = PresetStore(pdir)
        assert store.get("roto") is None  # degradación limpia, no rompe
