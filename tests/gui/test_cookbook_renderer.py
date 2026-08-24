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
    transit_cookbook_entries,
    synastry_cookbook_entries,
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


def _realize(widget, width=900, height=700):
    """Realize a widget inside a sized window and pump the main loop.

    A fixed window size matters for wrap-dependent layout (the cookbook
    detail label): inside a bare ScrolledWindow the content gets
    unbounded width and never wraps, which is not how the real window
    lays it out.
    """
    win = Gtk.Window()
    win.set_default_size(width, height)
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


def _detail_grows_with_content():
    """The detail pane must be above the list and sized to its content
    (variable depth) — no fixed cap that clips the prose.

    Measures the label's natural height at a bounded width (the way the
    real notebook constrains it) using the markup path the selection
    handler uses. A short entry must measure shorter than a long one.
    """
    short_entry = CookbookEntry(title="Short", subtitle="", text="One line.")
    long_text = "Long prose. " * 40
    long_entry = CookbookEntry(title="Long", subtitle="", text=long_text)

    def _markup(entry):
        return f"<b>{entry.title}</b>\n\n{entry.text}"

    def _measure(entry, width):
        view = build_cookbook_list([entry])
        view.detail_label.set_markup(_markup(entry))
        return view.detail_label.measure(Gtk.Orientation.VERTICAL, width)[1]

    width = 600  # typical panel width in the real window
    short_height = _measure(short_entry, width)
    long_height = _measure(long_entry, width)

    assert long_height > short_height, (
        f"detail pane not variable depth: short={short_height} long={long_height}"
    )
    # Detail pane must sit ABOVE the list: the first child of the box is
    # the detail label, the second is the list's ScrolledWindow.
    view = build_cookbook_list([short_entry])
    first_child = view.get_first_child()
    assert isinstance(first_child, Gtk.Label), f"first child: {type(first_child)}"
    second_child = first_child.get_next_sibling()
    assert second_child is not None and isinstance(second_child, Gtk.ScrolledWindow)
    assert view.listbox is not None


check("cookbook list: detail pane above list, variable depth (no clip)", _detail_grows_with_content)


class _FakeTransitSnapshot:
    def __init__(self, bodies, active_transits):
        self.bodies = bodies
        self.active_transits = active_transits
        self.observed_at = "2026-08-24T07:00:00-07:00"


TRANSIT_SNAPSHOT = _FakeTransitSnapshot(
    bodies=[
        {"name": "Saturn", "sign": "Pisces", "sign_degree": 3.5,
         "natal_house": 4, "retrograde": True},
        {"name": "Mars", "sign": "Aries", "sign_degree": 12.0,
         "natal_house": 9, "retrograde": False},
    ],
    active_transits=[
        {"transiting_body": "Saturn", "natal_body": "Sun", "aspect": "conjunction",
         "orb": 0.5, "days_to_exact": 2},
        {"transiting_body": "Moon", "natal_body": "Venus", "aspect": "square",
         "orb": 1.2, "days_to_exact": 0},
    ],
)

TRANSIT_COOKBOOK = {
    "transit_signs": [
        {"body": "Saturn", "sign": "Pisces", "text": "Saturn in Pisces grounds intuition."},
    ],
    "transit_houses": [
        {"body": "Saturn", "house": 4, "text": "Work on the home foundation."},
    ],
    "transit_aspects": [
        {"transit_body": "Saturn", "natal_body": "Sun", "aspect": "conjunction",
         "orb": 0.5, "days_to_exact": 2, "text": "A steady, grounding pressure."},
    ],
    "missing": ["transit-sign:Mars-Aries"],
}


def _transit_entries_basic():
    entries = transit_cookbook_entries(TRANSIT_SNAPSHOT, TRANSIT_COOKBOOK)
    # Saturn grounded (sign+house); Mars missing; Saturn aspect; missing section
    saturn = [e for e in entries if e.section == "Bodies" and "Saturn" in e.title][0]
    assert "Saturn in Pisces grounds intuition." in saturn.text
    assert "Over natal house 4: Work on the home foundation." in saturn.text
    assert not saturn.missing
    mars = [e for e in entries if e.section == "Bodies" and "Mars" in e.title][0]
    assert mars.missing
    asp = [e for e in entries if e.section == "Active Transits"][0]
    assert asp.text == "A steady, grounding pressure."
    assert "exact in 2d" in asp.subtitle, f"subtitle: {asp.subtitle!r}"
    assert any(e.section == "Missing" for e in entries)


check("transit entries: grounded prose, timing label, missing flagged", _transit_entries_basic)


class _FakeSynastrySnapshot:
    def __init__(self, bodies, aspects):
        self.person_a = "Xephyr"
        self.person_b = "Rainy"
        self.bodies = bodies
        self.aspects = aspects


SYNASTRY_SNAPSHOT = _FakeSynastrySnapshot(
    bodies=[
        {"name": "Venus", "sign": "Gemini", "sign_degree": 10.0, "house_b": 7},
        {"name": "Moon", "sign": "Cancer", "sign_degree": 5.0, "house_b": 8},
    ],
    aspects=[
        {"body_a": "Moon", "body_b": "Sun", "aspect": "trine", "orb": 1.5},
    ],
)

SYNASTRY_COOKBOOK = {
    "synastry_houses": [
        {"body": "Venus", "house": 7, "text": "Venus in the partner's 7th house favors partnership."},
    ],
    "synastry_aspects": [
        {"body_a": "Moon", "body_b": "Sun", "aspect": "trine", "orb": 1.5,
         "text": "A trine from the Moon eases emotional contact."},
    ],
    "missing": ["synastry-house:Moon-8"],
}


def _synastry_entries_basic():
    entries = synastry_cookbook_entries(SYNASTRY_SNAPSHOT, SYNASTRY_COOKBOOK)
    venus = [e for e in entries if e.section == "Bodies in Rainy's house" and "Venus" in e.title][0]
    assert venus.text == "Venus in the partner's 7th house favors partnership."
    assert not venus.missing
    moon = [e for e in entries if e.section == "Bodies in Rainy's house" and "Moon" in e.title][0]
    assert moon.missing
    asp = [e for e in entries if e.section == "Cross Aspects"][0]
    assert asp.text == "A trine from the Moon eases emotional contact."
    assert [e.section for e in entries if e.missing] == ["Bodies in Rainy's house", "Missing"]


check("synastry entries: grounded prose + person-B section, missing flagged", _synastry_entries_basic)


print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
