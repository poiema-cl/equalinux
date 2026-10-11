# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: punto de entrada del app: solo orquesta; la lógica vive en core/.

import sys

from gi.repository import GLib

from .ui.window import EqualinuxApp

APP_ID = "com.poiema.Equalinux"  # el .desktop MUST llamarse igual (Regla E11)


def main() -> int:
    # Sin esto GTK declara WM_CLASS="main.py" y el panel de Cinnamon no
    # encuentra el icono ni el nombre en la barra de tareas.
    GLib.set_prgname(APP_ID)
    GLib.set_application_name("Equalinux")
    app = EqualinuxApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
