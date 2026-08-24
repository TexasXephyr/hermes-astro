"""Unit tests for astro_display SVG wheel renderer."""
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from astro_display.svg.wheel import WheelRenderer
from astro_display.fonts import find_font


SAMPLE_HOUSES = [
    {"house_num": 1, "longitude": 0.0},
    {"house_num": 2, "longitude": 30.0},
    {"house_num": 3, "longitude": 60.0},
    {"house_num": 4, "longitude": 90.0},
    {"house_num": 5, "longitude": 120.0},
    {"house_num": 6, "longitude": 150.0},
    {"house_num": 7, "longitude": 180.0},
    {"house_num": 8, "longitude": 210.0},
    {"house_num": 9, "longitude": 240.0},
    {"house_num": 10, "longitude": 270.0},
    {"house_num": 11, "longitude": 300.0},
    {"house_num": 12, "longitude": 330.0},
]

SAMPLE_BODIES = [
    {"name": "Sun", "longitude": 15.0, "sign_degree": 15.0, "retrograde": False},
    {"name": "Moon", "longitude": 45.0, "sign_degree": 15.0, "retrograde": True},
]

SAMPLE_ASPECTS = [
    {"body_a": "Sun", "body_b": "Moon", "aspect_name": "Sextile"},
]


@pytest.fixture
def renderer():
    return WheelRenderer()


def test_font_discovery_regular():
    path = find_font("regular")
    assert Path(path).exists()
    assert "LiberZodiac-Regular.ttf" in path


def test_font_discovery_bold():
    path = find_font("bold")
    assert Path(path).exists()
    assert "LiberZodiac-Bold.ttf" in path


def test_font_discovery_italic():
    path = find_font("italic")
    assert Path(path).exists()
    assert "LiberZodiac-Italic.ttf" in path


def test_font_discovery_missing_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "astro_display.fonts._FONT_DIR", tmp_path / "fonts"
    )
    with pytest.raises(FileNotFoundError):
        find_font("regular")


def test_render_natal_returns_valid_svg(renderer):
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": SAMPLE_ASPECTS,
    }
    svg = renderer.render_natal(chart)
    # Parse as XML
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["width"] == "600"
    assert root.attrib["height"] == "600"
    # Spot-check expected elements exist
    assert "LiberZodiac" in svg
    assert "file://" in svg
    # Glyphs are inline <path> outlines, not text (no font fallback)
    assert "<path" in svg
    assert "#69db7c" in svg  # sextile color


def test_render_natal_asc_mc_labels_present(renderer):
    chart = {
        "angles": {"ascendant": 113.0, "mc": 9.5},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [],
    }
    svg = renderer.render_natal(chart)
    assert "Asc" in svg
    assert "MC" in svg


def test_render_natal_south_node_glyph(renderer):
    """South Node renders as a path glyph, not a capital S fallback."""
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [
            {"name": "South Node", "longitude": 166.9, "sign_degree": 16.9, "retrograde": False},
        ],
        "aspects": [],
    }
    svg = renderer.render_natal(chart)
    assert "<path" in svg  # glyph rendered as outline
    # The body glyph must NOT be a text element (degree labels/Asc/MC are text,
    # but a body fallback as plain text like "S" would be a bug)
    import re
    body_text = re.findall(r'<text[^>]*>([^<]*)</text>', svg)
    assert "S" not in body_text, "South Node must not fall back to a text 'S'"


def test_render_natal_all_zodiac_glyphs_paths(renderer):
    """All 12 zodiac signs are emitted as inline paths (no emoji fallback)."""
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [],
        "aspects": [],
    }
    svg = renderer.render_natal(chart)
    assert svg.count("<path") >= 12
    # No emoji fallback: the SVGs must not contain colorful emoji chars
    for emoji in ("\U0001F7E0", "\U0001F7E1", "\U0001F7E2", "\U0001F7E3"):
        assert emoji not in svg


def test_render_natal_no_clipped_signs(renderer):
    """Sign labels stay inside the canvas (no thin crescents at edges)."""
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [],
        "aspects": [],
    }
    svg = renderer.render_natal(chart)
    # All text coordinates must be within [0, 600]
    import re
    for m in re.finditer(r'<text x="([0-9.]+)" y="([0-9.]+)"', svg):
        x = float(m.group(1))
        y = float(m.group(2))
        assert 0 <= x <= 600, f"text x out of canvas: {x}"
        assert 0 <= y <= 600, f"text y out of canvas: {y}"


