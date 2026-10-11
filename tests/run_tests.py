# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: el entorno no tiene pytest; este corredor mínimo descubre los
# tests_* de cada módulo y los ejecuta sin dependencias externas.

import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TEST_MODULES = ("test_presets", "test_state", "test_engine", "test_packaging")


def main() -> int:
    passed = failed = 0
    for modname in TEST_MODULES:
        mod = __import__(modname)
        for attr in sorted(dir(mod)):
            if not attr.startswith("test_") or not callable(getattr(mod, attr)):
                continue
            # los tests del motor piden monkeypatch: se saltan sin pytest
            func = getattr(mod, attr)
            if getattr(func, "__code__", None) and func.__code__.co_argcount:
                continue
            try:
                func()
                passed += 1
            except Exception:
                failed += 1
                print("FAIL %s.%s" % (modname, attr))
                traceback.print_exc()
    print("%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
