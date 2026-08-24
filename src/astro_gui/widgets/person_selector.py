"""person_selector.py — PersonSelector widget with DropDown, New/Edit buttons."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

from astro_gui.api_client import AstroApiClient
from astro_gui.widgets.person_dialog import PersonDialog


# Family quick-access pin IDs
FAMILY_PIN_IDS = {5, 6}  # Xephyr, Rainy Phoenix Knight


class PersonSelector(Gtk.Box):
    """Top-row widget: DropDown populated from API + New / Edit buttons."""

    __gtype_name__ = "AstroPersonSelector"

    def __init__(self, client=None, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(12)
        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_hexpand(True)

        # Accept either the HTTP AstroApiClient or the library AstroClient;
        # both expose list_people() with the same response shape.
        self._client = client or AstroApiClient()
        self._people = []  # list of person dicts

        # Label
        label = Gtk.Label(label="Person:")
        label.set_xalign(0.0)
        self.append(label)

        # DropDown (use a StringList for names; keep parallel people list)
        self._names = Gtk.StringList()
        self._dropdown = Gtk.DropDown(model=self._names)
        self._dropdown.set_hexpand(True)
        self._dropdown.set_halign(Gtk.Align.FILL)
        self._dropdown.connect("notify::selected", self._on_selected)
        self.append(self._dropdown)

        # "+ New Person" button
        self._new_btn = Gtk.Button(label="+ New Person")
        self._new_btn.connect("clicked", self._on_new_clicked)
        self.append(self._new_btn)

        # "Edit" button
        self._edit_btn = Gtk.Button(label="Edit")
        self._edit_btn.connect("clicked", self._on_edit_clicked)
        self.append(self._edit_btn)

        # Load data from API
        self._load_people()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_people(self):
        try:
            resp = self._client.list_people()
            raw_people = resp.get("people", [])
        except Exception:
            raw_people = []

        # Sort: family pins first, then alphabetical
        def sort_key(p):
            pid = p.get("id")
            name = p.get("name", "")
            is_family = pid in FAMILY_PIN_IDS
            return (0 if is_family else 1, name.lower())

        self._people = sorted(raw_people, key=sort_key)

        # Populate StringList
        self._names.splice(0, self._names.get_n_items())
        for person in self._people:
            name = person.get("name", "Unknown")
            self._names.append(name)

        # Select first if available
        if self._people:
            self._dropdown.set_selected(0)
            # NOTE: Do NOT emit person-changed here. The caller (MainWindow)
            # connects its handler AFTER construction and triggers loading itself.

    # ------------------------------------------------------------------
    # Signals / callbacks
    # ------------------------------------------------------------------
    def _on_selected(self, dropdown, pspec):
        idx = dropdown.get_selected()
        if 0 <= idx < len(self._people):
            self.emit("person-changed", self._people[idx])

    def _on_new_clicked(self, btn):
        dialog = PersonDialog(
            parent=self.get_root(),
            title="New Person",
            person=None,
            chart=None,
        )
        dialog.present()
        dialog.connect("response", self._on_new_response)

    def _on_new_response(self, dialog, response_id):
        if response_id != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        values = dialog.get_values()
        dialog.destroy()
        if values is None:
            return
        try:
            self._save_person(values)
        except Exception as exc:
            self._show_error(f"Could not create person: {exc}")
            return
        self.refresh()

    def _on_edit_clicked(self, btn):
        person = self.get_selected_person()
        if person is None:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_root(),
                modal=True,
                buttons=Gtk.ButtonsType.OK,
                message_type=Gtk.MessageType.WARNING,
                text="No person selected.",
            )
            dialog.connect("response", lambda d, r: d.destroy())
            dialog.present()
            return
        chart = self._get_person_chart(person)
        dialog = PersonDialog(
            parent=self.get_root(),
            title=f"Edit {person.get('name', '???')}",
            person=person,
            chart=chart,
        )
        dialog.present()
        dialog.connect("response", self._on_edit_response)

    def _on_edit_response(self, dialog, response_id):
        if response_id != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        values = dialog.get_values()
        dialog.destroy()
        if values is None:
            return
        try:
            self._save_person(values)
        except Exception as exc:
            self._show_error(f"Could not update person: {exc}")
            return
        self.refresh()

    def _save_person(self, values):
        """Compute a natal chart and upsert the person in the store.

        Library AstroClient: natal(...) -> chart dict with chart_id, then
        create_person(name, chart_id) upserts by name. Legacy HTTP
        AstroApiClient: calculate_natal(...) then create_person(birth data).
        """
        client = self._client
        if hasattr(client, "natal"):
            chart = client.natal(
                name=values["name"],
                date=values["date"],
                time=values["time"],
                timezone=values["timezone"],
                latitude=values["latitude"],
                longitude=values["longitude"],
            )
            client.create_person(values["name"], chart["chart_id"])
            return
        # Legacy HTTP client path
        person_data = {
            "name": values["name"],
            "birth_date": values["date"],
            "birth_time": values["time"],
            "timezone": values["timezone"],
            "latitude": values["latitude"],
            "longitude": values["longitude"],
        }
        client.calculate_natal(person_data, options={"house_system": "K", "orb_preset": "Modern"})
        client.create_person(person_data)

    def _get_person_chart(self, person):
        """Return the stored natal chart for a person, or None."""
        chart_id = person.get("chart_id")
        if not chart_id:
            return None
        try:
            return self._client.get_chart(chart_id)
        except Exception:
            return None

    def _show_error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(),
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            message_type=Gtk.MessageType.ERROR,
            text=message,
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_selected_person(self):
        idx = self._dropdown.get_selected()
        if 0 <= idx < len(self._people):
            return self._people[idx]
        return None

    def select_person_by_id(self, person_id):
        """Select a person by id, emitting person-changed if found.

        Returns True when the selection changed, False when the id was not
        found or was already selected. Used by document-set restore to
        re-open the last active person on startup.
        """
        for idx, p in enumerate(self._people):
            if p.get("id") == person_id:
                if self._dropdown.get_selected() == idx:
                    return False
                self._dropdown.set_selected(idx)
                return True
        return False

    def refresh(self):
        """Reload the people list from the API."""
        self._load_people()

    # ------------------------------------------------------------------
    # GObject signal
    # ------------------------------------------------------------------
    @GObject.Signal(name="person-changed", arg_types=(GObject.TYPE_PYOBJECT,))
    def person_changed(self, person_dict):
        """Emitted whenever the DropDown selection changes."""
        pass
