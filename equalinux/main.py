# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: punto de entrada del app: solo orquesta; la lógica vive en core/.

import sys

from .ui.window import EqualinuxApp


def main() -> int:
    app = EqualinuxApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
