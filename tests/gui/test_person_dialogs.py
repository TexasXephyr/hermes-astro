"""test_person_dialogs.py — Headless verification of New Person / Edit dialogs.

Covers PersonDialog validation (strict date/time, lat/lon ranges, IANA
timezone, error label keeps dialog open) and the PersonSelector save path
(create + edit upsert via the library AstroClient, list refresh). Runs
without a display (GTK widgets instantiate headless).
"""
import sys
sys.path.insert(0, "/home/xephyr/astro/src")

import os
import tempfile

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
