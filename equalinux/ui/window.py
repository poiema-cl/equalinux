# Autor: DeepSeek (model GLM, harness DSH) - 2026-10-10
# Por qué: ventana GTK4 en modo "estudio": encabezado con estado visible,
# 15 sliders verticales como un EQ real, tarjetas de preajuste con mini-curva
# drawn en Cairo y pie con acción de reset (Regla E7: intuitiva a la primera).

from __future__ import annotations

import os

import cairo  # noqa: F401  (backend de dibujo GTK4)
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from ..core import engine_pulse  # noqa: E402
from ..core.engine_pulse import EngineError  # noqa: E402
from ..core.presets import (  # noqa: E402
    BAND_HZ, BAND_LIMIT_DB, PresetStore)
from ..core.state import (  # noqa: E402
    DEFAULT_PRESETS_DIR, DEFAULT_STATE_PATH, StateStore)

# --- Constantes de interfaz ---
APP_TITLE = "Equalinux"
APP_ID = "com.poiema.Equalinux"
SLIDER_STEP_DB = 1.0
SLIDER_DIGITS = 0
UI_SPACING = 6
UI_MARGIN = 16
CARD_MIN = 84  # px por tarjeta compacta (ancho mínimo)
CURVE_HEIGHT = 96  # alto del panel de curva del EQ
EQ_PANEL_MIN = 470  # ancho mínimo de la columna de eq a la izquierda
MINI_CURVE_H = 26  # alto de las mini-curvas de las tarjetas de preajuste
MASTER_COMBO_WIDTH = 320  # límite el mínimo de la ventana (nombres largos)
CHIPS_PER_ROW = 5
BAND_LABELS = (
    "50", "100", "156", "220", "311", "440", "622", "880", "1k25", "1k75",
    "2k5", "3k5", "5k", "10k", "20k",
)
CSS_ASSETS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "equalinux.css")
ACCENT = "#3AD79E"


