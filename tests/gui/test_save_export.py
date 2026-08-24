"""test_save_export.py — Headless verification of item 33: Save button exports.

Covers the pure CSV row builders (real Unicode glyphs), UTF-16 BOM
writing, the MainWindow _export_current routing (which export fires per
tab, correct default names), and empty-state guards. Runs without a
display.
"""

import os
import sys
import tempfile

sys.path.insert(0, "/home/xephyr/astro/src")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from astro_gui.window import (
    MainWindow,
    natal_csv_rows,
    transit_grid_csv_rows,
    by_planet_csv_rows,
    write_csv_utf16,
    NATAL_CSV_COLUMNS,
    TRANSIT_GRID_CSV_COLUMNS,
    BY_PLANET_CSV_COLUMNS,
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


# ------------------------------------------------------------------
# 1. Natal table CSV rows carry real Unicode glyph characters
# ------------------------------------------------------------------
NATAL_CHART = {
    "bodies": [
        {"name": "Sun", "longitude": 248.7, "sign_name": "Leo",
         "sign_degree": 8.7, "house": 5, "speed": 1.01, "retrograde": False},
        {"name": "Moon", "longitude": 147.3, "sign_name": "Taurus",
         "sign_degree": 3.5, "house": 2, "speed": 12.1, "retrograde": True},
    ]
}


def _natal_rows():
    rows = natal_csv_rows(NATAL_CHART)
    assert len(rows) == 2, f"expected 2 rows, got {len(rows)}"
    by_body = {r["Body"]: r for r in rows}
    sun = by_body["☉ Sun"]
    assert sun["Sign"] == "♌ Leo", f"Sun sign: {sun['Sign']!r}"
    assert sun["Degree"] == "8° 42'", f"Sun degree: {sun['Degree']!r}"
    assert sun["House"] == "5"
    assert sun["Dignity"] == "domicile", f"Sun dignity: {sun['Dignity']!r}"
    assert sun["Speed"] == "1.010"
    assert sun["Retro"] == ""
    moon = by_body["☽ Moon"]
    assert moon["Sign"] == "♉ Taurus", f"Moon sign: {moon['Sign']!r}"
    assert moon["Retro"] == "R", f"Moon retro: {moon['Retro']!r}"
    # Body and Sign cells start with the real Unicode glyph (☉ ♌ ☽ ♉)
    for r in rows:
        assert r["Body"][0] in "☉☽☿♀♂♃♄♅♆♇", f"Body missing glyph: {r['Body']!r}"
        assert r["Sign"][0] in "♈♉♊♋♌♍♎♏♐♑♒♓", f"Sign missing glyph: {r['Sign']!r}"


check("natal CSV rows: glyph+name Body/Sign, degree, house, dignity, speed, retro",
      _natal_rows)


def _natal_unknown_sign():
    # Unknown sign names degrade to name-only (no crash, no text fallback)
    chart = {"bodies": [{"name": "Sun", "longitude": 248.7, "sign_name": "Llorona",
                         "sign_degree": 8.7, "house": 5, "speed": 1.0,
                         "retrograde": False}]}
    rows = natal_csv_rows(chart)
    assert rows[0]["Sign"] == "Llorona", f"unknown sign: {rows[0]['Sign']!r}"
    # Empty chart yields no rows
    assert natal_csv_rows({"bodies": []}) == []


check("natal CSV rows tolerate unknown sign names + empty charts", _natal_unknown_sign)


# ------------------------------------------------------------------
# 2. Transit grid CSV rows mirror the grid builder's lookups
# ------------------------------------------------------------------
TRANSITS = [
    {"transiting_body": "Mercury", "natal_body": "Moon", "aspect": "conjunction",
     "orb": 1.19, "days_to_exact": 1, "priority": 128},
    {"transiting_body": "Chiron", "natal_body": "Neptune", "aspect": "trine",
     "orb": 1.18, "days_to_exact": 0, "priority": 119},
]
TRANSIT_BODIES = [
    {"name": "Mercury", "sign_name": "Virgo", "longitude": 174.0},
    {"name": "Chiron", "sign_name": "Aries", "longitude": 9.0},
]
NATAL_BODIES = [
    {"name": "Moon", "sign_name": "Taurus", "house": 2},
    {"name": "Neptune", "sign_name": "Pisces", "house": 6},
]
NATAL_HOUSES = [{"house_num": i + 1, "longitude": i * 30.0} for i in range(12)]


def _grid_rows():
    rows = transit_grid_csv_rows({
        "active": TRANSITS,
        "transit_bodies": TRANSIT_BODIES,
        "natal_bodies": NATAL_BODIES,
        "natal_houses": NATAL_HOUSES,
    })
    assert len(rows) == 2, f"expected 2 rows, got {len(rows)}"
    by_body = {r["T Body"]: r for r in rows}
    merc = by_body["☿ Mercury"]
    assert merc["T Sign"] == "♍ Virgo", f"Mercury T Sign: {merc['T Sign']!r}"
    assert merc["N Sign"] == "♉ Taurus", f"Mercury N Sign: {merc['N Sign']!r}"
    assert merc["Aspect"] == "☌ conjunction", f"Mercury Aspect: {merc['Aspect']!r}"
    # Transit Mercury @174° -> house 6; natal Moon's own house is 2
    assert merc["T House"] == "6", f"Mercury T House: {merc['T House']!r}"
    assert merc["N House"] == "2", f"Mercury N House: {merc['N House']!r}"
    assert merc["Orb"] == "1.19°"
    assert merc["Days"] == "1d"
    assert merc["Priority"] == "128"
    chiron = by_body["⚷ Chiron"]
    assert chiron["Aspect"] == "△ trine", f"Chiron Aspect: {chiron['Aspect']!r}"
    assert chiron["T House"] == "1" and chiron["N House"] == "6"
    assert chiron["Days"] == "0h"
    # Every T/N Body and T/N Sign cell starts with a real glyph
    for r in rows:
        assert r["T Body"][0] in "☉☽☿♀♂♃♄♅♆♇⚷", f"T Body missing glyph: {r['T Body']!r}"
        assert r["N Body"][0] in "☉☽☿♀♂♃♄♅♆♇⚷", f"N Body missing glyph: {r['N Body']!r}"
        assert r["T Sign"][0] in "♈♉♊♋♌♍♎♏♐♑♒♓", f"T Sign missing glyph: {r['T Sign']!r}"
        assert r["N Sign"][0] in "♈♉♊♋♌♍♎♏♐♑♒♓", f"N Sign missing glyph: {r['N Sign']!r}"


check("transit grid CSV rows: glyph columns, house crossing, orb, days, priority",
      _grid_rows)


def _grid_no_bodies():
    # House/sign lookups degrade gracefully without body lists
    rows = transit_grid_csv_rows({"active": TRANSITS})
    assert rows[0]["T Sign"] == "" and rows[0]["N Sign"] == ""
    assert rows[0]["T House"] == "" and rows[0]["N House"] == ""
    # Empty active list
    assert transit_grid_csv_rows({"active": []}) == []


check("transit grid CSV rows tolerate missing lookups + empty active list",
      _grid_no_bodies)


# ------------------------------------------------------------------
# 3. By-planet CSV rows
# ------------------------------------------------------------------
def _by_planet_rows_check():
    rows = by_planet_csv_rows([
        {"body": "Mercury", "total_priority": 197, "transit_count": 5,
         "top_aspect": "conjunction", "top_natal_body": "Moon"},
        {"body": "Chiron", "total_priority": 172, "transit_count": 4,
         "top_aspect": "trine", "top_natal_body": "Neptune"},
    ])
    by_body = {r["Body"]: r for r in rows}
    merc = by_body["☿ Mercury"]
    assert merc["Total"] == "197"
    assert merc["Count"] == "5"
    assert merc["Top Aspect"] == "☌ conjunction"
    assert merc["vs Natal"] == "☽ Moon"
    assert by_body["⚷ Chiron"]["Top Aspect"] == "△ trine"
    assert by_planet_csv_rows([]) == []


check("by-planet CSV rows: glyphs + totals", _by_planet_rows_check)


# ------------------------------------------------------------------
# 4. UTF-16 CSV writing (BOM + glyph survival)
# ------------------------------------------------------------------
def _write_utf16():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "natal.csv")
        write_csv_utf16(path, NATAL_CSV_COLUMNS, natal_csv_rows(NATAL_CHART))
        raw = open(path, "rb").read()
        assert raw[:2] == b"\xff\xfe", f"missing UTF-16 LE BOM: {raw[:4]!r}"
        text = open(path, encoding="utf-16").read()
        assert "☉ Sun" in text, "glyph did not survive round-trip"
        assert "♌ Leo" in text and "♉ Taurus" in text
        assert "Body,Sign,Degree,House,Dignity,Speed,Retro" in text.replace("\ufeff", "")
        assert "domicile" in text


