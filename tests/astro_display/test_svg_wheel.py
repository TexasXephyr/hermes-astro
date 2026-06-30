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
    assert "Sun" in svg or "☉" in svg
    assert "Moon" in svg or "☽" in svg
    assert "#69db7c" in svg  # sextile color


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
    assert "(T)" in svg


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
    assert "(B)" in svg
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
