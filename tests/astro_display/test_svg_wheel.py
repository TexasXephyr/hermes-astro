"""Unit tests for astro_display SVG wheel renderer."""
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
