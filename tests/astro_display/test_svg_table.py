"""Unit tests for astro_display SVG table renderer (review items 18-19)."""
import re
import xml.etree.ElementTree as ET

import pytest

from astro_display.svg.table import TableRenderer, COLUMNS


SAMPLE_BODIES = [
    {"name": "Sun", "longitude": 220.06, "sign_name": "Scorpio",
     "sign_degree": 10.06, "house": 5, "speed": 1.001, "retrograde": False},
    {"name": "Moon", "longitude": 43.89, "sign_name": "Taurus",
     "sign_degree": 3.5, "house": 11, "speed": 15.19, "retrograde": False},
    {"name": "Mercury", "longitude": 235.42, "sign_name": "Scorpio",
     "sign_degree": 25.42, "house": 5, "speed": 1.477, "retrograde": True},
]


@pytest.fixture
def renderer():
    return TableRenderer()


def test_render_natal_table_valid_svg(renderer):
    svg = renderer.render_natal_table({"bodies": SAMPLE_BODIES})
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["width"] == str(renderer.width)


def test_render_natal_table_uses_path_glyphs_not_emoji(renderer):
    """Review item 18: glyphs are inline SVG paths, no emoji fallback."""
    svg = renderer.render_natal_table({"bodies": SAMPLE_BODIES})
    # Body + sign glyphs are <path> elements
    assert svg.count("<path") >= 2 * len(SAMPLE_BODIES)
    # No emoji / colored-circle fallback characters
    for emoji in ("\U0001F7E0", "\U0001F7E1", "\U0001F7E2", "\U0001F7E3"):
        assert emoji not in svg
    # No Unicode astro glyph text either (♈♉☉☽ etc.)
    for ch in ("\u2648", "\u2649", "\u2609", "\u263D"):
        assert ch not in svg


def test_render_natal_table_dignity_column_populated(renderer):
    """Review item 19: dignity labels computed per body."""
    svg = renderer.render_natal_table({"bodies": SAMPLE_BODIES})
    # Sun in Scorpio -> peregrine; Moon in Taurus @3.5° -> exaltation;
    # Mercury in Scorpio -> peregrine
    assert "Exaltation" in svg
    assert "Peregrine" in svg


def test_render_natal_table_columns_present(renderer):
    svg = renderer.render_natal_table({"bodies": SAMPLE_BODIES})
    for title, _x, _w in COLUMNS:
        assert title in svg


def test_render_natal_table_retro_marker(renderer):
    svg = renderer.render_natal_table({"bodies": SAMPLE_BODIES})
    assert "R" in svg  # Mercury retrograde marker


def test_render_natal_table_empty_chart(renderer):
    svg = renderer.render_natal_table({"bodies": []})
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    # Header still present
    assert "Body" in svg


def test_render_natal_table_unknown_body_does_not_crash(renderer):
    svg = renderer.render_natal_table({
        "bodies": [{"name": "Bogus", "longitude": 10.0, "sign_name": "Aries",
                    "sign_degree": 10.0, "house": 1, "speed": 1.0,
                    "retrograde": False}],
    })
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
