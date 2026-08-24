"""window.py — MainWindow for the astrology GUI.

Library-first: uses AstroClient (library backend) so no HTTP server is
required. Tabs: Natal Wheel, Transit Wheel, Synastry Wheel, Natal Table,
Transit Grid (priority-sorted), By Planet (relative value aggregation).
"""
from __future__ import annotations

import re

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Gdk, Gio, GLib

from typing import Tuple

from astro_api_client import AstroClient
from astro_analyze.scoring import planet_relative_values, score_active_transits
from astro_analyze.transits import find_transit_events
from astro_analyze.calendar import export_to_ics_string, dedupe_contacts
from astro_gui.persistence import DocumentSetStore
from astro_gui.widgets.person_selector import PersonSelector
from astro_gui.widgets.status_bar import StatusBar
from astro_display import WheelRenderer, TableRenderer
from astro_gui.renderers.table_renderer import (
    build_transit_grid,
    build_planet_agg_table,
    format_days,
)
from astro_gui.renderers.calendar_renderer import (
    build_calendar_view,
    calendar_csv_rows,
    CALENDAR_CSV_COLUMNS,
)
from astro_text.symbols import symbol_for_body, symbol_for_sign, symbol_for_aspect
from astro_text.format import format_degree
from astro_text.dignity import get_dignity
from astro_text.houses import find_house


# ------------------------------------------------------------------
# Export helpers (pure functions — unit-testable headless)
# ------------------------------------------------------------------

