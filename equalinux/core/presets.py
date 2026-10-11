# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: presets generales para las 15 bandas del ecualizador (en dB),
# fuente única de datos de las curvas; la UI y el almacenamiento los consumen.

from __future__ import annotations

import json
import os

BAND_HZ = (
    50, 100, 156, 220, 311, 440, 622, 880, 1250, 1750,
    2500, 3500, 5000, 10000, 20000,
)
BAND_LIMIT_DB = 20.0  # límite ± dB de cada banda (mismo rango en UI y presets)

# Presets integrados; valores alineados 1:1 con BAND_HZ (corregido por
# DeepSeek en 2026-10-10: los nombres de clave deben ir sin ':' final)
BUILTIN_PRESETS = {
    "flat":           [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "bass_boost":     [7.0, 6.0, 5.0, 3.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "bass_reduce":    [-7.0, -6.0, -4.0, -2.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "treble_boost":   [0, 0, 0, 0, 0, 0, 0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    "treble_reduce":  [0, 0, 0, 0, 0, 0, 0, 0, -1.0, -2.0, -3.0, -4.0, -6.0, -7.0, -8.0],
    "vocal_boost":    [-2.0, 0, 1.0, 3.0, 4.0, 4.0, 3.0, 4.0, 3.0, 2.0, 1.0, 0, -1.0, -2.0, -3.0],
    "podcast":        [-3.0, -1.0, 1.0, 3.0, 4.0, 4.0, 3.0, 2.0, 1.0, 0, 0, 0, 0, 0, 0],
    "pop":            [-1.0, 2.0, 4.0, 4.0, 2.0, 0, -1.0, 0, 1.0, 2.0, 3.0, 3.0, 2.0, 1.0, 0],
    "rock":           [5.0, 4.0, 3.0, 1.0, 0, -1.0, 0, 1.0, 3.0, 4.0, 4.0, 3.0, 2.0, 2.0, 1.0],
    "jazz":           [4.0, 3.0, 2.0, 1.0, 0, 1.0, 2.0, 2.0, 1.0, 0, 1.0, 2.0, 3.0, 3.0, 2.0],
    "classical":      [5.0, 4.0, 3.0, 2.0, 0, 0, 0, 0, 0, 0, 1.0, 2.0, 3.0, 4.0, 5.0],
    "electronic":     [6.0, 5.0, 3.0, 0, -2.0, 0, 1.0, 2.0, 3.0, 3.0, 4.0, 5.0, 5.0, 4.0, 3.0],
    "hiphop":         [8.0, 7.0, 5.0, 3.0, 1.0, 0, -1.0, 0, 1.0, 2.0, 3.0, 3.0, 2.0, 2.0, 1.0],
    "latin":          [6.0, 5.0, 3.0, 1.0, 0, 0, 1.0, 2.0, 2.0, 1.0, 2.0, 3.0, 4.0, 3.0, 2.0],
    "dance":          [7.0, 6.0, 4.0, 2.0, 0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0, 5.0, 5.0, 4.0],
    "reggae":         [5.0, 4.0, 3.0, 1.0, -1.0, -2.0, 0, 1.0, 3.0, 3.0, 2.0, 1.0, 2.0, 3.0, 3.0],
    "acoustic":       [4.0, 3.0, 2.0, 2.0, 1.0, 1.0, 2.0, 2.0, 3.0, 2.0, 2.0, 1.0, 0, -1.0, -2.0],
    "soft":           [3.0, 2.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 1.0, 2.0, 3.0, 4.0],
    "loudness":       [8.0, 7.0, 5.0, 2.0, 0, 0, 0, 0, 0, 2.0, 5.0, 7.0, 8.0, 8.0, 7.0],
    "night_mode":     [-2.0, -1.0, 0, 1.0, 2.0, 2.0, 1.0, 0, -1.0, -2.0, -3.0, -4.0, -5.0, -6.0, -7.0],
    "cinema":         [7.0, 6.0, 4.0, 2.0, 1.0, 1.0, 0, 1.0, 2.0, 2.0, 1.0, 2.0, 4.0, 5.0, 6.0],
    "gaming":         [5.0, 4.0, 3.0, 1.0, 0, 0, 2.0, 4.0, 3.0, 2.0, 1.0, 2.0, 3.0, 4.0, 4.0],
    "speech":         [-5.0, -3.0, 0, 2.0, 3.0, 4.0, 4.0, 3.0, 2.0, 1.0, -1.0, -3.0, -4.0, -5.0, -6.0],
    "small_speakers": [6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 7.0],
}


def validate_values(values) -> list[float]:
    """Comprueba longitud y rango; devuelve la lista normalizada."""
    if len(values) != len(BAND_HZ):
        raise ValueError(
            "El preajuste debe tener %d valores; tiene %d."
            % (len(BAND_HZ), len(values))
        )
    out = [float(v) for v in values]
    for v in out:
        if not -BAND_LIMIT_DB <= v <= BAND_LIMIT_DB:
            raise ValueError(
                "El valor %+.1f dB sale del rango ±%.0f dB." % (v, BAND_LIMIT_DB)
            )
    return out


class PresetStore:
    """Fuente única de presets: integrados + personales (JSON del usuario)."""

    def __init__(self, user_dir: str) -> None:
        self.user_dir = user_dir
        os.makedirs(user_dir, exist_ok=True)
        self._user_presets = self._read_user_presets()

    # --- lecturas ---

    def _preset_path(self, name: str) -> str:
        safe = "".join(c for c in name if c not in "\\/:*?\"<>|").strip()
        return os.path.join(self.user_dir, "%s.json" % safe)

    def _read_user_presets(self) -> dict:
        found = {}
        try:
            names = sorted(os.listdir(self.user_dir))
        except OSError:
            return found
        for fname in names:
            if not fname.endswith(".json"):
                continue
            data = self._read_file(os.path.join(self.user_dir, fname))
            if data is not None:
                found[fname[:-5]] = data
        return found

    def _read_file(self, path: str):
        """Lee un preset tolerando fichero corrupto (degradación limpia)."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return validate_values(json.load(fh))
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def builtin_names(self) -> list[str]:
        return list(BUILTIN_PRESETS.keys())

    def user_names(self) -> list[str]:
        return sorted(self._user_presets.keys())

    def get(self, name: str) -> list[float] | None:
        if name in BUILTIN_PRESETS:
            return validate_values(BUILTIN_PRESETS[name])
        if name in self._user_presets:
            return list(self._user_presets[name])
        return None

    # --- escritura ---

    def save_user(self, name: str, values) -> str:
        vals = validate_values(values)
        path = self._preset_path(name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(vals, fh, ensure_ascii=False)
        self._user_presets[name] = vals
        return path

    def delete_user(self, name: str) -> bool:
        path = self._preset_path(name)
        if name in self._user_presets and os.path.exists(path):
            os.remove(path)
        return self._user_presets.pop(name, None) is not None
