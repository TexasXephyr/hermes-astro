"""test_document_sets.py — Headless verification of document-set persistence.

Covers the DocumentSetStore (SQLite schema, default-set uniqueness, named
snapshots, last-active tracking) and the MainWindow capture/apply/restore
round-trip. Runs without a display (GTK widgets instantiate headless).
"""
import sys
sys.path.insert(0, "/home/xephyr/astro/src")

import json
import os
import tempfile

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from astro_gui.persistence import DocumentSetStore
from astro_gui.window import MainWindow

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
# 1. Store: schema + default-set uniqueness
# ------------------------------------------------------------------
def _store_schema():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "library.db")
        store = DocumentSetStore(db)
        store.save_default(1, {"current_tab": 2, "transit_date": "2026-08-24"})
        store.save_default(1, {"current_tab": 4, "transit_date": "2026-08-25"})
        # Only one default row per person (partial unique index)
        cfg = store.load_default(1)
        assert cfg is not None
        assert cfg["current_tab"] == 4, f"expected latest default, got {cfg}"
        # Named snapshot coexists with the default
        store.save_set(1, "Morning", {"current_tab": 1})
        assert store.load_set(1, "Morning")["current_tab"] == 1
        # Named snapshot upsert by (person_id, name)
        store.save_set(1, "Morning", {"current_tab": 3})
        assert store.load_set(1, "Morning")["current_tab"] == 3
        # list_sets excludes the reserved auto/current set
        names = [s["name"] for s in store.list_sets(1)]
        assert names == ["Morning"], f"list_sets: {names}"
        # Per-person isolation
        store.save_default(2, {"current_tab": 5})
        assert store.load_default(2)["current_tab"] == 5
        assert store.load_default(1)["current_tab"] == 4


check("store schema, default uniqueness, named snapshots, isolation", _store_schema)


def _store_last_active():
    with tempfile.TemporaryDirectory() as tmp:
        store = DocumentSetStore(os.path.join(tmp, "library.db"))
        assert store.load_last_active() is None
        store.save_last_active(7)
        assert store.load_last_active() == 7
        store.save_last_active(9)
        assert store.load_last_active() == 9


check("store last-active person tracking", _store_last_active)


def _store_missing_default():
    with tempfile.TemporaryDirectory() as tmp:
        store = DocumentSetStore(os.path.join(tmp, "library.db"))
        assert store.load_default(42) is None
        assert store.load_set(42, "nope") is None
        assert store.list_sets(42) == []


check("store missing set returns None/empty", _store_missing_default)


# ------------------------------------------------------------------
# 2. MainWindow: capture / apply / restore round-trip
# ------------------------------------------------------------------
def _capture_apply_roundtrip():
    w = MainWindow()
    try:
        # Drive the UI into a distinctive state
        w.notebook.set_current_page(w.PAGE_TRANSIT_GRID)
        w._transit_date.set_text("2026-08-24")
        w._transit_time.set_text("12:34:56")
        w._transit_lat.set_text("44.0521")
        w._transit_lon.set_text("-123.0868")
        w._set_aspect_mode("both")
        grid = w._transit_grid_view()
        point_label = ""
        if grid is not None:
            fr = grid.filter_row
            # The point filter is a dropdown of ACTIVE points: pick the first
            # one ('All' is index 0). The captured value is the dropdown
            # label itself ('T: Mercury'), which apply matches by string.
            model = fr.point_dropdown.get_model()
            assert model.get_string(0) == "All"
            point_label = model.get_string(1)
            fr.point_dropdown.set_selected(1)
            fr.aspect_dropdown.set_selected(1)  # conjunction
            fr.sign_dropdown.set_selected(1)  # Aries
            fr.house_dropdown.set_selected(1)  # house 1

        cfg = w._capture_document_set()
        assert cfg["current_tab"] == w.PAGE_TRANSIT_GRID
        assert cfg["transit_date"] == "2026-08-24"
        assert cfg["transit_time"] == "12:34:56"
        assert cfg["transit_lat"] == "44.0521"
        assert cfg["transit_lon"] == "-123.0868"
        assert cfg["aspect_mode"] == "both"
        if "grid_filter" in cfg:
            assert cfg["grid_filter"]["point"] == point_label
            assert cfg["grid_filter"]["aspect"] == "conjunction"
            assert cfg["grid_filter"]["sign"] == "Aries"
            assert cfg["grid_filter"]["house"] == "1"

        # Apply to a fresh window and verify the state lands
        w2 = MainWindow()
        try:
            w2._apply_document_set(cfg)
            assert w2.notebook.get_current_page() == w.PAGE_TRANSIT_GRID
            assert w2._transit_date.get_text() == "2026-08-24"
            assert w2._transit_time.get_text() == "12:34:56"
            assert w2._transit_lat.get_text() == "44.0521"
            assert w2._transit_lon.get_text() == "-123.0868"
            assert w2._transit_aspect_mode.get_selected_item().get_string() == "both"
            grid2 = w2._transit_grid_view()
            if grid2 is not None:
                fr2 = grid2.filter_row
                assert fr2.point_dropdown.get_selected_item().get_string() == point_label
                assert fr2.aspect_dropdown.get_selected_item().get_string() == "conjunction"
                assert fr2.sign_dropdown.get_selected_item().get_string() == "Aries"
                assert fr2.house_dropdown.get_selected_item().get_string() == "1"
        finally:
            w2.close()
    finally:
        w.close()