def test_glyph_paths_are_y_flipped():
    """Glyph paths are embedded with a negative-y scale (upright in SVG)."""
    from astro_display.svg.wheel import _path_element
    el = _path_element("Aries", 100, 100, 20)
    assert "scale(" in el
    # The transform must flip y: scale(s, -s)
    m = re.search(r"scale\(([0-9.]+),(-[0-9.]+)\)", el)
    assert m is not None, f"Aries glyph must use a y-flipped scale, got: {el}"
    assert float(m.group(1)) > 0
    assert float(m.group(2)) < 0


def test_render_natal_scale_applied(renderer):
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [],
    }
    svg = renderer.render_natal(chart, scale=1.5)
    assert 'scale(1.5)' in svg


def test_render_transit_returns_valid_svg(renderer):
    natal = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": SAMPLE_ASPECTS,
    }
    transit = {
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False},
        ],
    }
    svg = renderer.render_transit(natal, transit)
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert "(T)" not in svg  # transit suffix removed (review item 9)


def test_render_transit_draws_transit_natal_not_natal_natal(renderer):
    """Review item 14: transit wheel draws transit-natal aspects, never
    natal-natal aspects."""
    natal = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,  # Sun 15°, Moon 45° — sextile in natal
        "aspects": SAMPLE_ASPECTS,  # natal Sun-Moon sextile
    }
    transit = {
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False},
        ],
        "cross_aspects": [
            {"transit_body": "Mars", "natal_body": "Sun",
             "aspect_name": "Trine", "orb": 1.0},
        ],
    }
    svg = renderer.render_transit(natal, transit)
    # The natal-natal Sun-Moon sextile must NOT appear as a line.
    # Sextile color is #69db7c; trine is #4dabf7.
    assert "#69db7c" not in svg, "natal-natal aspects must not render on transit wheel"
    assert "#4dabf7" in svg, "transit-natal aspect must render"


def test_render_transit_cross_aspect_endpoints_at_aspect_ring(renderer):
    """Review item 28: transit-natal lines run dot-to-dot on the aspect
    ring (R_aspect=165) — BOTH endpoints, never to the planet rings."""
    natal = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [],
    }
    transit = {
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False},
        ],
        "cross_aspects": [
            {"transit_body": "Mars", "natal_body": "Sun",
             "aspect_name": "Trine", "orb": 1.0},
        ],
    }
    svg = renderer.render_transit(natal, transit)
    import re
    lines = re.findall(
        r'<line x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)" '
        r'stroke="#4dabf7"', svg)
    assert lines, "expected a trine line"
    x1, y1, x2, y2 = (float(v) for v in lines[0])
    r1 = math.hypot(x1 - 300, y1 - 300)
    r2 = math.hypot(x2 - 300, y2 - 300)
    assert round(r1) == 165, f"transit endpoint must be at R_aspect, got {r1:.1f}"
    assert round(r2) == 165, f"natal endpoint must be at R_aspect, got {r2:.1f}"
    # Neither endpoint may sit at the planet radii (225 natal / 252 transit)
    assert round(r1) not in (225, 252)
    assert round(r2) not in (225, 252)


def test_render_transit_aspect_mode_transit_transit(renderer):
    """Review item 15: aspect_mode='transit-transit' draws aspects among
    transiting bodies only (no transit-natal cross lines)."""
    natal = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,  # Sun 15°, Moon 45°
        "aspects": [],
    }
    transit = {
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False, "speed": 0.5},
            {"name": "Venus", "longitude": 180.0, "sign_degree": 0.0, "retrograde": False, "speed": 1.2},
        ],
        "cross_aspects": [
            {"transit_body": "Mars", "natal_body": "Sun",
             "aspect_name": "Trine", "orb": 1.0},
        ],
    }
    svg = renderer.render_transit(natal, transit, aspect_mode="transit-transit")
    # Mars 120° vs Venus 180° = 60° = sextile (#69db7c)
    assert "#69db7c" in svg, "transit-transit sextile must render"
    # The transit-natal trine (#4dabf7) must NOT render in this mode
    assert "#4dabf7" not in svg, "transit-natal aspects must not render in transit-transit mode"


def test_render_transit_aspect_mode_both(renderer):
    """Review item 15: aspect_mode='both' draws transit-natal AND
    transit-transit, with transit-transit in a distinct dashed yellow."""
    natal = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,  # Sun 15°, Moon 45°
        "aspects": [],
    }
    transit = {
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False, "speed": 0.5},
            {"name": "Venus", "longitude": 180.0, "sign_degree": 0.0, "retrograde": False, "speed": 1.2},
        ],
        "cross_aspects": [
            {"transit_body": "Mars", "natal_body": "Sun",
             "aspect_name": "Trine", "orb": 1.0},
        ],
    }
    svg = renderer.render_transit(natal, transit, aspect_mode="both")
    # transit-natal trine present
    assert "#4dabf7" in svg, "transit-natal aspect must render in both mode"
    # transit-transit sextile present, in the distinct yellow with dash
    assert 'stroke="#ffd43b"' in svg, "transit-transit must use distinct yellow in both mode"
    assert "stroke-dasharray" in svg, "transit-transit must be dashed in both mode"


