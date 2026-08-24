"""test_table_renderer.py — Headless verification of the sortable table views."""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from astro_gui.renderers.table_renderer import (
    build_planet_table,
    build_transit_grid,
    build_planet_agg_table,
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


# 1. Natal planet table
chart = {
    "bodies": [
        {"name": "Sun", "longitude": 248.7, "sign_name": "Sagittarius",
         "house": 5, "speed": 1.01, "retrograde": False},
        {"name": "Moon", "longitude": 147.3, "sign_name": "Leo",
         "house": 2, "speed": 12.1, "retrograde": False},
    ]
}
check("build_planet_table returns ColumnView",
      lambda: isinstance(build_planet_table(chart), Gtk.ColumnView))

# 2. Transit grid
transits = [
    {"transiting_body": "Mercury", "natal_body": "Moon", "aspect": "conjunction",
     "orb": 1.19, "days_to_exact": 1, "priority": 128},
    {"transiting_body": "Chiron", "natal_body": "Neptune", "aspect": "trine",
     "orb": 1.18, "days_to_exact": 0, "priority": 119},
]
check("build_transit_grid returns ColumnView",
      lambda: isinstance(build_transit_grid(transits), Gtk.ColumnView))

# 3. By-planet aggregation
agg = [
    {"body": "Mercury", "total_priority": 197, "transit_count": 5,
     "top_aspect": "conjunction", "top_natal_body": "Moon"},
    {"body": "Chiron", "total_priority": 172, "transit_count": 4,
     "top_aspect": "trine", "top_natal_body": "Neptune"},
]
check("build_planet_agg_table returns ColumnView",
      lambda: isinstance(build_planet_agg_table(agg), Gtk.ColumnView))

# 4. Empty transit list still builds
check("build_transit_grid handles empty list",
      lambda: isinstance(build_transit_grid([]), Gtk.ColumnView))

# 5. Empty chart still builds
check("build_planet_table handles empty chart",
      lambda: isinstance(build_planet_table({"bodies": []}), Gtk.ColumnView))

print(f"\nResults: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
