"""window.py — MainWindow for the astrology GUI."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Gdk

from typing import Tuple

from astro_gui.widgets.person_selector import PersonSelector
from astro_gui.widgets.status_bar import StatusBar
from astro_gui.api_client import AstroApiClient
from astro_gui.renderers.wheel_renderer import WheelRenderer


class MainWindow(Gtk.ApplicationWindow):
    """Primary window: person selector, sidebar, notebook viewport, status bar."""

    __gtype_name__ = "AstroMainWindow"

    def __init__(self, app=None, **kwargs):
        super().__init__(application=app, **kwargs)
        self.set_title("Astrology Tool")
        self.set_default_size(1200, 800)

        self._client = AstroApiClient()
        self._renderer = WheelRenderer(width=600, height=600)
        self._selected_person = None
        self._all_people = []

        # Root vertical box
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(root_box)

        # --- Top: Person Selector ---
        self._person_selector = PersonSelector()
        self._person_selector.set_hexpand(True)
        self._person_selector.connect("person-changed", self._on_person_changed)
        root_box.append(self._person_selector)

        # --- Middle: Paned sidebar + notebook ---
        self._paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned.set_vexpand(True)
        self._paned.set_hexpand(True)
        self._paned.set_wide_handle(True)
        root_box.append(self._paned)

        # Left sidebar placeholder
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

        # Trigger initial chart load now that all widgets exist and handler is connected
        first_person = self._person_selector.get_selected_person()
        if first_person:
            self._on_person_changed(self._person_selector, first_person)

    # ------------------------------------------------------------------
    # Sidebar placeholder
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

        # Placeholder buttons for future navigation controls
        btn_natal = Gtk.Button(label="Natal")
        btn_natal.connect("clicked", lambda _b: self._show_natal_wheel())
        sidebar_box.append(btn_natal)

        btn_transit = Gtk.Button(label="Transit")
        btn_transit.connect("clicked", lambda _b: self._show_transit_wheel())
        sidebar_box.append(btn_transit)

        btn_synastry = Gtk.Button(label="Synastry")
        btn_synastry.connect("clicked", lambda _b: self._show_synastry_wheel())
        sidebar_box.append(btn_synastry)

        btn_horary = Gtk.Button(label="Horary")
        sidebar_box.append(btn_horary)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar_box.append(spacer)

        return sidebar_box

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
        # Build transit controls overlay (top of scroll)
        self._transit_scroll.set_child(self._transit_picture)
        # Controls go above — use a vertical box inside scroll
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

        notebook.set_current_page(0)
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
        # Get selected person B from dropdown
        selected = self._synastry_dropdown.get_selected_item()
        if not selected:
            self._status_bar.set_info("Select Person B")
            return
        # The dropdown items are GObject strings; get string value
        person_b_name = selected.get_string()
        # Find matching person dict
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
        self._notebook.set_current_page(0)
        person = self._person_selector.get_selected_person()
        if person:
            self._load_natal_chart(person)

    def _show_transit_wheel(self):
        """Switch to the Transit Wheel tab and refresh."""
        self._notebook.set_current_page(1)
        self._refresh_transit()

    def _show_synastry_wheel(self):
        """Switch to the Synastry Wheel tab."""
        self._notebook.set_current_page(2)

    # ------------------------------------------------------------------
    # Person list management
    # ------------------------------------------------------------------
    def _fetch_all_people(self):
        """Populate _all_people and synastry dropdown from API."""
        try:
            result = self._client.list_people()
            if result.get("status") == "ok":
                self._all_people = result.get("people", [])
                names = [p.get("name", "?") for p in self._all_people]
                str_list = GObject.Value(GObject.TYPE_OBJECT, None)
                model = Gtk.StringList.new(names)
                self._synastry_dropdown.set_model(model)
                # Select second person by default if available
                if len(names) > 1:
                    self._synastry_dropdown.set_selected(1)
        except Exception as exc:
            self._status_bar.set_info(f"People fetch error: {exc}")

    # ------------------------------------------------------------------
    # Chart loading
    # ------------------------------------------------------------------
    def _on_person_changed(self, selector, person_dict):
        self._selected_person = person_dict
        name = person_dict.get("name", "Unknown")
        self._status_bar.set_info(f"Loading chart for {name}...")
        self._load_natal_chart(person_dict)
        # Also refresh synastry dropdown index to avoid self-comparison
        for i, p in enumerate(self._all_people):
            if p.get("id") == person_dict.get("id"):
                # Pick next person as default B if available
                next_idx = (i + 1) % len(self._all_people) if len(self._all_people) > 1 else 0
                self._synastry_dropdown.set_selected(next_idx)
                break

    def _load_natal_chart(self, person_dict):
        try:
            chart = self._client.calculate_natal(person_dict)
            if chart.get("status") != "ok":
                self._status_bar.set_info(f"Error: {chart.get('message', 'Unknown')}")
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

    def _load_transit_chart(self, person_dict):
        """Fetch transit data and render two-ring transit wheel."""
        try:
            pid = person_dict.get("id")
            natal_chart = self._client.get_natal_chart_for_person(pid)
            if not natal_chart:
                self._status_bar.set_info(f"No persisted natal chart for {person_dict.get('name')}")
                return
            chart_id = natal_chart.get("chart_id")
            date = self._transit_date.get_text()
            time = self._transit_time.get_text()
            result = self._client.get_transit(chart_id, date, time)
            if result.get("status") != "ok":
                self._status_bar.set_info(f"Transit error: {result.get('message', 'Unknown')}")
                return
            # Build natal + transit merged chart for renderer
            natal_data = {
                "angles": natal_chart.get("positions", {}).get("angles", {}),
                "houses": natal_chart.get("positions", {}).get("houses", []),
                "bodies": result.get("bodies", []),
                "aspects": natal_chart.get("aspects", []),
            }
            transit_data = {"bodies": result.get("transiting_bodies", [])}
            svg = self._renderer.render_transit(natal_data, transit_data)
            self._display_svg(svg, self._transit_picture)
            count = len(result.get("cross_aspects", []))
            self._status_bar.set_info(
                f"Transit for {person_dict.get('name')} on {date} {time} — {count} cross aspects"
            )
        except Exception as exc:
            self._status_bar.set_info(f"Transit error: {exc}")

    def _load_synastry_chart(self, person_a, person_b):
        """Fetch synastry data and render two-ring synastry wheel."""
        try:
            chart_a = self._client.get_natal_chart_for_person(person_a.get("id"))
            chart_b = self._client.get_natal_chart_for_person(person_b.get("id"))
            if not chart_a or not chart_b:
                missing = "A" if not chart_a else "B"
                self._status_bar.set_info(f"No persisted natal chart for person {missing}")
                return
            result = self._client.get_synastry(
                chart_a.get("chart_id"), chart_b.get("chart_id")
            )
            if result.get("status") != "ok":
                self._status_bar.set_info(f"Synastry error: {result.get('message', 'Unknown')}")
                return
            a_data = {
                "angles": chart_a.get("positions", {}).get("angles", {}),
                "houses": chart_a.get("positions", {}).get("houses", []),
                "bodies": chart_a.get("positions", {}).get("bodies", []),
            }
            b_data = {
                "bodies": chart_b.get("positions", {}).get("bodies", []),
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
