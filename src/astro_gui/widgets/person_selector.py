"""person_selector.py — PersonSelector widget with DropDown, New/Edit buttons."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject

from astro_gui.api_client import AstroApiClient


# Family quick-access pin IDs
FAMILY_PIN_IDS = {5, 6}  # Xephyr, Rainy Phoenix Knight


class PersonSelector(Gtk.Box):
    """Top-row widget: DropDown populated from API + New / Edit buttons."""

    __gtype_name__ = "AstroPersonSelector"

    def __init__(self, client: AstroApiClient = None, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(12)
        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_hexpand(True)

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
        # Placeholder: open a dialog in a later sprint
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(),
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            message_type=Gtk.MessageType.INFO,
            text="New Person dialog is not yet implemented.",
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

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
        # Placeholder: open an edit dialog in a later sprint
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(),
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            message_type=Gtk.MessageType.INFO,
            text=f"Edit dialog for {person.get('name', '???')} is not yet implemented.",
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
