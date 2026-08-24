"""test_calendar_renderer.py — Headless verification of the Calendar tab.

Covers the calendar event list builder (columns, default date sort,
visible sort buttons in the realized tree), the CSV row builder, and the
ICS string exporter. Runs without a display.
"""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from astro_gui.renderers.calendar_renderer import (
    build_calendar_view,
    calendar_csv_rows,
    CALENDAR_CSV_COLUMNS,
)
from astro_analyze.calendar import export_to_ics_string

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


def _find_column_view(widget):
    if isinstance(widget, Gtk.ColumnView):
        return widget
    if isinstance(widget, Gtk.Box):
        for child in widget:
            found = _find_column_view(child)
            if found is not None:
                return found
    return None


def _realize(widget):
    win = Gtk.Window()
    sw = Gtk.ScrolledWindow()
    sw.set_child(widget)
    win.set_child(sw)
    win.present()
    for _ in range(30):
        while GLib.MainContext.default().iteration(False):
            pass
    return win


EVENTS = [
    {"date": "2026-09-05", "transiting_body": "Saturn", "natal_body": "Sun",
     "aspect": "conjunction", "orb": 0.4, "applying": True, "priority": 210},
    {"date": "2026-08-30", "transiting_body": "Mars", "natal_body": "Moon",
     "aspect": "square", "orb": 1.2, "applying": False, "priority": 96},
    {"date": "2026-09-01", "transiting_body": "Jupiter", "natal_body": "Venus",
     "aspect": "trine", "orb": 0.8, "applying": True, "priority": 130},
]


def _view_basics():
    view = build_calendar_view(EVENTS)
    cv = _find_column_view(view)
    assert cv is not None, "no ColumnView in calendar view"
    titles = [c.get_title() for c in cv.get_columns()]
    assert titles == ["Date", "Body", "Aspect", "Natal", "Orb", "Applying", "Priority"], \
        f"columns: {titles}"
    # Default sort: date ascending → first row is the earliest date
    model = cv.get_model()
    assert model is not None
    first = model.get_item(0)
    assert first.date == "2026-08-30", f"default sort first row: {first.date}"
    # Sort buttons row present in the realized tree
    win = _realize(view)
    assert hasattr(cv, "_sort_row"), "no _sort_row on calendar view"
    assert cv._sort_row.get_first_child() is not None, "sort row empty"
    win.destroy()


check("calendar view: 7 columns, default date-ascending sort, sort row realized",
      _view_basics)


def _sort_buttons_work():
    view = build_calendar_view(EVENTS)
    cv = _find_column_view(view)
    model = cv.get_model()
    # Click the Priority sort button → descending priority first
    btn = cv._sort_buttons["Priority"]
    btn.emit("clicked")
    first = model.get_item(0)
    assert first.priority == "210", f"priority sort first row: {first.priority}"
    # Re-click inverts → ascending priority first
    btn.emit("clicked")
    first = model.get_item(0)
    assert first.priority == "96", f"priority sort inverted first row: {first.priority}"


check("calendar view: sort buttons sort + invert by priority", _sort_buttons_work)


def _csv_rows():
    rows = calendar_csv_rows(EVENTS)
    assert len(rows) == 3
    assert rows[0]["Date"] == "2026-09-05"
    assert rows[0]["Body"] == "Saturn"
    assert rows[0]["Aspect"] == "conjunction"
    assert rows[0]["Natal"] == "Sun"
    assert rows[0]["Orb"] == "0.40"
    assert rows[0]["Applying"] == "1"
    assert rows[0]["Priority"] == "210"
    assert CALENDAR_CSV_COLUMNS == ["Date", "Body", "Aspect", "Natal", "Orb", "Applying", "Priority"]


check("calendar CSV rows: fields match the view columns", _csv_rows)


def _ics_string():
    ics = export_to_ics_string(EVENTS)
    assert ics.startswith("BEGIN:VCALENDAR\r\n"), "missing calendar header"
    assert ics.rstrip().endswith("END:VCALENDAR"), "missing calendar footer"
    assert ics.count("BEGIN:VEVENT") == 3, f"VEVENT count: {ics.count('BEGIN:VEVENT')}"
    assert "DTSTART;VALUE=DATE:20260905" in ics, "DTSTART format wrong"
    assert "SUMMARY:Saturn conjunction natal Sun" in ics, "summary missing"
    assert "TRANSP:TRANSPARENT" in ics, "transp missing"
    # UIDs unique
    uids = [l for l in ics.splitlines() if l.startswith("UID:")]
    assert len(uids) == len(set(uids)), "duplicate UIDs"


check("ICS string: header/footer, VEVENTs, DTSTART, summary, unique UIDs", _ics_string)


def _ics_escaping():
    evil = [{"date": "2026-09-05", "transiting_body": "Saturn, Jr", "natal_body": "Sun",
             "aspect": "conjunction", "orb": 0.4, "applying": True, "priority": 1}]
    ics = export_to_ics_string(evil)
    assert "Saturn\\, Jr" in ics, "comma not escaped in ICS summary"


check("ICS string: special chars escaped", _ics_escaping)


print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
