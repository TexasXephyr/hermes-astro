"""test_person_dialogs.py — Headless verification of New Person / Edit dialogs.

Covers PersonDialog validation (strict date/time, lat/lon ranges, IANA
timezone, error label keeps dialog open) and the PersonSelector save path
(create + edit upsert via the library AstroClient, list refresh). Runs
without a display (GTK widgets instantiate headless).
"""
import sys
sys.path.insert(0, "/home/xephyr/astro/src")

import json
import os
import tempfile
import unittest.mock
import urllib.error

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from astro_api_client import AstroClient
from astro_gui.widgets.person_dialog import PersonDialog
from astro_gui.widgets.person_selector import PersonSelector

passed = 0
failed = 0


def check(label, expr):
    global passed, failed
    try:
        expr()
        print(f"PASS {label}")
        passed += 1
    except Exception as exc:
        print(f"FAIL {label} — {exc}")
        failed += 1


# ------------------------------------------------------------------
# 1. PersonDialog: validation
# ------------------------------------------------------------------
def _fill(dialog, name="Test Person", date="2000-01-01", time="12:00:00",
          tz="America/Los_Angeles", lat="44.0521", lon="-123.0868"):
    dialog._name_entry.set_text(name)
    dialog._date_entry.set_text(date)
    dialog._time_entry.set_text(time)
    dialog._tz_entry.set_text(tz)
    dialog._lat_entry.set_text(lat)
    dialog._lon_entry.set_text(lon)


def _valid_values():
    d = PersonDialog()
    _fill(d)
    d.response(Gtk.ResponseType.OK)
    values = d.get_values()
    assert values is not None, "valid input should produce values"
    assert values["name"] == "Test Person"
    assert values["date"] == "2000-01-01"
    assert values["time"] == "12:00:00"
    assert values["timezone"] == "America/Los_Angeles"
    assert values["latitude"] == 44.0521
    assert values["longitude"] == -123.0868
    d.destroy()


check("valid input produces values", _valid_values)


def _invalid_keeps_open():
    d = PersonDialog()
    _fill(d, date="2000/01/01")
    d.present()
    d.response(Gtk.ResponseType.OK)
    # Error label shown, dialog still visible, no values
    assert d.get_values() is None
    assert d._error_label.get_visible() is True
    assert d.get_visible() is True, "dialog must stay open on validation error"
    d.destroy()


check("bad date shows error and keeps dialog open", _invalid_keeps_open)


def _bad_time():
    d = PersonDialog()
    _fill(d, time="25:00:00")
    d.response(Gtk.ResponseType.OK)
    assert d.get_values() is None
    assert "HH:MM:SS" in d._error_label.get_text()
    d.destroy()


check("bad time rejected", _bad_time)


def _bad_lat_lon():
    d = PersonDialog()
    _fill(d, lat="95", lon="-200")
    d.response(Gtk.ResponseType.OK)
    assert d.get_values() is None
    assert "Latitude" in d._error_label.get_text()
    d.destroy()


check("out-of-range lat/lon rejected", _bad_lat_lon)


def _bad_tz():
    d = PersonDialog()
    _fill(d, tz="Not/AZone")
    d.response(Gtk.ResponseType.OK)
    assert d.get_values() is None
    assert "timezone" in d._error_label.get_text().lower()
    d.destroy()


check("unknown timezone rejected", _bad_tz)


def _empty_name():
    d = PersonDialog()
    _fill(d, name="   ")
    d.response(Gtk.ResponseType.OK)
    assert d.get_values() is None
    assert "Name" in d._error_label.get_text()
    d.destroy()


check("empty name rejected", _empty_name)


def _cancel_no_values():
    d = PersonDialog()
    _fill(d)
    d.response(Gtk.ResponseType.CANCEL)
    assert d.get_values() is None
    d.destroy()


check("cancel yields no values", _cancel_no_values)


# ------------------------------------------------------------------
# 2. PersonDialog: edit prefill from chart meta
# ------------------------------------------------------------------
def _prefill_from_chart():
    chart = {
        "meta": {
            "name": "Xephyr",
            "birth_date": "1990-06-15",
            "birth_time": "08:30:00",
            "timezone": "America/Los_Angeles",
            "latitude": 44.0521,
            "longitude": -123.0868,
        }
    }
    d = PersonDialog(person={"id": 1, "name": "Xephyr", "chart_id": "x"}, chart=chart)
    assert d._name_entry.get_text() == "Xephyr"
    assert d._date_entry.get_text() == "1990-06-15"
    assert d._time_entry.get_text() == "08:30:00"
    assert d._tz_entry.get_text() == "America/Los_Angeles"
    assert d._lat_entry.get_text() == "44.0521"
    assert d._lon_entry.get_text() == "-123.0868"
    d.destroy()