check("write_csv_utf16 emits UTF-16 BOM with glyphs intact", _write_utf16)


# ------------------------------------------------------------------
# 5. MainWindow routing: correct export fires per tab
# ------------------------------------------------------------------
def _routing_fires():
    w = MainWindow()
    try:
        fired = []

        def spy(default_name, filter_specs, callback, *payload):
            fired.append((default_name, filter_specs, callback, payload))

        w._pick_save_path = spy

        # Natal wheel -> PNG, natal_<person>.png
        w._last_wheel_svg = "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/>"
        w.notebook.set_current_page(w.PAGE_NATAL_WHEEL)
        w._export_current()
        assert len(fired) == 1, f"natal wheel fired {len(fired)}"
        name, specs, cb, payload = fired[-1]
        assert name.startswith("natal_") and name.endswith(".png"), f"default: {name!r}"
        assert cb == w._on_png_dialog_result and payload == (w._last_wheel_svg,)

        # Transit wheel -> transit_<person>_<date>.png
        w.notebook.set_current_page(w.PAGE_TRANSIT_WHEEL)
        w._export_current()
        assert fired[-1][0].startswith("transit_") and fired[-1][0].endswith(".png")

        # Synastry wheel -> synastry_<person>.png
        w.notebook.set_current_page(w.PAGE_SYNASTRY_WHEEL)
        w._export_current()
        assert fired[-1][0].startswith("synastry_") and fired[-1][0].endswith(".png")

        # Natal table -> natal_<person>.csv with natal columns
        w.notebook.set_current_page(w.PAGE_NATAL_TABLE)
        w._natal_table_chart = NATAL_CHART
        w._export_current()
        assert fired[-1][0].startswith("natal_") and fired[-1][0].endswith(".csv")
        cols, rows = fired[-1][3]
        assert cols == NATAL_CSV_COLUMNS
        assert len(rows) == 2

        # Transit grid -> transit_grid_<person>_<date>.csv
        w._transit_grid_data = {
            "active": TRANSITS,
            "transit_bodies": TRANSIT_BODIES,
            "natal_bodies": NATAL_BODIES,
            "natal_houses": NATAL_HOUSES,
        }
        w.notebook.set_current_page(w.PAGE_TRANSIT_GRID)
        w._export_current()
        assert "transit_grid_" in fired[-1][0] and fired[-1][0].endswith(".csv")
        cols2, rows2 = fired[-1][3]
        assert cols2 == TRANSIT_GRID_CSV_COLUMNS

        # By Planet -> by_planet_<person>_<date>.csv
        w._by_planet_rows = [
            {"body": "Mercury", "total_priority": 197, "transit_count": 5,
             "top_aspect": "conjunction", "top_natal_body": "Moon"},
        ]
        w.notebook.set_current_page(w.PAGE_BY_PLANET)
        w._export_current()
        assert "by_planet_" in fired[-1][0] and fired[-1][0].endswith(".csv")
        cols3, rows3 = fired[-1][3]
        assert cols3 == BY_PLANET_CSV_COLUMNS
    finally:
        w.close()


