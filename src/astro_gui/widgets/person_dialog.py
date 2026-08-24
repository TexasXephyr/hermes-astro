"""person_dialog.py — New Person / Edit Person dialogs for the astrology GUI."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from datetime import datetime
from zoneinfo import available_timezones


class PersonDialog(Gtk.Dialog):
    """Modal dialog for creating or editing a person's birth data.

    Fields: Name, Birth Date (YYYY-MM-DD), Birth Time (HH:MM:SS),
    Timezone (IANA), Latitude, Longitude. Validation errors are shown
    in an error label and keep the dialog open.
    """

    __gtype_name__ = "AstroPersonDialog"

    def __init__(self, parent=None, title="Person", person=None, chart=None):
        super().__init__()
        self.set_title(title)
        if parent is not None:
            self.set_transient_for(parent)
        self.set_modal(True)

        self._person = person  # {id, name, chart_id} or None for new
        self._chart = chart    # natal chart dict (edit prefill) or None
        self._values = None

        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        content = self.get_content_area()
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)

        self._name_entry = Gtk.Entry()
        self._date_entry = Gtk.Entry()
        self._time_entry = Gtk.Entry()
        self._tz_entry = Gtk.Entry()
        self._lat_entry = Gtk.Entry()
        self._lon_entry = Gtk.Entry()

        rows = [
            ("Name", self._name_entry),
            ("Birth Date (YYYY-MM-DD)", self._date_entry),
            ("Birth Time (HH:MM:SS)", self._time_entry),
            ("Timezone (IANA)", self._tz_entry),
            ("Latitude", self._lat_entry),
            ("Longitude", self._lon_entry),
        ]
        for i, (label, entry) in enumerate(rows):
            lbl = Gtk.Label(label=label)
            lbl.set_xalign(0.0)
            grid.attach(lbl, 0, i, 1, 1)
            grid.attach(entry, 1, i, 1, 1)

        self._error_label = Gtk.Label(label="")
        self._error_label.set_visible(False)
        self._error_label.add_css_class("error")
        self._error_label.set_wrap(True)
        self._error_label.set_xalign(0.0)
        grid.attach(self._error_label, 0, len(rows), 2, 1)

        content.append(grid)

        if person is not None:
            self._prefill(person, chart)

        # Keep the dialog open on validation errors: stop the response
        # emission before GtkDialog's default handler hides the dialog.
        self.connect("response", self._on_response)

    # ------------------------------------------------------------------
    # Prefill
    # ------------------------------------------------------------------
    def _prefill(self, person, chart):
        self._name_entry.set_text(person.get("name", ""))
        meta = (chart or {}).get("meta", {})
        if meta.get("birth_date"):
            self._date_entry.set_text(str(meta["birth_date"]))
        if meta.get("birth_time"):
            self._time_entry.set_text(str(meta["birth_time"]))
        if meta.get("timezone"):
            self._tz_entry.set_text(str(meta["timezone"]))
        if meta.get("latitude") is not None:
            self._lat_entry.set_text(f"{meta['latitude']:.4f}")
        if meta.get("longitude") is not None:
            self._lon_entry.set_text(f"{meta['longitude']:.4f}")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate(self):
        """Return (values, error). values is a dict or None; error a str or None."""
        name = self._name_entry.get_text().strip()
        date = self._date_entry.get_text().strip()
        time = self._time_entry.get_text().strip()
        tz = self._tz_entry.get_text().strip()
        lat_s = self._lat_entry.get_text().strip()
        lon_s = self._lon_entry.get_text().strip()

        if not name:
            return None, "Name is required."
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return None, "Birth Date must be YYYY-MM-DD."
        try:
            datetime.strptime(time, "%H:%M:%S")
        except ValueError:
            return None, "Birth Time must be HH:MM:SS."
        if tz not in available_timezones():
            return None, f"Unknown timezone: {tz}"
        try:
            lat = float(lat_s)
        except ValueError:
            return None, "Latitude must be a number."
        try:
            lon = float(lon_s)
        except ValueError:
            return None, "Longitude must be a number."
        if not -90.0 <= lat <= 90.0:
            return None, "Latitude must be in [-90, 90]."
        if not -180.0 <= lon <= 180.0:
            return None, "Longitude must be in [-180, 180]."

        return {
            "name": name,
            "date": date,
            "time": time,
            "timezone": tz,
            "latitude": lat,
            "longitude": lon,
        }, None

    def _on_response(self, dialog, response_id):
        if response_id != Gtk.ResponseType.OK:
            return
        values, error = self._validate()
        if error is not None:
            self._error_label.set_text(error)
            self._error_label.set_visible(True)
            self.stop_emission_by_name("response")
            return
        self._error_label.set_visible(False)
        self._values = values

    def get_values(self):
        """Return the validated values dict, or None if not validated."""
        return self._values
