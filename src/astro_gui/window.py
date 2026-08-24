"""window.py — MainWindow for the astrology GUI.

Library-first: uses AstroClient (library backend) so no HTTP server is
required. Tabs: Natal Wheel, Transit Wheel, Synastry Wheel, Natal Table,
Transit Grid (priority-sorted), By Planet (relative value aggregation).
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Gdk, Gio

from typing import Tuple

from astro_api_client import AstroClient
from astro_analyze.scoring import planet_relative_values
from astro_gui.persistence import DocumentSetStore
from astro_gui.widgets.person_selector import PersonSelector
from astro_gui.widgets.status_bar import StatusBar
from astro_display import WheelRenderer, TableRenderer
from astro_gui.renderers.table_renderer import (
    build_transit_grid,
    build_planet_agg_table,
)


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
        }
        # Transit grid filter state (point / aspect / sign), if present
        grid = self._transit_grid_view()
        if grid is not None:
            fr = grid.filter_row
            config["grid_filter"] = {
                "point": fr.point_entry.get_text(),
                "point_side": fr.point_side_dropdown.get_selected_item().get_string(),
                "aspect": fr.aspect_dropdown.get_selected_item().get_string(),
                "sign_side": fr.sign_side_dropdown.get_selected_item().get_string(),
                "sign": fr.sign_dropdown.get_selected_item().get_string(),
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
            # Transit grid filter state
            grid = self._transit_grid_view()
            if grid is not None:
                fr = grid.filter_row
                gf = config.get("grid_filter") or {}
                if "point" in gf:
                    fr.point_entry.set_text(str(gf["point"]))
                if "point_side" in gf:
                    self._set_dropdown_by_string(fr.point_side_dropdown, str(gf["point_side"]))
                if "aspect" in gf:
                    self._set_dropdown_by_string(fr.aspect_dropdown, str(gf["aspect"]))
                if "sign_side" in gf:
                    self._set_dropdown_by_string(fr.sign_side_dropdown, str(gf["sign_side"]))
                if "sign" in gf:
                    self._set_dropdown_by_string(fr.sign_dropdown, str(gf["sign"]))
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
            )
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
            view = build_planet_agg_table(rows)
            self._by_planet_scroll.set_child(view)
            self._status_bar.set_info(
                f"By planet for {person.get('name')} on {date} — {len(rows)} planets by relative value"
            )
        except Exception as exc:
            self._status_bar.set_info(f"By-planet error: {exc}")

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
            self._display_svg(svg, self._synastry_picture)
            count = len(result.get("cross_aspects", []))
            self._status_bar.set_info(
                f"Synastry: {person_a.get('name')} vs {person_b.get('name')} — {count} cross aspects"
            )
        except Exception as exc:
            self._status_bar.set_info(f"Synastry error: {exc}")

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
