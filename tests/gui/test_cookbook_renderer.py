"""test_cookbook_renderer.py — Headless verification of the Cookbook tab.

Covers the entry builder (natal placements → selectable rows with
grounded prose, missing keys flagged), the ListBox structure (sections,
selectable rows, detail pane), and selection behavior. Runs without a
display.
"""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from astro_gui.renderers.cookbook_renderer import (
    build_cookbook_list,
    natal_cookbook_entries,
    CookbookEntry,
)

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


class _FakeSnapshot:
    def __init__(self, bodies, aspects):
        self.bodies = bodies
        self.aspects = aspects


SNAPSHOT = _FakeSnapshot(
    bodies=[
        {"name": "Sun", "sign": "Sagittarius", "sign_degree": 8.7,
         "house": 5, "retrograde": False},
        {"name": "Moon", "sign": "Leo", "sign_degree": 27.3,
         "house": 2, "retrograde": False},
    ],
    aspects=[
        {"body_a": "Sun", "body_b": "Uranus", "aspect": "sextile", "orb": 0.8},
    ],
)

COOKBOOK = {
    "natal_signs": [
        {"body": "Sun", "sign": "Sagittarius", "text": "The Sun in Sagittarius explores."},
    ],
    "natal_houses": [
        {"body": "Sun", "house": 5, "text": "The Sun in the 5th house creates."},
    ],
    "natal_aspects": [
        {"body_a": "Sun", "body_b": "Uranus", "aspect": "sextile", "orb": 0.8,
         "text": "A sextile to the Sun offers opportunity."},
    ],
    "missing": ["natal-sign:Moon-Leo", "natal-house:Moon-2"],
}


def _entries_basic():
    entries = natal_cookbook_entries(SNAPSHOT, COOKBOOK)
    # Sun: one row (sign + house prose combined); Moon: one missing row;
    # aspect: one row; missing section: 2 rows
    assert len(entries) == 5, f"expected 5 entries, got {len(entries)}"
    sun = [e for e in entries if e.section == "Bodies" and "Sun" in e.title][0]
    assert "The Sun in Sagittarius explores." in sun.text
    assert "House 5: The Sun in the 5th house creates." in sun.text
    assert not sun.missing
    moon = [e for e in entries if e.section == "Bodies" and "Moon" in e.title][0]
    assert moon.missing, "Moon should be flagged missing"
    assert "do not guess" in moon.text.lower()
    asp = [e for e in entries if e.section == "Aspects"][0]
    assert asp.text == "A sextile to the Sun offers opportunity."
    missing_rows = [e for e in entries if e.section == "Missing"]
    assert len(missing_rows) == 2


check("natal entries: grounded prose, missing flagged, sections ordered", _entries_basic)


def _list_rows(listbox):
    """Iterate ListBox rows (GTK 4: no get_row_count)."""
    rows = []
    child = listbox.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.ListBoxRow):
            rows.append(child)
        child = child.get_next_sibling()
    return rows


def _list_structure():
    entries = natal_cookbook_entries(SNAPSHOT, COOKBOOK)
    view = build_cookbook_list(entries)
    win = _realize(view)
    listbox = view.listbox
    assert listbox is not None
    # Section headers (Bodies, Aspects, Missing) + 5 selectable rows
    rows = _list_rows(listbox)
    selectable = [r for r in rows if r.get_selectable()]
    assert len(selectable) == 5, f"expected 5 selectable rows, got {len(selectable)}"
    # Detail pane exists with placeholder text
    assert view.detail_label is not None
    assert "Select a placement" in view.detail_label.get_text()
    win.destroy()


check("cookbook list: sections + selectable rows + detail pane", _list_structure)


def _selection_shows_prose():
    entries = natal_cookbook_entries(SNAPSHOT, COOKBOOK)
    view = build_cookbook_list(entries)
    win = _realize(view)
    listbox = view.listbox
    # Find the Sun row (first selectable after the Bodies header)
    for row in _list_rows(listbox):
        if row.get_selectable() and "Sun" in getattr(row, "_entry", None).title:
            listbox.select_row(row)
            break
    for _ in range(10):
        while GLib.MainContext.default().iteration(False):
            pass
    text = view.detail_label.get_text()
    assert "The Sun in Sagittarius explores." in text, f"detail: {text!r}"
    win.destroy()


check("cookbook list: selecting a row shows its corpus prose", _selection_shows_prose)


def _missing_selection_warns():
    entries = natal_cookbook_entries(SNAPSHOT, COOKBOOK)
    view = build_cookbook_list(entries)
    win = _realize(view)
    listbox = view.listbox
    for row in _list_rows(listbox):
        if row.get_selectable() and getattr(row, "_entry", None).missing:
            listbox.select_row(row)
            break
    for _ in range(10):
        while GLib.MainContext.default().iteration(False):
            pass
    text = view.detail_label.get_text()
    assert "do not guess" in text.lower(), f"detail: {text!r}"
    win.destroy()


check("cookbook list: missing row warns instead of inventing prose", _missing_selection_warns)


print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