def test_render_transit_aspect_mode_default_is_transit_natal(renderer):
    """Review item 15: default aspect_mode is transit-natal."""
    natal = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [],
    }
    transit = {
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False, "speed": 0.5},
            {"name": "Venus", "longitude": 180.0, "sign_degree": 0.0, "retrograde": False, "speed": 1.2},
        ],
        "cross_aspects": [
            {"transit_body": "Mars", "natal_body": "Sun",
             "aspect_name": "Trine", "orb": 1.0},
        ],
    }
    svg = renderer.render_transit(natal, transit)
    assert "#4dabf7" in svg, "default mode must draw transit-natal aspects"
    # transit-transit sextile must NOT be drawn by default
    assert "#69db7c" not in svg, "default mode must not draw transit-transit aspects"


def test_render_synastry_cross_aspect_endpoints_at_aspect_ring(renderer):
    """Review item 28: synastry cross-aspect lines connect person A's dot
    to person B's dot — BOTH at R_aspect (150), never at 205/245."""
    chart_a = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
    }
    chart_b = {
        "angles": {"ascendant": 10.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False},
        ],
    }
    cross_aspects = [
        {"body_a": "Sun", "body_b": "Mars", "aspect_name": "Trine", "orb": 1.0},
    ]
    svg = renderer.render_synastry(chart_a, chart_b, cross_aspects)
    import re
    lines = re.findall(
        r'<line x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)" '
        r'stroke="#4dabf7"', svg)
    assert lines, "expected a trine line"
    x1, y1, x2, y2 = (float(v) for v in lines[0])
    r1 = math.hypot(x1 - 300, y1 - 300)
    r2 = math.hypot(x2 - 300, y2 - 300)
    assert round(r1) == 150, f"person A endpoint must be at R_aspect, got {r1:.1f}"
    assert round(r2) == 150, f"person B endpoint must be at R_aspect, got {r2:.1f}"
    assert round(r1) not in (205, 245)
    assert round(r2) not in (205, 245)


def test_no_aspect_line_endpoint_at_planet_radius(renderer):
    """Review item 28: NO aspect line endpoint may sit on a planet/point
    ring — transit-natal lines only touch R_aspect (165)."""
    natal = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [],
    }
    transit = {
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False},
        ],
        "cross_aspects": [
            {"transit_body": "Mars", "natal_body": "Sun",
             "aspect_name": "Trine", "orb": 1.0},
        ],
    }
    svg = renderer.render_transit(natal, transit)
    import re
    lines = re.findall(
        r'<line x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)" '
        r'stroke="#[0-9a-fA-F]{6}"', svg)
    # Filter out non-aspect lines (sign ticks are #888888; but none of the
    # transit-natal aspect lines here should touch 225 or 252).
    for line in lines:
        x1, y1, x2, y2 = (float(v) for v in line)
        r1 = round(math.hypot(x1 - 300, y1 - 300))
        r2 = round(math.hypot(x2 - 300, y2 - 300))
        assert r1 not in (225, 252), f"aspect endpoint at planet radius: {r1}"
        assert r2 not in (225, 252), f"aspect endpoint at planet radius: {r2}"


def test_aspect_ring_guide_circle_on_all_wheels(renderer):
    """Review item 28: a subtle guide circle at R_aspect (stroke #555,
    width 1, fill none) renders on natal, transit, and synastry wheels."""
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [],
    }
    transit = {"bodies": []}
    chart_b = {
        "angles": {"ascendant": 10.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [],
    }
    natal_svg = renderer.render_natal(chart)
    transit_svg = renderer.render_transit(chart, transit)
    synastry_svg = renderer.render_synastry(chart, chart_b, [])
    for svg, r in (
        (natal_svg, renderer.R_aspect),
        (transit_svg, renderer.R_aspect),
        (synastry_svg, 150.0),
    ):
        guides = re.findall(
            r'<circle cx="300.0" cy="300.0" r="([0-9.]+)" '
            r'stroke="#555555" stroke-width="1" fill="none"/>', svg)
        assert guides, "aspect ring guide circle missing"
        assert float(r) in {float(g) for g in guides}, (
            f"expected an aspect ring guide at r={r}, got {guides}"
        )


def test_render_sign_ticks_present(renderer):
    """Review item 13: a radial tick at each sign cusp (12 ticks)."""
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [],
        "aspects": [],
    }
    svg = renderer.render_natal(chart)
    # Ticks are lines with stroke #888888 and width 1.2
    import re
    ticks = re.findall(r'<line [^>]*stroke="#888888" stroke-width="1.2"', svg)
    assert len(ticks) == 12, f"expected 12 sign ticks, got {len(ticks)}"