class EqualinuxApp(Gtk.Application):
    """Aplicación GTK4 que controla el ecualizador del sistema."""

    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self.connect("activate", self._on_activate)
        self.engine = engine_pulse.PulseLadspaEngine()
        self._state_store = StateStore(DEFAULT_STATE_PATH)
        self.state = self._state_store.load()
        self.presets = PresetStore(DEFAULT_PRESETS_DIR)
        self._scales: list[Gtk.Scale] = []
        self._db_labels: list[Gtk.Label] = []
        self._selected: str = self.state.get("preset") or "flat"
        self._silent_ui = False  # evita bucles UI -> engine en cambios espejo
        self._cards: dict[str, Gtk.Button] = {}

    # --- ciclo de vida ---

    def _on_activate(self, *args) -> None:
        self._load_css()
        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_title(APP_TITLE)
        self.win.set_default_size(700, 780)
        self.win.set_resizable(True)
        self.win.set_child(self._build_ui())
        # Maximizar con F11 (también por si el capirote del SO no lo permite).
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.win.add_controller(key_ctrl)
        if self.state.get("maximized"):
            self.win.maximize()
        self.win.present()
        GLib.idle_add(self._bootstrap_engine)

    def _on_key_pressed(self, ctrl, keyval, keycode, state) -> bool:
        if keyval == Gdk.KEY_F11:
            if self.win.is_maximized():
                self.win.unmaximize()
                self.state["maximized"] = False
            else:
                self.win.maximize()
                self.state["maximized"] = True
            self._state_store.save(self.state)
            return True
        return False

    def _load_css(self) -> None:
        css = Gtk.CssProvider()
        css.load_from_path(CSS_ASSETS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # --- construcción de UI ---

    def _build_ui(self) -> Gtk.Box:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                       spacing=UI_SPACING)
        root.set_margin_top(UI_MARGIN)
        root.set_margin_bottom(UI_MARGIN)
        root.set_margin_start(UI_MARGIN)
        root.set_margin_end(UI_MARGIN)
        for builder in (self._build_header, self._build_tip,
                        self._build_banner):
            root.append(builder())
        # Cuerpo en 2 columnas: EQ (curva + sliders) | preajustes compactos
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=16)
        body.set_vexpand(True)
        left_eq = self._build_eq_panel()
        left_eq.set_hexpand(True)  # mitad y mitad del espacio libre
        right_presets = self._build_preset_area()
        right_presets.set_hexpand(True)
        body.append(left_eq)
        body.append(right_presets)
        root.append(body)
        root.append(self._build_footer())
        return root

    def _build_header(self) -> Gtk.Box:
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=UI_SPACING)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label()
        title.set_markup('<span size="25000" fgcolor="#E9EDF2">'
                         "<b>Equalinux</b></span>")
        title.set_halign(Gtk.Align.START)
        left.append(title)
        subtitle = Gtk.Label(label="ecualizador del sistema · 15 bandas")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("eq-subtitle")
        left.append(subtitle)
        head.append(left)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                        spacing=UI_SPACING)
        right.set_halign(Gtk.Align.END)
        self._status_pill = Gtk.Label(label="OFF")
        self._status_pill.set_css_classes(["status-pill", "off"])
        self._status_pill.set_halign(Gtk.Align.END)
        right.append(self._status_pill)

        master_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                             spacing=UI_SPACING)
        master_label = Gtk.Label(label="Salida")
        master_label.add_css_class("eq-help")
        master_row.append(master_label)
        self.master_combo = Gtk.ComboBoxText()
        self.master_combo.set_size_request(MASTER_COMBO_WIDTH, -1)
        self._combo_id = self.master_combo.connect(
            "changed", self._on_master_changed)
        master_row.append(self.master_combo)
        right.append(master_row)

        self.switch = Gtk.Switch()
        self._switch_id = self.switch.connect("state-set", self._on_switch)
        self.switch.add_css_class("eq-switch")
        self.switch.set_halign(Gtk.Align.END)
        right.append(self.switch)
        head.append(right)
        return head

    def _build_tip(self) -> Gtk.Label:
        tip = Gtk.Label(label=(
            "Encendé el interruptor para que TODO el audio del sistema "
            "(música, videos, navegador) pase por este EQ. "
            "Tocá un preajuste o mové los niveles a mano."))
        tip.set_wrap(True)
        tip.add_css_class("eq-help")
        tip.set_halign(Gtk.Align.START)
        return tip

    def _build_banner(self) -> Gtk.InfoBar:
        self.banner = Gtk.InfoBar()
        self.banner.set_show_close_button(True)
        self.banner.connect("response", self._on_banner_response)
        self._error_label = Gtk.Label(label="")
        self._error_label.set_wrap(True)
        self._error_label.set_halign(Gtk.Align.START)
        try:
            self.banner.add_child(self._error_label)
        except Exception:
            pass  # GTK sin add_child: el texto sale por el propio banner
        self.banner.hide()
        return self.banner

    def _on_banner_response(self, bar, response) -> None:
        bar.hide()

    def _build_eq_panel(self) -> Gtk.Box:
        """Zona del EQ: curva dibujada + 15 sliders verticales (+20 arriba)."""
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                        spacing=UI_SPACING)
        label = Gtk.Label(label="NIVEL DE BANDA (dB)")
        label.add_css_class("section-label")
        label.set_halign(Gtk.Align.START)
        panel.append(label)

        # Curva continua del EQ: se recalcula con cada cambio de slider.
        self._eq_curve = Gtk.DrawingArea()
        self._eq_curve.set_content_height(CURVE_HEIGHT)
        self._eq_curve.set_vexpand(False)
        self._eq_curve.set_hexpand(True)
        self._eq_curve.set_draw_func(self._draw_eq_curve)
        panel.append(self._eq_curve)

        eq_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=UI_SPACING)
        for index in range(len(BAND_HZ)):
            eq_box.append(self._build_band_column(index))
        panel.append(eq_box)
        return panel

    def _band_xs(self, w):
        """Centros horizontales de las 15 columnas al ancho w."""
        step = w / len(BAND_HZ)
        return [(i + 0.5) * step for i in range(len(BAND_HZ))]

    def _draw_eq_curve(self, area, cr, w, h, ud=None):
        """Curva del EQ: línea teal conectando los valores actuales por banda
        (área sombreada devajo hasta la línea 0 dB)."""
        values = self._collect_scales()
        xs = self._band_xs(w)
        ys = [h / 2 - (v / BAND_LIMIT_DB) * (h / 2 - 6)
              for v in values]

        def stroke():
            for i, (x, y) in enumerate(zip(xs, ys)):
                if i == 0:
                    # inicio horizontal suavizado hacia el primer punto
                    cr.move_to(x, h / 2)
                    cr.curve_to((xs[0]) / 2, h / 2, x - 12, y, x, y)
                else:
                    px, py = xs[i - 1], ys[i - 1]
                    mx = (px + x) / 2
                    cr.curve_to(mx, py, mx, y, x, y)

        # área sombreada (curva -> baseline) para lectura rápida del peso
        stroke()
        cr.line_to(xs[-1], h / 2)
        cr.line_to(xs[0], h / 2)
        cr.close_path()
        cr.set_source_rgba(0.23, 0.84, 0.62, 0.12)
        cr.fill()
        stroke()
        cr.set_source_rgba(0.23, 0.84, 0.62, 0.95)
        cr.set_line_width(2.0)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.stroke()
        # línea vertical de 0 dB
        cr.set_source_rgba(1, 1, 1, 0.18)
        cr.set_line_width(1.0)
        cr.move_to(0, h / 2)
        cr.line_to(w, h / 2)
        cr.stroke()

    def _build_band_column(self, index: int) -> Gtk.Box:
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        db = Gtk.Label(label="0 dB")
        db.add_css_class("eq-db-label")
        db.set_size_request(24, -1)
        col.append(db)
        self._db_labels.append(db)
        scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.VERTICAL,
            -BAND_LIMIT_DB, BAND_LIMIT_DB, SLIDER_STEP_DB)
        scale.set_inverted(True)  # +20 arriba, -20 abajo
        scale.set_digits(SLIDER_DIGITS)
        scale.set_vexpand(True)
        scale.set_draw_value(False)
        scale.set_value(0)
        scale.set_tooltip_text("%s Hz" % BAND_LABELS[index])
        scale.add_css_class("eq-band")
        scale.set_size_request(24, -1)  # limita el ancho mínimo de la columna
        scale.connect("value-changed", self._on_slider_changed, index)
        self._scales.append(scale)
        col.append(scale)
        hz = Gtk.Label(label=BAND_LABELS[index])
        hz.add_css_class("eq-hz-label")
        hz.set_halign(Gtk.Align.CENTER)
        col.append(hz)
        return col

    def _build_preset_area(self) -> Gtk.Box:
        area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                       spacing=UI_SPACING)
        label = Gtk.Label(label="PREAJUSTES")
        label.add_css_class("section-label")
        label.set_halign(Gtk.Align.START)
        area.append(label)

        self._chip_box = Gtk.FlowBox()
        self._chip_box.set_homogeneous(True)
        self._chip_box.set_max_children_per_line(CHIPS_PER_ROW)
        # mínimo 3 por línea: reduce el ancho mínimo de la ventana para
        # que el SO permita maximizar o achicarla (antes: 5 fijo)
        self._chip_box.set_min_children_per_line(3)
        self._chip_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._chip_box.set_hexpand(True)
        self._chip_box.set_vexpand(True)
        self._chip_box.set_valign(Gtk.Align.FILL)
        self._chip_box.set_halign(Gtk.Align.FILL)
        area.append(self._chip_box)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                      spacing=UI_SPACING)
        self.preset_entry = Gtk.Entry()
        self.preset_entry.set_placeholder_text(
            "Nombre del nuevo preajuste (se guarda con tus niveles actuales)")
        self.preset_entry.set_hexpand(True)
        row.append(self.preset_entry)
        save_btn = Gtk.Button(label="Guardar")
        save_btn.add_css_class("flat-accent")
        save_btn.connect("clicked", self._on_save_preset)
        row.append(save_btn)
        del_btn = Gtk.Button(label="Borrar personal")
        del_btn.add_css_class("flat-muted")
        del_btn.connect("clicked", self._on_delete_user_preset)
        row.append(del_btn)
        area.append(row)

        self._build_all_cards()
        return area

    def _build_all_cards(self) -> None:
        while self._chip_box.get_first_child():
            self._chip_box.remove(self._chip_box.get_first_child())
        self._cards.clear()
        names = self.presets.builtin_names() + self.presets.user_names()
        for name in names:
            self._add_card(name)
        self._reflect_selected_card()

    @staticmethod
    def _pretty_name(name: str) -> str:
        label = name.replace("_", " ").strip()
        return label[:1].upper() + label[1:]

    def _add_card(self, name: str) -> None:
        card = Gtk.Button()
        card.add_css_class("preset-card")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        mini = Gtk.DrawingArea()
        mini.set_content_height(MINI_CURVE_H)
        mini.set_content_width(CARD_MIN)
        values = self.presets.get(name) or []
        mini.set_draw_func(self._draw_mini_curve, values)
        box.append(mini)
        name_lbl = Gtk.Label(label=self._pretty_name(name))
        name_lbl.add_css_class("preset-name")
        name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        name_lbl.set_max_width_chars(12)
        name_lbl.set_halign(Gtk.Align.CENTER)
        box.append(name_lbl)
        card.set_child(box)
        card.connect("clicked", self._on_card_clicked, name)
        self._cards[name] = card
        self._chip_box.append(card)

    @staticmethod
    def _draw_mini_curve(area, cr, w, h, values):
        """Mini-curva del preset: línea teal mostrando la forma del EQ."""
        if len(values) < 2:
            return
        # normalización relativa: la forma del preset, no la magnitud absoluta
        denom = max(4.0, max(abs(float(v)) for v in values))
        cr.set_source_rgba(0.23, 0.84, 0.62, 0.95)
        cr.set_line_width(1.6)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        step = w / (len(values) - 1)
        for i, v in enumerate(values):
            y = h / 2 - (float(v) / denom) * (h / 2 - 4)
            if i == 0:
                cr.move_to(0, y)
            else:
                cr.line_to(i * step, y)
        cr.stroke()

    def _build_footer(self) -> Gtk.Box:
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                       spacing=UI_SPACING)
        self.status_label = Gtk.Label(label="")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_hexpand(True)
        self.status_label.add_css_class("eq-help")
        foot.append(self.status_label)
        reset_btn = Gtk.Button(label="Restablecer")
        reset_btn.add_css_class("flat-muted")
        reset_btn.connect("clicked", self._on_reset)
        foot.append(reset_btn)
        return foot

    # --- arranque y estado ---

    def _bootstrap_engine(self) -> bool:
        wanted = self.state.get("master") or self._default_sink()
        try:
            names = self.engine.list_masters()
            if wanted not in names:
                wanted = names[0] if names else ""
            if wanted:
                self.engine.ensure_loaded(wanted)
            if self.state.get("enabled") and wanted:
                self.engine.set_default_sink(engine_pulse.EQ_SINK_NAME)
                self.engine.route_streams_to_eq()
            self.state["master"] = self.engine.get_master() or wanted
            self._state_store.save(self.state)
        except EngineError as exc:
            self._show_error(str(exc))
        self._refresh_masters()
        self._apply_state_to_ui()
        return False

    def _refresh_masters(self) -> None:
        try:
            names = self.engine.list_masters()
        except EngineError as exc:
            self._show_error(str(exc))
            return
        self.master_combo.handler_block(self._combo_id)
        self.master_combo.remove_all()
        for name in names:
            self.master_combo.append_text(name)
        current = self._loaded_master_or_none()
        if current in names:
            self.master_combo.set_active(names.index(current))
        elif names:
            self.master_combo.set_active(0)
        self.master_combo.handler_unblock(self._combo_id)

    def _refresh_status(self) -> None:
        try:
            active = self.engine.is_active()
            loaded = self.engine.is_loaded()
        except EngineError as exc:
            self._show_error(str(exc))
            return
        if not loaded:
            self.status_label.set_text("EQ no cargado.")
            self._status_pill.set_text("OFF")
            self._status_pill.set_css_classes(["status-pill", "off"])
            return
        master = self.engine.get_master() or "-"
        if active:
            self.status_label.set_text(
                "Activo en todo el sistema (maestro: %s)." % master)
            self._status_pill.set_text("● ACTIVO")
            self._status_pill.set_css_classes(["status-pill", "on"])
        else:
            self.status_label.set_text(
                "Preparado, sin activar (maestro: %s)." % master)
            self._status_pill.set_text("OFF")
            self._status_pill.set_css_classes(["status-pill", "off"])
        self._reflect_selected_card()

    def _reflect_selected_card(self) -> None:
        for name, card in self._cards.items():
            selected = (name == self._selected)
            card.set_css_classes(["preset-card"] +
                                 (["selected"] if selected else []))

    # --- eventos ---

    def _on_switch(self, switch, enabled: bool) -> bool:
        try:
            if enabled:
                self.engine.ensure_loaded(self._wanted_master())
                self.engine.set_default_sink(engine_pulse.EQ_SINK_NAME)
                # Los streams ya sonando no siguen el sink por defecto: hay que
                # moverlos al EQ para que el audio actual SI escuche el cambio.
                self.engine.route_streams_to_eq()
                self.state["enabled"] = True
            else:
                master = self.engine.get_master() or self._wanted_master()
                if master and master != engine_pulse.EQ_SINK_NAME:
                    self.engine.set_default_sink(master)
                    self.engine.route_streams_back_to_master()
                self.state["enabled"] = False
        except EngineError as exc:
            self._show_error(str(exc))
            switch.handler_block(self._switch_id)
            switch.set_active(not enabled)
            switch.handler_unblock(self._switch_id)
            return True
        self._persist_state()
        self._refresh_status()
        return False

    def _on_master_changed(self, combo) -> None:
        chosen = combo.get_active_text()
        if not chosen or chosen == engine_pulse.EQ_SINK_NAME:
            return
        try:
            self.engine.ensure_loaded(chosen)
        except EngineError as exc:
            self._show_error(str(exc))
            return
        self.state["master"] = chosen
        self._persist_state()
        self._refresh_status()

    def _on_card_clicked(self, btn, name: str) -> None:
        values = self.presets.get(name)
        if values is None:
            self._show_error("El preajuste %s no se pudo cargar." % name)
            return
        self._set_scales(values)
        self._selected = name
        self.state["preset"] = name
        self.state["bands"] = list(values)
        self._persist_state()
        self._reflect_selected_card()
        self._apply_engine_values(values)

    def _on_save_preset(self, btn) -> None:
        name = self.preset_entry.get_text().strip()
        if not name:
            self._show_error(
                "Ponle un nombre al preajuste antes de guardarlo.")
            return
        values = self._collect_scales()
        try:
            self.presets.save_user(name, values)
        except (ValueError, OSError) as exc:
            self._show_error("No se pudo guardar: %s" % exc)
            return
        if name not in self._cards:
            self._add_card(name)
        self._selected = name
        self.state["preset"] = name
        self._persist_state()
        self._reflect_selected_card()

    def _on_delete_user_preset(self, btn) -> None:
        name = self._selected
        if name in self.presets.builtin_names():
            self._show_error("Los preajustes integrados no se borran.")
            return
        if not name:
            self._show_error("Elije un preajuste personal en la lista.")
            return
        try:
            self.presets.delete_user(name)
        except OSError as exc:
            self._show_error("No se pudo borrar: %s" % exc)
            return
        card = self._cards.pop(name, None)
        if card:
            self._chip_box.remove(card)
        self._set_preset("flat")

    def _on_reset(self, btn) -> None:
        self._set_preset("flat")

    def _on_slider_changed(self, scale, index: int) -> None:
        if self._silent_ui:
            return
        self._selected = ""
        self._db_labels[index].set_text(
            "%+.0f dB" % self._scales[index].get_value())
        self.state["bands"] = self._collect_scales()
        self._eq_curve.queue_draw()
        self._persist_state()

    # --- utilidades ---

    def _collect_scales(self) -> list[float]:
        return [scale.get_value() for scale in self._scales]

    def _set_scales(self, values: list[float]) -> None:
        self._silent_ui = True
        for scale, value in zip(self._scales, values):
            scale.set_value(value)
        self._silent_ui = False
        for lbl, value in zip(self._db_labels, values):
            lbl.set_text("%+.0f dB" % value)
        self._eq_curve.queue_draw()

    def _set_preset(self, name: str) -> None:
        values = self.presets.get(name)
        if values is None:
            self._show_error("El preajuste %s no existe." % name)
            return
        self._set_scales(values)
        self._selected = name
        self.state["preset"] = name
        self.state["bands"] = list(values)
        self._persist_state()
        self._reflect_selected_card()
        self._apply_engine_values(values)

    def _apply_state_to_ui(self) -> None:
        self._silent_ui = True
        preset = self.state.get("preset")
        values = self.presets.get(preset) if preset else None
        if values is None:
            values = self.state.get("bands") or [0.0] * len(BAND_HZ)
        for scale, value in zip(self._scales, values):
            scale.set_value(value)
        self._silent_ui = False
        for lbl, value in zip(self._db_labels, values):
            lbl.set_text("%+.0f dB" % value)
        self._eq_curve.queue_draw()
        self.switch.handler_block(self._switch_id)
        self.switch.set_active(bool(self.state.get("enabled")))
        self.switch.handler_unblock(self._switch_id)
        self._selected = preset or ""
        self._reflect_selected_card()
        self._refresh_status()

    def _apply_engine_values(self, values: list[float]) -> None:
        try:
            self.engine.set_bands(values)
        except EngineError as exc:
            self._show_error(str(exc))

    def _persist_state(self) -> None:
        if self._silent_ui:
            return
        values = self._collect_scales()
        self.state["bands"] = list(values)
        self._apply_engine_values(values)
        self.state["master"] = self._wanted_master()
        self._state_store.save(self.state)

    def _wanted_master(self) -> str:
        chosen = self.master_combo.get_active_text() \
            if hasattr(self, "master_combo") else None
        return chosen or self._default_sink()

    def _default_sink(self) -> str:
        try:
            return self.engine.get_default_sink()
        except EngineError:
            return ""

    def _loaded_master_or_none(self) -> str | None:
        try:
            return self.engine.get_master()
        except EngineError:
            return None

    def _show_error(self, text: str) -> None:
        self._error_label.set_text("Atención: %s" % text)
        self.banner.show()
