"""person_dialog.py — New Person / Edit Person dialogs for the astrology GUI."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

import json
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime
from zoneinfo import available_timezones


class PersonDialog(Gtk.Dialog):
    """Modal dialog for creating or editing a person's birth data.

    Fields: Name, Birth Date (YYYY-MM-DD), Birth Time (HH:MM:SS),
    Timezone (IANA), Latitude, Longitude, plus a Location search that
    geocodes via Nominatim and fills Latitude/Longitude. Validation
    errors are shown in an error label and keep the dialog open.
    Geocoding failures (network, no results, invalid response) are
    shown in a search label and never close the dialog.
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

        # Location search row: geocodes via Nominatim and fills lat/lon.
        search_row = len(rows)
        self._location_entry = Gtk.Entry()
        self._location_entry.set_placeholder_text("e.g. Portland, OR")
        self._location_entry.connect("activate", self._on_search_clicked)
        self._search_btn = Gtk.Button(label="Search")
        self._search_btn.connect("clicked", self._on_search_clicked)
        loc_lbl = Gtk.Label(label="Location")
        loc_lbl.set_xalign(0.0)
        grid.attach(loc_lbl, 0, search_row, 1, 1)
        grid.attach(self._location_entry, 1, search_row, 1, 1)
        grid.attach(self._search_btn, 2, search_row, 1, 1)

        # Search feedback label (geocode errors / success), never fatal.
        self._search_label = Gtk.Label(label="")
        self._search_label.set_visible(False)
        self._search_label.set_wrap(True)
        self._search_label.set_xalign(0.0)
        grid.attach(self._search_label, 0, search_row + 1, 3, 1)

        self._error_label = Gtk.Label(label="")
        self._error_label.set_visible(False)
        self._error_label.add_css_class("error")
        self._error_label.set_wrap(True)
        self._error_label.set_xalign(0.0)
        grid.attach(self._error_label, 0, search_row + 2, 3, 1)

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
    # Location search (Nominatim geocoding)
    # ------------------------------------------------------------------
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    USER_AGENT = "astro-gui/0.5 (personal use)"

    def _on_search_clicked(self, _widget=None):
        """Geocode the Location entry and fill Latitude/Longitude.

        Failures (network, no results, invalid response) are shown in
        the search label; the dialog is never closed or crashed.
        """
        query = self._location_entry.get_text().strip()
        if not query:
            self._set_search_message("Enter a location to search for.", error=True)
            return
        self._set_search_message("Searching\u2026", error=False)
        try:
            result = self._geocode(query)
        except Exception as exc:
            self._set_search_message(f"Location search failed: {exc}", error=True)
            return
        if result is None:
            self._set_search_message("No results for that location.", error=True)
            return
        lat, lon = result
        self._lat_entry.set_text(f"{lat:.6f}")
        self._lon_entry.set_text(f"{lon:.6f}")
        self._set_search_message(f"Found: {lat:.6f}, {lon:.6f}", error=False)

    def _geocode(self, query):
        """Return (lat, lon) floats for query, or None when no results."""
        params = urllib.parse.urlencode({"format": "json", "q": query, "limit": 1})
        url = f"{self.NOMINATIM_URL}?{params}"
        request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Nominatim HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error: {exc.reason}") from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError("Invalid response from Nominatim.") from exc
        if not isinstance(payload, list):
            raise RuntimeError("Invalid response from Nominatim.")
        if not payload:
            return None
        hit = payload[0]
        if not isinstance(hit, dict) or "lat" not in hit or "lon" not in hit:
            raise RuntimeError("Invalid response from Nominatim.")
        try:
            lat = float(hit["lat"])
            lon = float(hit["lon"])
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Invalid coordinates from Nominatim.") from exc
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise RuntimeError("Invalid coordinates from Nominatim.")
        return lat, lon

    def _set_search_message(self, message, error=False):
        self._search_label.set_text(message)
        self._search_label.set_visible(True)
        self._search_label.set_css_classes(["error"] if error else [])
        self._search_label.set_tooltip_text(message)

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