def _safe_name(name: str) -> str:
    """Sanitize a person/tab name for use inside a default file name."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "person").strip("_") or "person"


def _body_label(name: str) -> str:
    """'☉ Sun' — Unicode glyph + canonical name (no text fallback)."""
    glyph = symbol_for_body(name) or ""
    return f"{glyph} {name}".strip()


def _sign_label(name: str) -> str:
    """'♌ Leo' — Unicode glyph + sign name; '' when the name is empty."""
    if not name:
        return ""
    try:
        glyph = symbol_for_sign(name)
    except KeyError:
        glyph = ""
    return f"{glyph} {name}".strip()


def _aspect_label(name: str) -> str:
    """'☌ conjunction' — Unicode glyph + aspect name; '' when empty."""
    if not name:
        return ""
    try:
        glyph = symbol_for_aspect(name)
    except KeyError:
        glyph = ""
    return f"{glyph} {name}".strip()


def natal_csv_rows(chart: dict) -> list[dict]:
    """Rows for the natal table CSV (Body/Sign carry real glyph chars)."""
    rows = []
    for b in sorted(chart.get("bodies", []), key=lambda x: x.get("longitude", 0.0)):
        name = b.get("name", "?")
        sign = b.get("sign_name", "?")
        dignity = ""
        try:
            dignity = get_dignity(name, sign, sign_degree=b.get("sign_degree", 0.0))["label"]
        except Exception:
            dignity = ""
        rows.append({
            "Body": _body_label(name),
            "Sign": _sign_label(sign),
            "Degree": format_degree(b.get("sign_degree", 0.0)),
            "House": str(b.get("house", "-")),
            "Dignity": dignity,
            "Speed": f"{b.get('speed', 0.0):.3f}",
            "Retro": "R" if b.get("retrograde") else "",
        })
    return rows


NATAL_CSV_COLUMNS = ["Body", "Sign", "Degree", "House", "Dignity", "Speed", "Retro"]


def transit_grid_csv_rows(data: dict) -> list[dict]:
    """Rows for the transit grid CSV, mirroring build_transit_grid's lookups.

    `data` is the dict stored by the window when it builds the grid:
    {active, transit_bodies, natal_bodies, natal_houses}.
    """
    active = data.get("active", [])
    transit_bodies = data.get("transit_bodies") or []
    natal_bodies = data.get("natal_bodies") or []
    natal_houses = data.get("natal_houses") or []
    transit_by_name = {b.get("name", ""): b for b in transit_bodies}
    natal_by_name = {b.get("name", ""): b for b in natal_bodies}

    rows = []
    for t in active:
        tb = t.get("transiting_body", "?")
        nb = t.get("natal_body", "?")
        tb_body = transit_by_name.get(tb)
        nb_body = natal_by_name.get(nb)
        t_sign = (tb_body or {}).get("sign_name", "")
        n_sign = (nb_body or {}).get("sign_name", "")
        # Transit body's natal house = the house it is currently crossing.
        t_house = ""
        if tb_body is not None and natal_houses:
            try:
                t_house = str(find_house(float(tb_body.get("longitude", 0.0)), natal_houses))
            except Exception:
                t_house = ""
        # Natal body's own house from the natal chart.
        n_house = ""
        if nb_body is not None:
            try:
                n_house_num = int(nb_body.get("house", 0))
                n_house = str(n_house_num) if n_house_num else ""
            except (TypeError, ValueError):
                n_house = ""
        rows.append({
            "T Body": _body_label(tb),
            "T Sign": _sign_label(t_sign),
            "T House": t_house,
            "Aspect": _aspect_label(t.get("aspect", "?")),
            "N Body": _body_label(nb),
            "N Sign": _sign_label(n_sign),
            "N House": n_house,
            "Orb": f"{t.get('orb', 0.0):.2f}°",
            "Days": format_days(t.get("days_to_exact", 0)),
            "Priority": str(t.get("priority", 0)),
        })
    return rows


TRANSIT_GRID_CSV_COLUMNS = [
    "T Body", "T Sign", "T House", "Aspect",
    "N Body", "N Sign", "N House", "Orb", "Days", "Priority",
]


def by_planet_csv_rows(rows: list[dict]) -> list[dict]:
    """Rows for the by-planet CSV (glyphs on Body and vs-Natal names)."""
    out = []
    for r in rows:
        out.append({
            "Body": _body_label(r.get("body", "?")),
            "Total": str(r.get("total_priority", 0)),
            "Count": str(r.get("transit_count", 0)),
            "Top Aspect": _aspect_label(r.get("top_aspect", "")),
            "vs Natal": _body_label(r.get("top_natal_body", "")),
        })
    return out


BY_PLANET_CSV_COLUMNS = ["Body", "Total", "Count", "Top Aspect", "vs Natal"]


def write_csv_utf16(path: str, columns: list[str], rows: list[dict]) -> None:
    """Write a CSV with a UTF-16 BOM so Excel/LibreOffice detect it and
    the Unicode glyph characters survive."""
    import csv
    with open(path, "w", encoding="utf-16", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


class MainWindow(Gtk.ApplicationWindow):
    """Primary window: person selector, sidebar, notebook viewport, status bar."""

    __gtype_name__ = "AstroMainWindow"

    # Notebook page indices (sidebar buttons reference these)
    PAGE_NATAL_WHEEL = 0
    PAGE_TRANSIT_WHEEL = 1
    PAGE_SYNASTRY_WHEEL = 2
    PAGE_NATAL_TABLE = 3
    PAGE_TRANSIT_GRID = 4
    PAGE_BY_PLANET = 5
    PAGE_CALENDAR = 6

    def __init__(self, app=None, **kwargs):
        super().__init__(application=app, **kwargs)
        self.set_title("Astrology Tool")
        self.set_default_size(1200, 800)

        self._client = AstroClient()  # library backend, no server needed
        self._renderer = WheelRenderer(width=600, height=600)
        self._table_renderer = TableRenderer()
        self._selected_person = None
        self._all_people = []
        self._doc_sets = DocumentSetStore()
        self._restoring = False  # suppress auto-save while applying a set
        # Export state (item 33): last rendered SVG / table data per tab
        self._last_wheel_svg = None
        self._natal_table_chart = None
        self._transit_grid_data = None
        self._by_planet_rows = None
        self._calendar_data = None

        # Root vertical box
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root_box)

        # --- Top: Person Selector ---
        self._person_selector = PersonSelector(client=self._client)
        self._person_selector.set_hexpand(True)
        self._person_selector.connect("person-changed", self._on_person_changed)
        root_box.append(self._person_selector)

        # --- Middle: Paned sidebar + notebook ---
        self._paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned.set_vexpand(True)
        self._paned.set_hexpand(True)
        self._paned.set_wide_handle(True)
        root_box.append(self._paned)

        # Left sidebar
        sidebar = self._build_sidebar()
        self._paned.set_start_child(sidebar)
        self._paned.set_position(240)

        # Right: Notebook (viewport)
        self._notebook = self._build_notebook()
        self._paned.set_end_child(self._notebook)

        # --- Bottom: Status Bar ---
        self._status_bar = StatusBar()
        root_box.append(self._status_bar)

        # Fetch people list for synastry dropdown and tracking
        self._fetch_all_people()

        # Auto-save the current document set when the window closes
        self.connect("close-request", self._on_close_request)

        # Window actions backing the File menu (win.save-document-set / win.load-document-set)
        save_action = Gio.SimpleAction.new("save-document-set", None)
        save_action.connect("activate", self._on_save_set_as)
        self.add_action(save_action)
        load_action = Gio.SimpleAction.new("load-document-set", None)
        load_action.connect("activate", self._on_load_set)
        self.add_action(load_action)

        # Trigger initial chart load now that all widgets exist and handler is connected
        first_person = self._person_selector.get_selected_person()
        if first_person:
            self._on_person_changed(self._person_selector, first_person)

        # Restore the last active person and their saved document set
        self._restore_session()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> Gtk.Box:
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_spacing(6)
        sidebar_box.set_margin_start(6)
        sidebar_box.set_margin_end(6)
        sidebar_box.set_margin_top(6)
        sidebar_box.set_margin_bottom(6)

        label = Gtk.Label(label="Navigation Panel")
        label.set_xalign(0.0)
        sidebar_box.append(label)

        btn_natal = Gtk.Button(label="Natal")
        btn_natal.connect("clicked", lambda _b: self._show_natal_wheel())
        sidebar_box.append(btn_natal)

        btn_transit = Gtk.Button(label="Transit")
        btn_transit.connect("clicked", lambda _b: self._show_transit_wheel())
        sidebar_box.append(btn_transit)

        btn_synastry = Gtk.Button(label="Synastry")
        btn_synastry.connect("clicked", lambda _b: self._show_synastry_wheel())
        sidebar_box.append(btn_synastry)

        btn_table = Gtk.Button(label="Table")
        btn_table.connect("clicked", lambda _b: self._show_natal_table())
        sidebar_box.append(btn_table)

        btn_grid = Gtk.Button(label="Grid")
        btn_grid.connect("clicked", lambda _b: self._show_transit_grid())
        sidebar_box.append(btn_grid)

        btn_by_planet = Gtk.Button(label="By Planet")
        btn_by_planet.connect("clicked", lambda _b: self._show_by_planet())
        sidebar_box.append(btn_by_planet)

        btn_calendar = Gtk.Button(label="Calendar")
        btn_calendar.connect("clicked", lambda _b: self._show_calendar())
        sidebar_box.append(btn_calendar)

        # Save / export the currently displayed chart (item 33)
        btn_save = Gtk.Button(label="Save...")
        btn_save.set_tooltip_text("Export the displayed chart: PNG (wheels) or CSV (tables)")
        btn_save.connect("clicked", lambda _b: self._export_current())
        sidebar_box.append(btn_save)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar_box.append(spacer)

        return sidebar_box

    # ------------------------------------------------------------------
    # Document-set persistence
    # ------------------------------------------------------------------
    def _transit_grid_view(self):
        """The transit grid filter box (unwraps the ScrolledWindow's Viewport)."""
        child = self._transit_grid_scroll.get_child()
        if child is None:
            return None
        # Gtk.ScrolledWindow wraps its child in a Viewport
        if hasattr(child, "get_child") and not hasattr(child, "filter_row"):
            child = child.get_child()
        if child is not None and hasattr(child, "filter_row"):
            return child
        return None

    def _capture_document_set(self) -> dict:
        """Snapshot the current UI state into a config dict."""
        config = {
            "version": 1,
            "current_tab": self._notebook.get_current_page(),
            "transit_date": self._transit_date.get_text(),
            "transit_time": self._transit_time.get_text(),
            "transit_lat": self._transit_lat.get_text(),
            "transit_lon": self._transit_lon.get_text(),
            "aspect_mode": self._transit_aspect_mode.get_selected_item().get_string(),
            "calendar_start": self._calendar_start.get_text(),
            "calendar_end": self._calendar_end.get_text(),
            "calendar_aspect": self._calendar_aspect.get_selected_item().get_string(),
        }
        # Transit grid filter state (point / aspect / sign / house), if present
        grid = self._transit_grid_view()
        if grid is not None:
            fr = grid.filter_row
            config["grid_filter"] = {
                "point": fr.point_dropdown.get_selected_item().get_string(),
                "point_side": fr.point_side_dropdown.get_selected_item().get_string(),
                "aspect": fr.aspect_dropdown.get_selected_item().get_string(),
                "sign_side": fr.sign_side_dropdown.get_selected_item().get_string(),
                "sign": fr.sign_dropdown.get_selected_item().get_string(),
                "house_side": fr.house_side_dropdown.get_selected_item().get_string(),
                "house": fr.house_dropdown.get_selected_item().get_string(),
            }
        return config

    def _apply_document_set(self, config: dict):
        """Restore UI state from a config dict (best-effort, tolerant)."""
        if not isinstance(config, dict):
            return
        self._restoring = True
        try:
            if "current_tab" in config:
                try:
                    page = int(config["current_tab"])
                    if 0 <= page < self._notebook.get_n_pages():
                        self._notebook.set_current_page(page)
                except (TypeError, ValueError):
                    pass
            if "transit_date" in config:
                self._transit_date.set_text(str(config["transit_date"]))
            if "transit_time" in config:
                self._transit_time.set_text(str(config["transit_time"]))
            if "transit_lat" in config:
                self._transit_lat.set_text(str(config["transit_lat"]))
            if "transit_lon" in config:
                self._transit_lon.set_text(str(config["transit_lon"]))
            if "aspect_mode" in config:
                self._set_aspect_mode(str(config["aspect_mode"]))
            if "calendar_start" in config:
                self._calendar_start.set_text(str(config["calendar_start"]))
            if "calendar_end" in config:
                self._calendar_end.set_text(str(config["calendar_end"]))
            if "calendar_aspect" in config:
                self._set_dropdown_by_string(self._calendar_aspect, str(config["calendar_aspect"]))
            # Transit grid filter state
            grid = self._transit_grid_view()
            if grid is not None:
                fr = grid.filter_row
                gf = config.get("grid_filter") or {}
                if "point" in gf:
                    self._set_dropdown_by_string(fr.point_dropdown, str(gf["point"]))
                if "point_side" in gf:
                    self._set_dropdown_by_string(fr.point_side_dropdown, str(gf["point_side"]))
                if "aspect" in gf:
                    self._set_dropdown_by_string(fr.aspect_dropdown, str(gf["aspect"]))
                if "sign_side" in gf:
                    self._set_dropdown_by_string(fr.sign_side_dropdown, str(gf["sign_side"]))
                if "sign" in gf:
                    self._set_dropdown_by_string(fr.sign_dropdown, str(gf["sign"]))
                if "house_side" in gf:
                    self._set_dropdown_by_string(fr.house_side_dropdown, str(gf["house_side"]))
                if "house" in gf:
                    self._set_dropdown_by_string(fr.house_dropdown, str(gf["house"]))
        finally:
            self._restoring = False

    @staticmethod
    def _set_dropdown_by_string(dropdown: Gtk.DropDown, value: str):
        """Select a DropDown item by its string value; no-op if absent."""
        model = dropdown.get_model()
        if model is None:
            return
        for i in range(model.get_n_items()):
            if model.get_string(i) == value:
                dropdown.set_selected(i)
                return

    def _set_aspect_mode(self, value: str):
        """Select the transit aspect-mode DropDown by value; no-op if absent."""
        self._set_dropdown_by_string(self._transit_aspect_mode, value)

    def _save_current_set(self, person_id: int):
        """Auto-save the current UI state as the person's default set."""
        try:
            self._doc_sets.save_default(person_id, self._capture_document_set())
        except Exception as exc:
            self._status_bar.set_info(f"Document set save error: {exc}")

    def _restore_person_set(self, person_id: int):
        """Load a person's saved default set, or the default layout."""
        config = self._doc_sets.load_default(person_id)
        if config is None:
            config = {"version": 1, "current_tab": self.PAGE_NATAL_WHEEL}
        self._apply_document_set(config)

    def _restore_session(self):
        """Restore the last active person and their saved document set."""
        try:
            last_id = self._doc_sets.load_last_active()
        except Exception:
            last_id = None
        if last_id is not None:
            self._person_selector.select_person_by_id(last_id)
        # Apply the (possibly just-loaded) person's saved set
        person = self._person_selector.get_selected_person()
        if person is not None:
            self._restore_person_set(person.get("id"))

    def _on_close_request(self, *args):
        """Auto-save the current document set before the window closes."""
        person = self._selected_person
        if person is not None:
            self._save_current_set(person.get("id"))
        return False  # allow the close to proceed

    def _on_save_set_as(self, *args):
        """File -> Save Document Set As...: prompt for a name and snapshot."""
        person = self._selected_person
        if person is None:
            self._status_bar.set_info("No person selected")
            return
        dialog = Gtk.Dialog(
            transient_for=self,
            modal=True,
            title="Save Document Set As...",
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(6)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.append(Gtk.Label(label="Set name:"))
        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g. Morning check")
        content.append(entry)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.connect("response", self._on_save_set_response, entry, person)
        dialog.present()

    def _on_save_set_response(self, dialog, response, entry, person):
        if response == Gtk.ResponseType.OK:
            name = entry.get_text().strip()
            if name:
                try:
                    self._doc_sets.save_set(
                        person.get("id"), name, self._capture_document_set()
                    )
                    self._status_bar.set_info(f"Saved document set '{name}'")
                except Exception as exc:
                    self._status_bar.set_info(f"Document set save error: {exc}")
        dialog.destroy()

    def _on_load_set(self, *args):
        """File -> Load Document Set...: choose a saved snapshot to apply."""
        person = self._selected_person
        if person is None:
            self._status_bar.set_info("No person selected")
            return
        sets = self._doc_sets.list_sets(person.get("id"))
        if not sets:
            self._status_bar.set_info("No saved document sets for this person")
            return
        dialog = Gtk.Dialog(
            transient_for=self,
            modal=True,
            title="Load Document Set...",
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Load", Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(6)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.append(Gtk.Label(label="Saved sets:"))
        names = Gtk.StringList.new([s["name"] for s in sets])
        dropdown = Gtk.DropDown(model=names)
        dropdown.set_hexpand(True)
        content.append(dropdown)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.connect("response", self._on_load_set_response, dropdown, sets, person)
        dialog.present()

    def _on_load_set_response(self, dialog, response, dropdown, sets, person):
        if response == Gtk.ResponseType.OK:
            idx = dropdown.get_selected()
            if 0 <= idx < len(sets):
                config = self._doc_sets.load_set(person.get("id"), sets[idx]["name"])
                if config is not None:
                    self._apply_document_set(config)
                    self._status_bar.set_info(f"Loaded document set '{sets[idx]['name']}'")
                else:
                    self._status_bar.set_info("Document set could not be loaded")
        dialog.destroy()

    # ------------------------------------------------------------------
    # Notebook / viewport
    # ------------------------------------------------------------------
    def _build_notebook(self) -> Gtk.Notebook:
        notebook = Gtk.Notebook()
        notebook.set_hexpand(True)
        notebook.set_vexpand(True)

        # --- Tab 1: Natal Wheel ---
        self._natal_scroll, self._natal_picture = self._make_wheel_view()
        notebook.append_page(self._natal_scroll, Gtk.Label(label="Natal Wheel"))

        # --- Tab 2: Transit Wheel ---
        self._transit_scroll, self._transit_picture = self._make_wheel_view()
        transit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._transit_scroll.set_child(transit_box)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        controls.set_spacing(6)
        controls.set_margin_top(6)
        controls.set_margin_start(6)
        controls.set_margin_end(6)

        controls.append(Gtk.Label(label="Date:"))
        self._transit_date = Gtk.Entry()
        self._transit_date.set_placeholder_text("YYYY-MM-DD")
        self._transit_date.set_text(self._today_iso())
        self._transit_date.set_max_width_chars(12)
        controls.append(self._transit_date)

        controls.append(Gtk.Label(label="Time:"))
        self._transit_time = Gtk.Entry()
        self._transit_time.set_placeholder_text("HH:MM:SS")
        self._transit_time.set_text(self._now_time())
        self._transit_time.set_max_width_chars(10)
        controls.append(self._transit_time)

        controls.append(Gtk.Label(label="Lat:"))
        self._transit_lat = Gtk.Entry()
        self._transit_lat.set_placeholder_text("lat")
        self._transit_lat.set_max_width_chars(8)
        controls.append(self._transit_lat)

        controls.append(Gtk.Label(label="Lon:"))
        self._transit_lon = Gtk.Entry()
        self._transit_lon.set_placeholder_text("lon")
        self._transit_lon.set_max_width_chars(9)
        controls.append(self._transit_lon)

        controls.append(Gtk.Label(label="Aspects:"))
        self._transit_aspect_mode = Gtk.DropDown.new_from_strings([
            "transit-natal", "transit-transit", "both",
        ])
        self._transit_aspect_mode.set_selected(0)  # transit-natal default
        self._transit_aspect_mode.connect(
            "notify::selected", lambda _d, _p: self._refresh_transit()
        )
        controls.append(self._transit_aspect_mode)

        btn_now = Gtk.Button(label="Now")
        btn_now.connect("clicked", lambda _b: self._set_transit_now())
        controls.append(btn_now)

        btn_go = Gtk.Button(label="Update")
        btn_go.connect("clicked", lambda _b: self._refresh_transit())
        controls.append(btn_go)

        transit_box.append(controls)
        transit_box.append(self._transit_picture)
        self._transit_picture.set_vexpand(True)

        notebook.append_page(self._transit_scroll, Gtk.Label(label="Transit Wheel"))

        # --- Tab 3: Synastry Wheel ---
        self._synastry_scroll, self._synastry_picture = self._make_wheel_view()
        synastry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._synastry_scroll.set_child(synastry_box)

        syn_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        syn_controls.set_spacing(6)
        syn_controls.set_margin_top(6)
        syn_controls.set_margin_start(6)
        syn_controls.set_margin_end(6)
        syn_controls.append(Gtk.Label(label="Person B:"))

        self._synastry_dropdown = Gtk.DropDown()
        self._synastry_dropdown.set_hexpand(True)
        syn_controls.append(self._synastry_dropdown)

        btn_syn_go = Gtk.Button(label="Show")
        btn_syn_go.connect("clicked", lambda _b: self._refresh_synastry())
        syn_controls.append(btn_syn_go)

        synastry_box.append(syn_controls)
        synastry_box.append(self._synastry_picture)
        self._synastry_picture.set_vexpand(True)

        notebook.append_page(self._synastry_scroll, Gtk.Label(label="Synastry Wheel"))

        # --- Tab 4: Natal Table ---
        self._natal_table_scroll, self._natal_table_picture = self._make_wheel_view()
        notebook.append_page(self._natal_table_scroll, Gtk.Label(label="Natal Table"))

        # --- Tab 5: Transit Grid ---
        self._transit_grid_scroll = Gtk.ScrolledWindow()
        self._transit_grid_scroll.set_hexpand(True)
        self._transit_grid_scroll.set_vexpand(True)
        notebook.append_page(self._transit_grid_scroll, Gtk.Label(label="Transit Grid"))

        # --- Tab 6: By Planet ---
        self._by_planet_scroll = Gtk.ScrolledWindow()
        self._by_planet_scroll.set_hexpand(True)
        self._by_planet_scroll.set_vexpand(True)
        notebook.append_page(self._by_planet_scroll, Gtk.Label(label="By Planet"))

        # --- Tab 7: Calendar (date-range transit events) ---
        self._calendar_scroll = Gtk.ScrolledWindow()
        self._calendar_scroll.set_hexpand(True)
        self._calendar_scroll.set_vexpand(True)
        calendar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._calendar_scroll.set_child(calendar_box)

        cal_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cal_controls.set_spacing(6)
        cal_controls.set_margin_top(6)
        cal_controls.set_margin_start(6)
        cal_controls.set_margin_end(6)

        cal_controls.append(Gtk.Label(label="Start:"))
        self._calendar_start = Gtk.Entry()
        self._calendar_start.set_placeholder_text("YYYY-MM-DD")
        self._calendar_start.set_text(self._today_iso())
        self._calendar_start.set_max_width_chars(12)
        cal_controls.append(self._calendar_start)

        cal_controls.append(Gtk.Label(label="End:"))
        self._calendar_end = Gtk.Entry()
        self._calendar_end.set_placeholder_text("YYYY-MM-DD")
        self._calendar_end.set_text(self._days_from_today_iso(30))
        self._calendar_end.set_max_width_chars(12)
        cal_controls.append(self._calendar_end)

        cal_controls.append(Gtk.Label(label="Aspect:"))
        self._calendar_aspect = Gtk.DropDown.new_from_strings([
            "all", "conjunction", "opposition", "square", "trine", "sextile",
        ])
        self._calendar_aspect.set_selected(0)
        cal_controls.append(self._calendar_aspect)

        btn_cal_go = Gtk.Button(label="Update")
        btn_cal_go.connect("clicked", lambda _b: self._refresh_calendar())
        cal_controls.append(btn_cal_go)

        calendar_box.append(cal_controls)
        self._calendar_view_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        calendar_box.append(self._calendar_view_box)
        self._calendar_view_box.set_vexpand(True)

        notebook.append_page(self._calendar_scroll, Gtk.Label(label="Calendar"))

        notebook.set_current_page(self.PAGE_NATAL_WHEEL)
        return notebook

    def _make_wheel_view(self) -> Tuple[Gtk.ScrolledWindow, Gtk.Picture]:
        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        picture = Gtk.Picture()
        picture.set_hexpand(True)
        picture.set_vexpand(True)
        picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        scroll.set_child(picture)
        return scroll, picture

    def _today_iso(self) -> str:
        import datetime
        return datetime.date.today().isoformat()

    def _days_from_today_iso(self, days: int) -> str:
        import datetime
        return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()

    def _now_time(self) -> str:
        import datetime
        return datetime.datetime.now().strftime("%H:%M:%S")

    def _set_transit_now(self):
        self._transit_date.set_text(self._today_iso())
        self._transit_time.set_text(self._now_time())
        self._refresh_transit()

    def _refresh_transit(self):
        person = self._selected_person
        if not person:
            self._status_bar.set_info("No person selected")
            return
        self._load_transit_chart(person)

    def _refresh_synastry(self):
        person_a = self._selected_person
        if not person_a:
            self._status_bar.set_info("No Person A selected")
            return
        selected = self._synastry_dropdown.get_selected_item()
        if not selected:
            self._status_bar.set_info("Select Person B")
            return
        person_b_name = selected.get_string()
        for p in self._all_people:
            if p.get("name") == person_b_name:
                self._load_synastry_chart(person_a, p)
                return
        self._status_bar.set_info(f"Person B '{person_b_name}' not found")

    # ------------------------------------------------------------------
    # Chart loading
    # ------------------------------------------------------------------
    def _display_svg(self, svg_text: str, picture: Gtk.Picture = None):
        """Render an SVG string into a Picture widget via a temp file."""
        import tempfile, os
        target = picture or self._natal_picture
        fd, path = tempfile.mkstemp(suffix=".svg")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg_text)
            texture = Gdk.Texture.new_from_filename(path)
            target.set_paintable(texture)
        except Exception as exc:
            self._status_bar.set_info(f"SVG display error: {exc}")
        finally:
            os.close(fd)
            os.unlink(path)

    def _show_natal_wheel(self):
        """Switch to the Natal Wheel tab and refresh."""
        self._notebook.set_current_page(self.PAGE_NATAL_WHEEL)
        person = self._person_selector.get_selected_person()
        if person:
            self._load_natal_chart(person)

    def _show_transit_wheel(self):
        """Switch to the Transit Wheel tab and refresh."""
        self._notebook.set_current_page(self.PAGE_TRANSIT_WHEEL)
        self._refresh_transit()

    def _show_synastry_wheel(self):
        """Switch to the Synastry Wheel tab."""
        self._notebook.set_current_page(self.PAGE_SYNASTRY_WHEEL)

    def _show_natal_table(self):
        """Switch to the Natal Table tab and refresh."""
        self._notebook.set_current_page(self.PAGE_NATAL_TABLE)
        person = self._person_selector.get_selected_person()
        if person:
            self._load_natal_table(person)

    def _show_transit_grid(self):
        """Switch to the Transit Grid tab and refresh."""
        self._notebook.set_current_page(self.PAGE_TRANSIT_GRID)
        self._refresh_transit_grid()

    def _show_by_planet(self):
        """Switch to the By Planet tab and refresh."""
        self._notebook.set_current_page(self.PAGE_BY_PLANET)
        self._refresh_by_planet()

    def _show_calendar(self):
        """Switch to the Calendar tab and refresh."""
        self._notebook.set_current_page(self.PAGE_CALENDAR)
        self._refresh_calendar()

    # ------------------------------------------------------------------
    # Person list management
    # ------------------------------------------------------------------
    def _fetch_all_people(self):
        """Populate _all_people and synastry dropdown from the store."""
        try:
            result = self._client.list_people()
            if result.get("status") == "ok":
                self._all_people = result.get("people", [])
                names = [p.get("name", "?") for p in self._all_people]
                model = Gtk.StringList.new(names)
                self._synastry_dropdown.set_model(model)
                if len(names) > 1:
                    self._synastry_dropdown.set_selected(1)
        except Exception as exc:
            self._status_bar.set_info(f"People fetch error: {exc}")

    # ------------------------------------------------------------------
    # Chart loading
    # ------------------------------------------------------------------
    def _on_person_changed(self, selector, person_dict):
        # Auto-save the previous person's document set before switching
        if self._selected_person is not None and not self._restoring:
            self._save_current_set(self._selected_person.get("id"))
        self._selected_person = person_dict
        name = person_dict.get("name", "Unknown")
        self._status_bar.set_info(f"Loading chart for {name}...")
        self._load_natal_chart(person_dict)
        self._load_natal_table(person_dict)
        # Refresh the transit grid and by-planet tabs (review items 26+27)
        self._refresh_transit_grid()
        self._refresh_by_planet()
        # Prefill transit lat/lon from the natal chart's location
        chart = self._get_chart(person_dict)
        if chart is not None:
            meta = chart.get("meta", {})
            if meta.get("latitude") is not None:
                self._transit_lat.set_text(f"{meta['latitude']:.4f}")
            if meta.get("longitude") is not None:
                self._transit_lon.set_text(f"{meta['longitude']:.4f}")
        for i, p in enumerate(self._all_people):
            if p.get("id") == person_dict.get("id"):
                next_idx = (i + 1) % len(self._all_people) if len(self._all_people) > 1 else 0
                self._synastry_dropdown.set_selected(next_idx)
                break
        # Restore the newly selected person's saved document set
        if not self._restoring:
            self._restore_person_set(person_dict.get("id"))
            # Re-render transit-dependent views with the restored date/filters
            self._refresh_transit_grid()
            self._refresh_by_planet()
        # Track the last active person for next-session restore
        try:
            self._doc_sets.save_last_active(person_dict.get("id"))
        except Exception:
            pass

    def _get_chart(self, person_dict) -> dict | None:
        """Return the stored natal chart for a person, or None."""
        chart_id = person_dict.get("chart_id")
        if not chart_id:
            return None
        try:
            return self._client.get_chart(chart_id)
        except Exception:
            return None

    def _load_natal_chart(self, person_dict):
        try:
            chart = self._get_chart(person_dict)
            if chart is None:
                self._status_bar.set_info(f"No stored natal chart for {person_dict.get('name')}")
                return
            svg = self._renderer.render_natal(chart, scale=1.0)
            self._last_wheel_svg = svg
            self._display_svg(svg, self._natal_picture)
            bodies = chart.get("bodies", [])
            sun = next((b for b in bodies if b.get("name") == "Sun"), None)
            asc = chart.get("angles", {}).get("ascendant", 0)
            hs = chart.get("houses", [{}])[0].get("sign_name", "?")
            sun_info = f"Sun {sun.get('sign_name', '?')} {sun.get('sign_degree', 0):.1f}°" if sun else "Sun ?"
            info = f"{person_dict.get('name', 'Unknown')} — {sun_info} | Asc {hs} {asc:.1f}° | Koch"
            self._status_bar.set_info(info)
        except Exception as exc:
            self._status_bar.set_info(f"Chart error: {exc}")

    def _load_natal_table(self, person_dict):
        try:
            chart = self._get_chart(person_dict)
            if chart is None:
                self._status_bar.set_info(f"No stored natal chart for {person_dict.get('name')}")
                return
            svg = self._table_renderer.render_natal_table(chart)
            self._natal_table_chart = chart
            self._display_svg(svg, self._natal_table_picture)
            self._status_bar.set_info(f"Natal table for {person_dict.get('name')} — LiberZodiac glyphs")
        except Exception as exc:
            self._status_bar.set_info(f"Table error: {exc}")

    def _load_transit_chart(self, person_dict):
        """Fetch transit data and render two-ring transit wheel."""
        try:
            natal_chart = self._get_chart(person_dict)
            if natal_chart is None:
                self._status_bar.set_info(f"No stored natal chart for {person_dict.get('name')}")
                return
            chart_id = person_dict.get("chart_id")
            date = self._transit_date.get_text()
            time = self._transit_time.get_text()
            # Location override: use the lat/lon fields if filled, else natal
            lat_text = self._transit_lat.get_text().strip()
            lon_text = self._transit_lon.get_text().strip()
            lat = float(lat_text) if lat_text else None
            lon = float(lon_text) if lon_text else None
            result = self._client.transit(chart_id, date, time, latitude=lat, longitude=lon)
            if result.get("status") != "ok":
                self._status_bar.set_info(f"Transit error: {result.get('message', 'Unknown')}")
                return
            natal_data = {
                "angles": natal_chart.get("angles", {}),
                "houses": natal_chart.get("houses", []),
                "bodies": natal_chart.get("bodies", []),
                "aspects": natal_chart.get("aspects", []),
            }
            transit_data = {
                "bodies": result.get("bodies", []),
                "cross_aspects": result.get("cross_aspects", []),
            }
            aspect_mode = self._transit_aspect_mode.get_selected_item().get_string()
            svg = self._renderer.render_transit(
                natal_data, transit_data, aspect_mode=aspect_mode
            )
            self._last_wheel_svg = svg
            self._display_svg(svg, self._transit_picture)
            loc = f" @ {lat_text},{lon_text}" if lat_text and lon_text else ""
            self._status_bar.set_info(
                f"Transit for {person_dict.get('name')} on {date} {time}{loc} "
                f"[{aspect_mode}]"
            )
        except Exception as exc:
            self._status_bar.set_info(f"Transit error: {exc}")

    def _refresh_transit_grid(self):
        person = self._selected_person
        if not person:
            self._status_bar.set_info("No person selected")
            return
        try:
            natal_chart = self._get_chart(person)
            if natal_chart is None:
                self._status_bar.set_info(f"No stored natal chart for {person.get('name')}")
                return
            chart_id = person.get("chart_id")
            date = self._transit_date.get_text()
            time = self._transit_time.get_text()
            transit = self._client.transit(chart_id, date, time)
            impact = self._client.period_impact(chart_id, date, orb_days=7)
            active = impact.get("impact", {}).get("active_transits", [])
            view = build_transit_grid(
                active,
                transit_bodies=transit.get("bodies", []),
                natal_bodies=natal_chart.get("bodies", []),
                natal_houses=natal_chart.get("houses", []),
            )
            self._transit_grid_data = {
                "active": active,
                "transit_bodies": transit.get("bodies", []),
                "natal_bodies": natal_chart.get("bodies", []),
                "natal_houses": natal_chart.get("houses", []),
            }
            self._transit_grid_scroll.set_child(view)
            self._status_bar.set_info(
                f"Transit grid for {person.get('name')} on {date} — {len(active)} transits, sorted by priority"
            )
        except Exception as exc:
            self._status_bar.set_info(f"Grid error: {exc}")

    def _refresh_by_planet(self):
        person = self._selected_person
        if not person:
            self._status_bar.set_info("No person selected")
            return
        try:
            natal_chart = self._get_chart(person)
            if natal_chart is None:
                self._status_bar.set_info(f"No stored natal chart for {person.get('name')}")
                return
            chart_id = person.get("chart_id")
            date = self._transit_date.get_text()
            time = self._transit_time.get_text()
            transit = self._client.transit(chart_id, date, time)
            impact = self._client.period_impact(chart_id, date, orb_days=7)
            active = impact.get("impact", {}).get("active_transits", [])
            rows = planet_relative_values(active, natal_chart, transit)
            self._by_planet_rows = rows
            view = build_planet_agg_table(rows)
            self._by_planet_scroll.set_child(view)
            self._status_bar.set_info(
                f"By planet for {person.get('name')} on {date} — {len(rows)} planets by relative value"
            )
        except Exception as exc:
            self._status_bar.set_info(f"By-planet error: {exc}")

    def _refresh_calendar(self):
        """Build the date-range transit event list for the Calendar tab.

        Uses astro_analyze.transits.find_transit_events (library-first,
        no HTTP server) and scores each event with the centralized
        score_active_transits so the list matches the Transit Grid's
        priority semantics. The natal chart's location is flattened from
        `meta` to the top level because find_transit_events reads
        latitude/longitude/house_system there.
        """
        person = self._selected_person
        if not person:
            self._status_bar.set_info("No person selected")
            return
        try:
            natal_chart = self._get_chart(person)
            if natal_chart is None:
                self._status_bar.set_info(f"No stored natal chart for {person.get('name')}")
                return
            chart_id = person.get("chart_id")
            start = self._calendar_start.get_text().strip()
            end = self._calendar_end.get_text().strip()
            aspect = self._calendar_aspect.get_selected_item().get_string()

            # find_transit_events reads location at the chart top level;
            # stored charts keep it under meta — flatten it.
            flat = dict(natal_chart)
            meta = natal_chart.get("meta", {})
            flat.setdefault("latitude", meta.get("latitude", 0.0))
            flat.setdefault("longitude", meta.get("longitude", 0.0))
            flat.setdefault("house_system", meta.get("house_system", "K"))

            include_aspects = None if aspect == "all" else [aspect]
            events = find_transit_events(
                flat, start, end,
                include_points=None,
                include_aspects=include_aspects,
                orb_preset=meta.get("orb_preset", "Modern"),
            )
            # One row per aspect contact (dated at its most exact day),
            # not every in-orb day — otherwise a month shows ~1400 rows.
            events = dedupe_contacts(events)

            # Score with the centralized formula (sign lookups + grid
            # weights come from a synthesized transit chart at the first
            # event date; grid weights are a minor term, so a single-date
            # approximation is acceptable for the list view).
            transit_chart = {"bodies": [], "aspects": []}
            if events:
                first_date = events[0].get("date", start)
                try:
                    transit = self._client.transit(chart_id, first_date, "12:00:00")
                    transit_chart = {
                        "bodies": transit.get("bodies", []),
                        "aspects": transit.get("cross_aspects", []),
                    }
                except Exception:
                    transit_chart = {"bodies": [], "aspects": []}
            scored = score_active_transits(events, natal_chart, transit_chart)

            self._calendar_data = {
                "events": scored,
                "start": start,
                "end": end,
                "aspect": aspect,
            }
            view = build_calendar_view(scored)
            # Replace the previous view (keep the controls row above).
            child = self._calendar_view_box.get_first_child()
            while child is not None:
                self._calendar_view_box.remove(child)
                child = self._calendar_view_box.get_first_child()
            self._calendar_view_box.append(view)
            self._status_bar.set_info(
                f"Calendar for {person.get('name')} {start} → {end} — {len(scored)} events"
            )
        except Exception as exc:
            self._status_bar.set_info(f"Calendar error: {exc}")

    def _load_synastry_chart(self, person_a, person_b):
        """Fetch synastry data and render two-ring synastry wheel."""
        try:
            chart_a = self._get_chart(person_a)
            chart_b = self._get_chart(person_b)
            if not chart_a or not chart_b:
                missing = "A" if not chart_a else "B"
                self._status_bar.set_info(f"No stored natal chart for person {missing}")
                return
            result = self._client.synastry(
                person_a.get("chart_id"), person_b.get("chart_id")
            )
            if result.get("status") != "ok":
                self._status_bar.set_info(f"Synastry error: {result.get('message', 'Unknown')}")
                return
            a_data = {
                "angles": chart_a.get("angles", {}),
                "houses": chart_a.get("houses", []),
                "bodies": chart_a.get("bodies", []),
            }
            b_data = {
                "bodies": chart_b.get("bodies", []),
            }
            svg = self._renderer.render_synastry(
                a_data, b_data, result.get("cross_aspects", [])
            )
            self._last_wheel_svg = svg
            self._display_svg(svg, self._synastry_picture)
            count = len(result.get("cross_aspects", []))
            self._status_bar.set_info(
                f"Synastry: {person_a.get('name')} vs {person_b.get('name')} — {count} cross aspects"
            )
        except Exception as exc:
            self._status_bar.set_info(f"Synastry error: {exc}")

    # ------------------------------------------------------------------
    # Export (item 33: Save button)
    # ------------------------------------------------------------------
    def _export_current(self):
        """Export the currently displayed chart.

        Wheel tabs (Natal/Transit/Synastry) rasterize the last-rendered
        SVG to PNG via Gdk.Texture. Table tabs (Natal Table / Transit
        Grid / By Planet) write a UTF-16 CSV with the real Unicode glyph
        characters. Uses an async Gtk.FileDialog.save() so the main loop
        is never blocked; cancelling is a no-op.
        """
        page = self._notebook.get_current_page()
        if page in (self.PAGE_NATAL_WHEEL, self.PAGE_TRANSIT_WHEEL, self.PAGE_SYNASTRY_WHEEL):
            svg = getattr(self, "_last_wheel_svg", None)
            if not svg:
                self._status_bar.set_info("Nothing to export — render a wheel first")
                return
            default = f"{_safe_name(self._tab_default_name(page))}_{_safe_name(self._person_name())}.png"
            self._pick_save_path(default, [("PNG image", "image/png", "*.png")],
                                 self._on_png_dialog_result, svg)
        elif page == self.PAGE_NATAL_TABLE:
            chart = getattr(self, "_natal_table_chart", None)
            if chart is None:
                self._status_bar.set_info("Nothing to export — render the natal table first")
                return
            default = f"natal_{_safe_name(self._person_name())}.csv"
            self._pick_save_path(default, [("CSV", "text/csv", "*.csv")],
                                 self._on_csv_dialog_result,
                                 NATAL_CSV_COLUMNS, natal_csv_rows(chart))
        elif page == self.PAGE_TRANSIT_GRID:
            data = getattr(self, "_transit_grid_data", None)
            if not data or not data.get("active"):
                self._status_bar.set_info("Nothing to export — render the transit grid first")
                return
            default = f"transit_grid_{_safe_name(self._person_name())}_{self._transit_date.get_text()}.csv"
            self._pick_save_path(default, [("CSV", "text/csv", "*.csv")],
                                 self._on_csv_dialog_result,
                                 TRANSIT_GRID_CSV_COLUMNS, transit_grid_csv_rows(data))
        elif page == self.PAGE_BY_PLANET:
            rows = getattr(self, "_by_planet_rows", None)
            if not rows:
                self._status_bar.set_info("Nothing to export — render By Planet first")
                return
            default = f"by_planet_{_safe_name(self._person_name())}_{self._transit_date.get_text()}.csv"
            self._pick_save_path(default, [("CSV", "text/csv", "*.csv")],
                                 self._on_csv_dialog_result,
                                 BY_PLANET_CSV_COLUMNS, by_planet_csv_rows(rows))
        elif page == self.PAGE_CALENDAR:
            data = getattr(self, "_calendar_data", None)
            if not data or not data.get("events"):
                self._status_bar.set_info("Nothing to export — render the calendar first")
                return
            default = f"calendar_{_safe_name(self._person_name())}_{data.get('start')}_{data.get('end')}.ics"
            self._pick_save_path(default, [("iCalendar", "text/calendar", "*.ics")],
                                 self._on_ics_dialog_result, data.get("events"))
        else:
            self._status_bar.set_info("Nothing to export on this tab")

    def _tab_default_name(self, page: int) -> str:
        """Human-readable name for a wheel page (used in the PNG default name)."""
        if page == self.PAGE_NATAL_WHEEL:
            return "natal"
        if page == self.PAGE_TRANSIT_WHEEL:
            return "transit"
        if page == self.PAGE_SYNASTRY_WHEEL:
            return "synastry"
        return "wheel"

    def _person_name(self) -> str:
        person = self._selected_person or self._person_selector.get_selected_person()
        return person.get("name", "person") if person else "person"

    def _pick_save_path(self, default_name: str, filter_specs, callback, *payload):
        """Show the async GTK save dialog and route the result to `callback`."""
        dialog = Gtk.FileDialog()
        dialog.set_initial_name(default_name)
        filter_list = Gio.ListStore.new(Gtk.FileFilter)
        for name, mime, pattern in filter_specs:
            filt = Gtk.FileFilter()
            filt.set_name(name)
            filt.add_mime_type(mime)
            filt.add_pattern(pattern)
            filter_list.append(filt)
        dialog.set_filters(filter_list)
        dialog.set_default_filter(filter_list.get_item(0))
        dialog.save(self, None, self._on_dialog_result, (callback, payload))

    def _resolve_save_path(self, file) -> str | None:
        """Return a local filesystem path for a GFile, or None.

        Portal-based Gtk.FileDialog can hand back a GFile with no local
        path (get_path() -> None). Fall back to the file:// URI and
        unquote it; anything else is unresolvable.
        """
        path = file.get_path()
        if path:
            return path
        uri = file.get_uri()
        if uri and uri.startswith("file://"):
            from urllib.parse import unquote
            return unquote(uri[len("file://"):])
        return None

    def _on_dialog_result(self, dialog, result, user_data):
        """Common async callback: close the dialog and dispatch by kind."""
        callback, payload = user_data
        try:
            file = dialog.save_finish(result)
        except GLib.Error as err:
            # save_finish only fails when the user dismissed/cancelled the
            # dialog (the actual write happens later in the callback), so
            # ANY error here is a silent cancel. Never surface it in the
            # status bar.
            import sys
            print(f"Save dialog cancelled: {err.message}", file=sys.stderr)
            return
        path = self._resolve_save_path(file)
        if path is None:
            self._status_bar.set_info("Could not resolve the chosen path")
            return
        try:
            callback(path, payload)
        except Exception as exc:
            self._status_bar.set_info(f"Export error: {exc}")

    def _on_png_dialog_result(self, path, payload):
        # _pick_save_path collects extra args into a tuple via *payload;
        # the CSV callback unpacks it, so unpack here too.
        svg = payload[0] if isinstance(payload, tuple) else payload
        import tempfile, os
        fd, tmp_svg = tempfile.mkstemp(suffix=".svg")
        try:
            with open(tmp_svg, "w", encoding="utf-8") as f:
                f.write(svg)
            texture = Gdk.Texture.new_from_filename(tmp_svg)
            ok = texture.save_to_png(path)
            if not ok:
                self._status_bar.set_info(f"PNG export failed: {path}")
                return
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                self._status_bar.set_info(f"PNG export failed: {path} is empty or missing")
                return
            self._status_bar.set_info(f"Exported PNG: {path}")
        except Exception as exc:
            self._status_bar.set_info(f"PNG export failed: {exc}")
        finally:
            os.close(fd)
            os.unlink(tmp_svg)

    def _on_csv_dialog_result(self, path, payload):
        columns, rows = payload
        write_csv_utf16(path, columns, rows)
        self._status_bar.set_info(f"Exported CSV: {path}")

    def _on_ics_dialog_result(self, path, payload):
        import os
        events = payload[0] if isinstance(payload, tuple) else payload
        ics = export_to_ics_string(events)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(ics)
        if not (os.path.exists(path) and os.path.getsize(path) > 0):
            self._status_bar.set_info(f"ICS export failed: {path} is empty or missing")
            return
        self._status_bar.set_info(f"Exported ICS: {path}")

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------
    @property
    def person_selector(self) -> PersonSelector:
        return self._person_selector

    @property
    def status_bar(self) -> StatusBar:
        return self._status_bar

    @property
    def notebook(self) -> Gtk.Notebook:
        return self._notebook
