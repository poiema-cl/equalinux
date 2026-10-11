# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-11
# Por qué: tests del empaquetado: .desktop, icono, lanzador, build y licencia.

import os
import stat
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from equalinux import __version__  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")
DESKTOP = os.path.join(RAIZ, "data", "com.poiema.Equalinux.desktop")
LANZADOR = os.path.join(RAIZ, "bin", "equalinux")
BUILD = os.path.join(RAIZ, "scripts", "build_deb.sh")
LICENCIA = os.path.join(RAIZ, "LICENSE")
ICONO = os.path.join(RAIZ, "data", "icons", "equalinux.svg")
MAN = os.path.join(RAIZ, "man", "equalinux.1")


def _lineas(ruta):
    with open(ruta, "r", encoding="utf-8") as fh:
        return fh.read().splitlines()


def test_version_semantica():
    partes = __version__.split(".")
    assert len(partes) == 3 and all(p.isdigit() for p in partes)


def test_desktop_campos_clave():
    assert os.path.exists(DESKTOP)
    claves = {}
    for ln in _lineas(DESKTOP):
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            claves[k.strip()] = v.strip()
    assert claves["Type"] == "Application"
    assert claves["Name"] == "Equalinux"
    assert claves["Exec"] == "equalinux"
    assert "Audio" in claves["Categories"]
    # Regla E11: el .desktop debe llamarse como el application-id
    assert os.path.basename(DESKTOP) == claves.get(
        "StartupWMClass", "") + ".desktop"


def test_lanzador_ejecutable():
    assert os.path.exists(LANZADOR)
    modo = os.stat(LANZADOR).st_mode
    assert modo & stat.S_IXUSR
    contenido = open(LANZADOR).read()
    assert "python3 -m equalinux.main" in contenido


def test_build_deb_ejecutable_y_sano():
    assert os.path.exists(BUILD)
    modo = os.stat(BUILD).st_mode
    assert modo & stat.S_IXUSR
    contenido = open(BUILD).read()
    assert "fakeroot" in contenido
    assert "dpkg-deb --build" in contenido


def test_licencia_gpl3():
    assert os.path.exists(LICENCIA)
    contenido = open(LICENCIA).read()
    assert "GNU GENERAL PUBLIC LICENSE" in contenido
    assert "Version 3" in contenido


def test_icono_y_manual_existen():
    assert os.path.exists(ICONO)
    assert os.path.exists(MAN)
    svg = open(ICONO).read()
    assert svg.startswith("<?xml") or svg.startswith("<svg")
