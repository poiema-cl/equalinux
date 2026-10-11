#!/bin/sh
# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-11
# Por qué: arma el instalable .deb de Equalinux (edición A: motor del sistema)
# sin herramientas raras: estructura + dpkg-deb. Uso: scripts/build_deb.sh
# Licencia: GPL-3.0 (igual que el proyecto).
set -e

RAIZ=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$RAIZ"

# Versión desde la única fuente del dato (equalinux/__init__.py)
VERSION=$(python3 -c 'from equalinux import __version__ as v; print(v)')
if [ -z "$VERSION" ]; then
    echo "ERROR: no pude leer la versión de equalinux/__init__.py" >&2
    exit 1
fi

PAQUETE=equalinux
DESTINO=build/deb/$PAQUETE
SALIDA=dist
LIMPIO=0
MANTENEDOR="angelutreradev <angelutrera1988@outlook.cl>"

rm -rf "$DESTINO"
mkdir -p "$DESTINO/DEBIAN" \
         "$DESTINO/usr/lib/equalinux" \
         "$DESTINO/usr/bin" \
         "$DESTINO/usr/share/applications" \
         "$DESTINO/usr/share/icons/hicolor/48x48/apps" \
         "$DESTINO/usr/share/icons/hicolor/128x128/apps" \
         "$DESTINO/usr/share/icons/hicolor/scalable/apps"

# --- control del paquete ---
cat > "$DESTINO/DEBIAN/control" <<EOF
Package: $PAQUETE
Version: $VERSION
Section: sound
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, python3-dbus, pulseaudio-utils, swh-plugins
Maintainer: $MANTENEDOR
Homepage: https://poiema/equalinux
Description: Ecualizador gráfico de 15 bandas para todo el audio del sistema
 Ecualizador de sistema sobre PulseAudio: crea una salida virtual con el
 plugin LADSPA mbeq y controla las 15 bandas en caliente por D-Bus.
 Incluye 24 preajustes (Rock, Pop, Jazz, Podcast, Nocturno, Cine, ...) y
 preajustes personales del usuario. Interfaz GTK4.
EOF

# --- postinst: refrescar menú e iconos si las herramientas existen ---
cat > "$DESTINO/DEBIAN/postinst" <<'EOF'
#!/bin/sh
# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-11
# Por qué: refrescar cachés de menú e iconos tras instalar Equalinux.
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "$DESTINO/DEBIAN/postinst"

# --- contenido de la app ---
cp -r equalinux "$DESTINO/usr/lib/equalinux/equalinux"
cp -r data "$DESTINO/usr/lib/equalinux/data"
rm -rf "$DESTINO/usr/lib/equalinux/equalinux/__pycache__" \
       "$DESTINO/usr/lib/equalinux/equalinux"/*/__pycache__
install -m 755 bin/equalinux "$DESTINO/usr/bin/equalinux"
install -m 644 data/equalinux.desktop "$DESTINO/usr/share/applications/equalinux.desktop"
install -m 644 data/icons/equalinux-48.png   "$DESTINO/usr/share/icons/hicolor/48x48/apps/equalinux.png"
install -m 644 data/icons/equalinux-128.png  "$DESTINO/usr/share/icons/hicolor/128x128/apps/equalinux.png"
install -m 644 data/icons/equalinux.svg     "$DESTINO/usr/share/icons/hicolor/scalable/apps/equalinux.svg"

# --- documentos estándar de Debian ---
mkdir -p "$DESTINO/usr/share/doc/equalinux"
cat > "$DESTINO/usr/share/doc/equalinux/copyright" <<'COPY'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Equalinux
Source: <URL del repositorio al publicar>

Files: *
Copyright: 2026 angelutreradev
License: GPL-3+
 This program is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or
 (at your option) any later version.
 .
 On Debian systems, the complete text of the GNU General Public
 License version 3 can be found in "/usr/share/common-licenses/GPL-3".
COPY
gzip -9 -n -c README.md > "$DESTINO/usr/share/doc/equalinux/README.md.gz"
if [ -f debian/changelog ]; then
    gzip -9 -n -c debian/changelog > "$DESTINO/usr/share/doc/equalinux/changelog.gz"
fi

# permisos del contenido (sin +x en .py: lintian executable-not-elf-or-script)
find "$DESTINO/usr" -type d -exec chmod 755 {} +
find "$DESTINO/usr" -type f -exec chmod 644 {} +
chmod 755 "$DESTINO/usr/bin/equalinux"

# página de manual
mkdir -p "$DESTINO/usr/share/man/man1"
if [ -f man/equalinux.1 ]; then
    install -m 644 man/equalinux.1 "$DESTINO/usr/share/man/man1/equalinux.1"
    gzip -9 -n "$DESTINO/usr/share/man/man1/equalinux.1"
fi
# permisos finales (incluye directorios recién creados, p.ej. man1/)
find "$DESTINO/usr" -type d -exec chmod 755 {} +

# Debian exige dueño root/root: usamos fakeroot (sin sudo)
FAKEROOT=$(command -v fakeroot || true)
[ -n "$FAKEROOT" ] || { echo "ERROR: falta fakeroot (apt install fakeroot)" >&2; exit 1; }

mkdir -p "$SALIDA"
NOMBRE="$SALIDA/${PAQUETE}_${VERSION}-1_all.deb"
"$FAKEROOT" dpkg-deb --build "$DESTINO" "$NOMBRE"

echo
echo "OK: $NOMBRE"
echo "Verificá con: dpkg-deb --contents $NOMBRE"
