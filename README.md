# Equalinux

Ecualizador gráfico de **todo el audio del sistema** para Linux (probado en
Linux Mint 21.3 con PulseAudio 15.99 + plugins LADSPA de SWH).

![ventana](docs/equalinux_window.png)

## Qué hace

- 15 bandas de 50 Hz a 20 kHz con sliders de ±20 dB y curva dibujada en vivo.
- 24 preajustes generales: flat, bass_boost, rock, jazz, clásica, electrónica,
  hip-hop, podcast, nocturno, cine, gaming, etc., y los tuyos personales.
- Un interruptor para activar el EC en todo el sistema: crea una salida virtual
  `equalinux_eq` a partir de la salida real que elijas (el maestro), la marca
  como salida por defecto **y mueve a ella el audio que ya estaba sonando**.
- Guarda tu último estado (preset, sliders, maestro, activado, maximizado) y lo
  recupera al abrir de nuevo.
- Cambios de sliders y preajustes **en caliente** (sin recargar ni cortar el
  audio) a través de la interfaz D-Bus de PulseAudio.
- F11 maximiza/restaura la ventana y se recuerda.

## Instalación

### Opción A: instalable `.deb` (Debian, Ubuntu, Mint)

```bash
# desde el .deb publicado:
sudo apt install ./equalinux_0.1.0-1_all.deb

# o constrúyelo vos mismo (necesita fakeroot y lintian para verificar):
scripts/build_deb.sh
sudo apt install ./dist/equalinux_0.1.0-1_all.deb
```

Una vez instalado: `equalinux` en la terminal o "Equalinux" en el menú de
aplicaciones. Las dependencias (`python3-gi`, `gir1.2-gtk-4.0`,
`python3-dbus`, `pulseaudio-utils`, `swh-plugins`) se instalan solas.

### Opción B: correr sin instalar (modo desarrollo)

```bash
./bin/equalinux            # o:
python3 -m equalinux.main
```

## Requisitos

- Linux con **PulseAudio** activo (no PipeWire a secas: ver "Motor" abajo).
- `swh-plugins` (plugin LADSPA `mbeq_1197.so`), `python3-gi`, GTK4,
  `python3-dbus`, `pulseaudio-utils`.

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 python3-dbus \
                 pulseaudio-utils swh-plugins
```

Si el módulo D-Bus de PulseAudio no está cargado, la aplicación intenta
cargarlo con `pactl load-module module-dbus-protocol`.

## Motor, en una frase

`pactl load-module module-ladspa-sink sink_name=equalinux_eq sink_master=<maestro>
plugin=mbeq_1197.so label=mbeq control=0,...` crea una salida con EQ de 15
bandas; la ventana cambia los valores de banda en caliente escribiendo la
propiedad D-Bus `AlgorithmParameters` (interfaz `org.PulseAudio.Ext.Ladspa1`)
del objeto `/org/pulseaudio/core1/sink<Índice>` del bus privado de PulseAudio,
y re-rutea los streams ya sonando al activar o desactivar.

## Notas y límites conocidos

- El sink maestro se decide al cargar el EC; cambiar de salida física mientras
  el EC está activo debe hacerse desde la ventana (selector de maestro).
- Si PulseAudio reinicia, la salida EQ desaparece: al reabrir la aplicación se
  recrea con el estado guardado.
- Los valores van de -20 a +20 dB por banda y se guardan como JSON en
  `~/.config/equalinux/state.json` y `~/.config/equalinux/presets/`.
- El paquete instala la **edición A** (motor del sistema). La edición B
  (motor propio, para Flatpak/Snap) todavía no existe: ver "Ediciones".

## Ediciones (futuras)

- **Edición A (actual):** motor del sistema (LADSPA en PulseAudio). Va en
  `.deb`, PPA y GitHub Releases. Sin latencia extra.
- **Edición B (pendiente):** motor propio dentro de la app (salida virtual +
  filtros internos) para Flatpak y Snap, donde el sandbox no deja usar el
  plugin del sistema. Agregaría unos pocos ms de latencia.

## Estructura del repositorio

```
equalinux/          # app Python (GTK4): core (motor, presets, estado) + ui
data/               # CSS de la identidad visual, .desktop e iconos
bin/equalinux       # lanzador (instalado y de desarrollo)
scripts/build_deb.sh# construye dist/equalinux_<versión>-1_all.deb
debian/changelog    # changelog Debian (va dentro del .deb)
man/equalinux.1     # página de manual
tests/              # tests: run_tests.py (sin pytest) y test_*.py
docs/               # capturas y anexos
dist/, build/       # artefactos generados (no se versionan)
```

## Verificación del proyecto

```bash
python3 tests/run_tests.py            # 15 tests
lintian dist/equalinux_*.deb          # solo queda pendiente el correo real
```

## Licencia

GPL-3.0 (ver `LICENSE`): cualquiera puede usar, modificar y redistribuir,
pero las versiones derivadas siguen abiertas y con crédito.