check("_export_current routes each tab to the right export + default name",
      _routing_fires)


def _empty_guards():
    w = MainWindow()
    try:
        fired = []

        def spy(default_name, filter_specs, callback, *payload):
            fired.append(1)

        w._pick_save_path = spy
        # MainWindow init already renders every view for the selected
        # person, so clear ALL export state to simulate a fresh window.
        w._last_wheel_svg = None
        w._natal_table_chart = None
        w._transit_grid_data = None
        w._by_planet_rows = None
        w.notebook.set_current_page(w.PAGE_NATAL_WHEEL)
        w._export_current()
        assert fired == [], "wheel with no SVG must not open a dialog"
        # Table tabs with no stored data
        w.notebook.set_current_page(w.PAGE_NATAL_TABLE)
        w._export_current()
        w.notebook.set_current_page(w.PAGE_TRANSIT_GRID)
        w._export_current()
        w.notebook.set_current_page(w.PAGE_BY_PLANET)
        w._export_current()
        assert fired == [], "empty table tabs must not open a dialog"
        # Empty transit data must not fire either
        w._transit_grid_data = {"active": []}
        w._export_current()
        assert fired == [], "empty transit grid must not open a dialog"
    finally:
        w.close()


check("empty-state guards: no dialog when nothing to export", _empty_guards)


print(f"\nResults: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