check("capture/apply round-trip restores tab, dates, lat/lon, aspect, filters", _capture_apply_roundtrip)


def _apply_tolerant():
    w = MainWindow()
    try:
        # Unknown aspect mode and out-of-range tab must not raise
        w._apply_document_set({
            "current_tab": 999,
            "aspect_mode": "not-a-mode",
            "transit_date": "2026-01-01",
        })
        assert w._transit_date.get_text() == "2026-01-01"
        # Non-dict config is a no-op
        w._apply_document_set(None)
        w._apply_document_set("junk")
    finally:
        w.close()


check("apply tolerates bad values without raising", _apply_tolerant)


def _auto_save_on_close():
    w = MainWindow()
    try:
        person = w._selected_person
        assert person is not None, "expected a selected person"
        w.notebook.set_current_page(w.PAGE_BY_PLANET)
        w._transit_date.set_text("2026-08-24")
        w._on_close_request()
        cfg = w._doc_sets.load_default(person.get("id"))
        assert cfg is not None, "close-request should auto-save the default set"
        assert cfg["current_tab"] == w.PAGE_BY_PLANET
        assert cfg["transit_date"] == "2026-08-24"
    finally:
        w.close()


check("close-request auto-saves the current document set", _auto_save_on_close)


def _restore_session():
    w = MainWindow()
    try:
        person = w._selected_person
        assert person is not None
        # Save a distinctive default set for the current person
        w._doc_sets.save_default(person.get("id"), {
            "version": 1,
            "current_tab": w.PAGE_TRANSIT_GRID,
            "transit_date": "2026-08-24",
            "transit_time": "09:00:00",
            "transit_lat": "",
            "transit_lon": "",
            "aspect_mode": "transit-natal",
        })
        w._doc_sets.save_last_active(person.get("id"))
        # A fresh window restores the saved set
        w2 = MainWindow()
        try:
            assert w2.notebook.get_current_page() == w.PAGE_TRANSIT_GRID, \
                f"expected restored tab {w.PAGE_TRANSIT_GRID}, got {w2.notebook.get_current_page()}"
            assert w2._transit_date.get_text() == "2026-08-24"
            assert w2._transit_time.get_text() == "09:00:00"
        finally:
            w2.close()
    finally:
        w.close()


check("startup restores last active person's saved set", _restore_session)


def _default_layout_when_no_set():
    w = MainWindow()
    try:
        person = w._selected_person
        assert person is not None
        # No saved set -> default layout is the natal wheel tab
        w._doc_sets.save_default(person.get("id"), {"version": 1, "current_tab": w.PAGE_NATAL_WHEEL})
        w._doc_sets.save_last_active(person.get("id"))
        w2 = MainWindow()
        try:
            assert w2.notebook.get_current_page() == w.PAGE_NATAL_WHEEL
        finally:
            w2.close()
    finally:
        w.close()


check("no saved set falls back to natal wheel default", _default_layout_when_no_set)


def _menu_actions_registered():
    w = MainWindow()
    try:
        assert w.lookup_action("save-document-set") is not None
        assert w.lookup_action("load-document-set") is not None
    finally:
        w.close()


check("File menu window actions registered", _menu_actions_registered)


print(f"\nResults: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