check("edit dialog prefills from chart meta", _prefill_from_chart)


# ------------------------------------------------------------------
# 2b. PersonDialog: location search fills lat/lon (mock Nominatim)
# ------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, payload, status=200):
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_urlopen(payload, responses=None):
    """Patch for urlopen. payload is the search response; responses is an
    optional list of reverse-geocode responses consumed in order after
    the search (one reverse call per missing timezone)."""
    def opener(request, timeout=None):
        if request.full_url.startswith(PersonDialog.REVERSE_URL):
            if responses:
                return _FakeResponse(responses.pop(0))
            return _FakeResponse({})
        return _FakeResponse(payload)
    return opener


def _search_fills_coords():
    d = PersonDialog()
    _fill(d)
    d._location_entry.set_text("Portland, OR")
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen",
        _fake_urlopen([{"lat": "45.5152", "lon": "-122.6784"}]),
    ):
        d._on_search_clicked()
    assert d._lat_entry.get_text() == "45.515200", d._lat_entry.get_text()
    assert d._lon_entry.get_text() == "-122.678400", d._lon_entry.get_text()
    assert d._search_label.get_visible() is True
    assert "Found" in d._search_label.get_text()
    assert "could not determine timezone" in d._search_label.get_text()
    # Validation still works with the filled values
    d.response(Gtk.ResponseType.OK)
    values = d.get_values()
    assert values is not None, "lat/lon filled by search must validate"
    assert abs(values["latitude"] - 45.5152) < 1e-6
    assert abs(values["longitude"] - -122.6784) < 1e-6
    d.destroy()


check("location search fills lat/lon", _search_fills_coords)


def _search_fills_timezone_from_hit() -> None:
    """Search hit carries timezone -> fill it, no reverse request."""
    d = PersonDialog()
    _fill(d, tz="Europe/Paris")
    d._location_entry.set_text("Paris, France")
    opener = _fake_urlopen(
        [{"lat": "48.8566", "lon": "2.3522", "timezone": "Europe/Paris"}],
    )
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen",
        unittest.mock.Mock(wraps=opener),
    ) as mock_urlopen:
        d._on_search_clicked()
    mock_urlopen.assert_called_once()
    assert d._tz_entry.get_text() == "Europe/Paris"
    assert "could not determine" not in d._search_label.get_text()
    assert "Europe/Paris" in d._search_label.get_text()
    d.destroy()


check("search result timezone fills the tz field", _search_fills_timezone_from_hit)


def _search_invalid_timezone_not_filled() -> None:
    """Invalid timezone from Nominatim is not written to the field."""
    d = PersonDialog()
    _fill(d, tz="America/Los_Angeles")
    d._location_entry.set_text("Mars Colony")
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen",
        _fake_urlopen([{"lat": "45.5", "lon": "-122.6", "timezone": "Mars/Olympus"}]),
    ):
        d._on_search_clicked()
    assert d._tz_entry.get_text() == "America/Los_Angeles", "invalid tz must not overwrite"
    assert "could not determine timezone" in d._search_label.get_text()
    d.destroy()


check("invalid tz from Nominatim does not overwrite the field", _search_invalid_timezone_not_filled)


def _search_reverse_timezone_fallback() -> None:
    """No timezone on search hit -> one reverse request fills it."""
    d = PersonDialog()
    _fill(d, tz="UTC")
    d._location_entry.set_text("Portland, OR")
    opener = _fake_urlopen(
        [{"lat": "45.5152", "lon": "-122.6784"}],
        responses=[{"timezone": "America/Los_Angeles"}],
    )
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen",
        unittest.mock.Mock(wraps=opener),
    ) as mock_urlopen:
        d._on_search_clicked()
    # Search (no tz) + one reverse request
    assert mock_urlopen.call_count == 2
    assert d._tz_entry.get_text() == "America/Los_Angeles"
    assert "could not determine" not in d._search_label.get_text()
    d.destroy()


check("reverse geocode fallback fills timezone", _search_reverse_timezone_fallback)


def _search_reverse_network_error_keeps_timezone() -> None:
    """Reverse failure leaves the timezone field untouched, notes it."""
    d = PersonDialog()
    _fill(d, tz="America/New_York")
    d._location_entry.set_text("New York, NY")
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen",
        _fake_urlopen([{"lat": 40.7128, "lon": -74.0060}]),
    ):
        d._on_search_clicked()
    assert d._tz_entry.get_text() == "America/New_York"
    assert "could not determine timezone" in d._search_label.get_text()
    d.destroy()


