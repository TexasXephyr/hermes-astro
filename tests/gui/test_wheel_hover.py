"""test_wheel_hover.py — Headless verification of the wheel hover inspector.

Covers the hit-testing geometry (planets, aspect lines, houses, signs,
angles), the widget→SVG coordinate conversion, the HoverPanel widget,
and the markup assembly (status + aspects + cookbook rows). Runs
without a display.
"""

import sys
sys.path.insert(0, "/home/xephyr/astro/src")

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from astro_display.svg.hit_test import (
    build_natal_hotspots,
    build_transit_hotspots,
    build_synastry_hotspots,
    hit_test,
    widget_to_svg,
)
from astro_gui.widgets.hover_panel import HoverPanel
from astro_gui.renderers.wheel_hover import (
    render_target_markup,
    build_cookbook_index,
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
# Fixtures
# ------------------------------------------------------------------
NATAL = {
    "angles": {"ascendant": 0.0, "mc": 90.0},
    "houses": [{"house_num": i + 1, "longitude": i * 30.0} for i in range(12)],
    "bodies": [
        {"name": "Sun", "longitude": 15.0, "sign_name": "Aries",
         "sign_degree": 15.0, "house": 1, "speed": 1.0, "retrograde": False},
        {"name": "Moon", "longitude": 45.0, "sign_name": "Taurus",
         "sign_degree": 15.0, "house": 2, "speed": 12.0, "retrograde": False},
    ],
    "aspects": [
        {"body_a": "Sun", "body_b": "Moon", "aspect_name": "square",
         "orb": 0.5, "applying": True},
    ],
}

TRANSIT = {
    "bodies": [
        {"name": "Saturn", "longitude": 15.0, "sign_name": "Aries",
         "sign_degree": 15.0, "speed": 0.1, "retrograde": False},
    ],
    "cross_aspects": [
        {"transit_body": "Saturn", "natal_body": "Sun", "aspect_name": "conjunction",
         "orb": 0.4, "applying": True},
    ],
}

SYNASTRY_B = {
    "bodies": [
        {"name": "Venus", "longitude": 45.0, "sign_name": "Taurus",
         "sign_degree": 15.0, "speed": 1.0, "retrograde": False},
    ],
}


def _sun_hotspot(hotspots):
    return next(h for h in hotspots if h.kind == "planet" and h.label == "Sun")


# ------------------------------------------------------------------
# 1. Hit testing
# ------------------------------------------------------------------
def _planet_hit():
    hs = build_natal_hotspots(NATAL)
    sun = _sun_hotspot(hs)
    hits = hit_test(sun.x, sun.y, hs)
    assert hits and hits[0].label == "Sun", f"expected Sun, got {[h.label for h in hits]}"
    # A point far from everything hits nothing
    assert hit_test(10.0, 10.0, hs) == []


check("hit_test: planet near its glyph position wins", _planet_hit)


def _aspect_line_hit():
    hs = build_natal_hotspots(NATAL)
    asp = next(h for h in hs if h.kind == "aspect")
    # Midpoint of the segment should hit the aspect line
    mx = (asp.x + asp.x2) / 2.0
    my = (asp.y + asp.y2) / 2.0
    hits = hit_test(mx, my, hs)
    assert hits and hits[0].kind == "aspect", f"expected aspect, got {[h.kind for h in hits]}"


check("hit_test: aspect line hit at segment midpoint", _aspect_line_hit)


def _house_hit():
    hs = build_natal_hotspots(NATAL)
    # House 3 spans 60-90° (centroid 75°) — no planet there, so the
    # house wedge is the only candidate (House 1's centroid coincides
    # with the Sun planet, which correctly wins by priority).
    house = next(h for h in hs if h.kind == "house" and h.label == "House 3")
    hits = hit_test(house.x, house.y, hs)
    assert hits and hits[0].kind == "house", f"expected house, got {[h.kind for h in hits]}"


check("hit_test: house wedge hit at centroid", _house_hit)


def _sign_hit():
    hs = build_natal_hotspots(NATAL)
    sign = next(h for h in hs if h.kind == "sign" and h.label == "Aries")
    hits = hit_test(sign.x, sign.y, hs)
    assert hits and hits[0].kind == "sign", f"expected sign, got {[h.kind for h in hits]}"


check("hit_test: sign glyph hit", _sign_hit)


def _transit_hotspots():
    hs = build_transit_hotspots(NATAL, TRANSIT)
    kinds = {h.kind for h in hs}
    assert "planet" in kinds and "aspect" in kinds and "sign" in kinds
    # Transit Saturn sits at the same longitude as natal Sun — both planets
    # are candidates. The transit (outer ring) planet must WIN the hover:
    # the two rings are only 27px apart with 16px hit circles, so the
    # conjunct pair overlaps (2026-08-24 bug: hovering a transiting planet
    # showed natal info).
    sat = next(h for h in hs if h.kind == "planet" and h.label == "Saturn"
               and h.data.get("color") == "#ffd43b")
    hits = hit_test(sat.x, sat.y, hs)
    assert hits and hits[0].label == "Saturn", f"transit planet lost: {[h.label for h in hits[:2]]}"
    assert hits[0].data.get("color") == "#ffd43b", "transit hotspot should win"
    # Midway into the overlap band between the conjunct pair, the transit
    # planet must STILL win.
    import math
    sun = next(h for h in hs if h.kind == "planet" and h.label == "Sun"
               and h.data.get("color") == "#ffffff")
    mx, my = (sat.x + sun.x) / 2.0, (sat.y + sun.y) / 2.0
    hits_mid = hit_test(mx, my, hs)
    assert hits_mid and hits_mid[0].label == "Saturn", \
        f"overlap band picked natal: {[h.label for h in hits_mid[:2]]}"


check("hit_test: transit planet wins over conjunct natal in overlap", _transit_hotspots)


def _synastry_hotspots():
    hs = build_synastry_hotspots(NATAL, SYNASTRY_B, [
        {"body_a": "Sun", "body_b": "Venus", "aspect_name": "trine", "orb": 1.0},
    ])
    kinds = {h.kind for h in hs}
    assert "planet" in kinds and "aspect" in kinds
    venus = next(h for h in hs if h.kind == "planet" and h.label == "Venus")
    hits = hit_test(venus.x, venus.y, hs)
    assert hits and hits[0].label == "Venus"


check("hit_test: synastry hotspots include both persons' planets", _synastry_hotspots)


# ------------------------------------------------------------------
# 2. Coordinate conversion (CONTAIN fit)
# ------------------------------------------------------------------
def _coord_convert():
    # 600x600 SVG in a 1200x800 widget: scale = min(2, 1.333) = 1.333,
    # draw 800x800, offset x = 200, y = 0. Center of widget -> center of SVG.
    sx, sy = widget_to_svg(600.0, 400.0, 1200.0, 800.0)
    assert abs(sx - 300.0) < 0.01 and abs(sy - 300.0) < 0.01, f"{sx},{sy}"
    # Top-left of the drawn image -> SVG (0,0)
    sx, sy = widget_to_svg(200.0, 0.0, 1200.0, 800.0)
    assert abs(sx) < 0.01 and abs(sy) < 0.01, f"{sx},{sy}"
    # Outside the drawn image -> None
    sx, sy = widget_to_svg(0.0, 0.0, 1200.0, 800.0)
    assert sx is None and sy is None


check("widget_to_svg: CONTAIN-fit mapping + out-of-image guard", _coord_convert)


# ------------------------------------------------------------------
# 3. HoverPanel
# ------------------------------------------------------------------
def _panel_basic():
    panel = HoverPanel()
    assert panel.label is not None
    assert "Hover over the wheel" in panel.label.get_text()
    panel.show_markup("<b>Sun</b>\nstatus")
    assert "Sun" in panel.label.get_text()
    panel.clear()
    assert "Hover over the wheel" in panel.label.get_text()


check("HoverPanel: show/clear markup", _panel_basic)


# ------------------------------------------------------------------
# 4. Markup assembly
# ------------------------------------------------------------------
COOKBOOK = {
    "natal_signs": [
        {"body": "Sun", "sign": "Aries", "text": "The Sun in Aries is direct."},
    ],
    "natal_houses": [
        {"body": "Sun", "house": 1, "text": "The Sun in the 1st house leads."},
    ],
    "natal_aspects": [
        {"body_a": "Sun", "body_b": "Moon", "aspect": "square",
         "text": "A square to the Sun creates friction."},
    ],
}
CTX = {
    "bodies": NATAL["bodies"],
    "aspects": NATAL["aspects"],
    "aspect_domain": "aspect",
    "sign_domain": "natal-sign",
    "house_domain": "natal-house",
    "a_key": "body_a",
    "b_key": "body_b",
    "cookbook": build_cookbook_index(None, COOKBOOK),
}


def _planet_markup():
    hs = build_natal_hotspots(NATAL)
    sun = _sun_hotspot(hs)
    markup = render_target_markup(sun, CTX)
    assert "Sun" in markup
    assert "Aries" in markup
    assert "House 1" in markup
    assert "The Sun in Aries is direct." in markup
    assert "The Sun in the 1st house leads." in markup
    assert "A square to the Sun creates friction." in markup


check("planet markup: status + aspects + cookbook rows", _planet_markup)


def _aspect_markup():
    hs = build_natal_hotspots(NATAL)
    asp = next(h for h in hs if h.kind == "aspect")
    markup = render_target_markup(asp, CTX)
    assert "square" in markup
    assert "A square to the Sun creates friction." in markup
    assert "orb" in markup


check("aspect markup: bodies + orb + cookbook", _aspect_markup)


def _sign_markup():
    hs = build_natal_hotspots(NATAL)
    sign = next(h for h in hs if h.kind == "sign" and h.label == "Aries")
    markup = render_target_markup(sign, CTX)
    assert "Aries" in markup
    assert "Sun" in markup  # bodies in the sign
    assert "The Sun in Aries is direct." in markup


check("sign markup: bodies in sign + cookbook", _sign_markup)


def _house_markup():
    hs = build_natal_hotspots(NATAL)
    house = next(h for h in hs if h.kind == "house" and h.label == "House 1")
    markup = render_target_markup(house, CTX)
    assert "House 1" in markup
    assert "Sun" in markup
    assert "The Sun in the 1st house leads." in markup


check("house markup: bodies in house + cookbook", _house_markup)


def _angle_markup():
    hs = build_natal_hotspots(NATAL)
    asc = next(h for h in hs if h.kind == "angle" and h.label == "Asc")
    markup = render_target_markup(asc, CTX)
    assert "Asc" in markup
    assert "Aries" in markup


check("angle markup: label + sign + longitude", _angle_markup)


# ------------------------------------------------------------------
# 5. Window wiring regression: _attach_hover must receive callables
# ------------------------------------------------------------------
def _attach_hover_callables():
    """The hover handler calls hotspots_getter() and ctx_getter(), so
    _attach_hover must be given callables — passing a dict directly
    raises TypeError on every motion and the panel always clears
    (regression: 2026-08-24, hover appeared dead in the real app)."""
    from astro_gui.window import MainWindow

    captured = []

    def spy(self, picture, panel, hotspots_getter, ctx_getter):
        captured.append((picture, panel, hotspots_getter, ctx_getter))

    original = MainWindow._attach_hover
    MainWindow._attach_hover = spy
    try:
        w = MainWindow()
        try:
            assert len(captured) == 3, f"expected 3 wheel attach calls, got {len(captured)}"
            for picture, panel, hotspots_getter, ctx_getter in captured:
                assert callable(hotspots_getter), "hotspots_getter not callable"
                assert callable(ctx_getter), "ctx_getter not callable"
                # The getters must return the window's live state
                assert isinstance(hotspots_getter(), list)
                assert isinstance(ctx_getter(), dict)
        finally:
            w.close()
    finally:
        MainWindow._attach_hover = original


check("window wiring: _attach_hover gets callables for all 3 wheels",
      _attach_hover_callables)


print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