def test_render_aspects_skips_node_node_and_asc_mc(renderer):
    """Review item 12: no aspects between nodes, or between Asc and MC."""
    chart = {
        "angles": {"ascendant": 0.0, "mc": 90.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [
            {"name": "Mean Node", "longitude": 10.0, "sign_degree": 10.0, "retrograde": False},
            {"name": "True Node", "longitude": 20.0, "sign_degree": 20.0, "retrograde": False},
        ],
        "aspects": [
            {"body_a": "Mean Node", "body_b": "True Node", "aspect_name": "Conjunction"},
            {"body_a": "Asc", "body_b": "MC", "aspect_name": "Square"},
        ],
    }
    svg = renderer.render_natal(chart)
    # Conjunction color #ffff00 and square color #ff8787 must not appear
    assert "#ffff00" not in svg, "node-node aspect must be skipped"
    assert "#ff8787" not in svg, "Asc-MC aspect must be skipped"


def test_render_transit_retrograde_subscript_right(renderer):
    """Retrograde mark sits to the RIGHT-BELOW of the planet glyph."""
    natal = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [],
    }
    transit = {
        "bodies": [
            {"name": "Saturn", "longitude": 0.0, "sign_degree": 0.0, "retrograde": True},
        ],
    }
    svg = renderer.render_transit(natal, transit)
    assert "\u211E" in svg  # retrograde mark present
    # Find planet glyph x and retro x — retro must be to the right
    import re
    # Transit planet at R_planet=252, display 0 -> x = cx - r = 300-252 = 48
    retro_m = re.search(r'<text x="([0-9.]+)" y="([0-9.]+)"[^>]*>\u211E</text>', svg)
    assert retro_m is not None
    retro_x = float(retro_m.group(1))
    retro_y = float(retro_m.group(2))
    # planet glyph centered at (48, 300); retro right+below means x > 48 and y > 300
    assert retro_x > 48.0, "retrograde should be to the right of the planet"
    assert retro_y > 300.0, "retrograde should be below the planet (subscript)"


def test_render_synastry_returns_valid_svg(renderer):
    chart_a = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
    }
    chart_b = {
        "angles": {"ascendant": 10.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [
            {"name": "Mars", "longitude": 120.0, "sign_degree": 0.0, "retrograde": False},
        ],
    }
    cross_aspects = [
        {"body_a": "Sun", "body_b": "Mars", "aspect_name": "Trine"},
    ]
    svg = renderer.render_synastry(chart_a, chart_b, cross_aspects)
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert "(B)" not in svg  # suffix removed, consistent with transit
    assert "#4dabf7" in svg  # trine color


def test_aspect_color_case_insensitive(renderer):
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [
            {"body_a": "Sun", "body_b": "Moon", "aspect": "sextile"},
        ],
    }
    svg = renderer.render_natal(chart)
    assert "#69db7c" in svg


def test_unknown_aspect_falls_back_to_gray(renderer):
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": SAMPLE_BODIES,
        "aspects": [
            {"body_a": "Sun", "body_b": "Moon", "aspect_name": "BogusAspect"},
        ],
    }
    svg = renderer.render_natal(chart)
    assert "#888888" in svg


def test_retrograde_glyph_appended(renderer):
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": SAMPLE_HOUSES,
        "bodies": [
            {"name": "Moon", "longitude": 45.0, "sign_degree": 15.0, "retrograde": True},
        ],
        "aspects": [],
    }
    svg = renderer.render_natal(chart)
    assert "\u211E" in svg  # ℞


def test_empty_houses_does_not_crash(renderer):
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": [],
        "bodies": [],
        "aspects": [],
    }
    svg = renderer.render_natal(chart)
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"


def test_font_face_src_uses_file_url(renderer):
    chart = {
        "angles": {"ascendant": 0.0},
        "houses": [],
        "bodies": [],
        "aspects": [],
    }
    svg = renderer.render_natal(chart)
    assert "file:///home/xephyr/.local/share/fonts/LiberZodiac-Regular.ttf" in svg