check("reverse failure keeps timezone and shows note", _search_reverse_network_error_keeps_timezone)


def _search_no_results():
    d = PersonDialog()
    d._location_entry.set_text("zzz nowhere")
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen",
        _fake_urlopen([]),
    ):
        d._on_search_clicked()
    assert "No results" in d._search_label.get_text()
    assert d._lat_entry.get_text() == ""
    d.present()
    assert d.get_visible() is True
    d.destroy()


check("location search no results shows error, keeps dialog", _search_no_results)


def _search_network_error():
    d = PersonDialog()
    d._location_entry.set_text("Portland, OR")
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen",
        unittest.mock.Mock(side_effect=urllib.error.URLError("boom")),
    ):
        d._on_search_clicked()
    assert "failed" in d._search_label.get_text().lower()
    assert d._lat_entry.get_text() == ""
    d.present()
    assert d.get_visible() is True
    d.destroy()


check("location search network error shows error, keeps dialog", _search_network_error)


def _search_invalid_response():
    d = PersonDialog()
    d._location_entry.set_text("Portland, OR")
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen",
        _fake_urlopen({"not": "a list"}),
    ):
        d._on_search_clicked()
    assert "failed" in d._search_label.get_text().lower()
    assert d._lat_entry.get_text() == ""
    d.destroy()


check("location search invalid response shows error", _search_invalid_response)


def _search_empty_query():
    d = PersonDialog()
    with unittest.mock.patch(
        "astro_gui.widgets.person_dialog.urllib.request.urlopen"
    ) as mock_urlopen:
        d._on_search_clicked()
    mock_urlopen.assert_not_called()
    assert "Enter a location" in d._search_label.get_text()
    d.destroy()


check("location search empty query does not hit network", _search_empty_query)


# ------------------------------------------------------------------
# 3. PersonSelector: save path (create + edit) against a temp library
# ------------------------------------------------------------------
def _create_and_edit_person():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HOME"] = tmp
        client = AstroClient()
        sel = PersonSelector(client=client)
        try:
            # New person via the same code path the dialog uses
            values = {
                "name": "Dialog Test Person",
                "date": "1985-03-20",
                "time": "06:15:00",
                "timezone": "UTC",
                "latitude": 51.5074,
                "longitude": -0.1278,
            }
            sel._save_person(values)
            people = client.list_people().get("people", [])
            match = next((p for p in people if p["name"] == "Dialog Test Person"), None)
            assert match is not None, "person should exist after save"
            chart = client.get_chart(match["chart_id"])
            meta = chart["meta"]
            assert meta["birth_date"] == "1985-03-20"
            assert meta["birth_time"] == "06:15:00"
            assert meta["timezone"] == "UTC"
            assert abs(meta["latitude"] - 51.5074) < 1e-6
            assert abs(meta["longitude"] - -0.1278) < 1e-6

            # Edit: same name, new birth data -> upsert keeps one row, new chart
            values2 = {
                "name": "Dialog Test Person",
                "date": "1985-03-21",
                "time": "07:00:00",
                "timezone": "Europe/London",
                "latitude": 51.5,
                "longitude": -0.1,
            }
            sel._save_person(values2)
            people2 = client.list_people().get("people", [])
            matches2 = [p for p in people2 if p["name"] == "Dialog Test Person"]
            assert len(matches2) == 1, "upsert must not duplicate the person"
            chart2 = client.get_chart(matches2[0]["chart_id"])
            assert chart2["meta"]["birth_date"] == "1985-03-21"
            assert chart2["meta"]["timezone"] == "Europe/London"
        finally:
            sel.close() if hasattr(sel, "close") else None


check("save path creates and edits a person (upsert)", _create_and_edit_person)


def _refresh_after_save():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HOME"] = tmp
        client = AstroClient()
        sel = PersonSelector(client=client)
        try:
            assert len(sel._people) == 0
            values = {
                "name": "Refresh Me",
                "date": "1999-12-31",
                "time": "23:59:59",
                "timezone": "UTC",
                "latitude": 0.0,
                "longitude": 0.0,
            }
            sel._save_person(values)
            sel.refresh()
            assert len(sel._people) == 1
            assert sel._people[0]["name"] == "Refresh Me"
            assert sel.get_selected_person()["name"] == "Refresh Me"
        finally:
            sel.close() if hasattr(sel, "close") else None


check("refresh reloads the person list after save", _refresh_after_save)


print(f"\nResults: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
