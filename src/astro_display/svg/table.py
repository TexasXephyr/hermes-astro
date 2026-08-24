"""table.py — SVG table renderer for the astrology GUI.

Renders the natal planet table as an SVG with path-based astrological
glyphs (from ``astro_display.glyph_data``) instead of Unicode text
glyphs, so librsvg never falls back to Noto Color Emoji. Text is
Liberation Sans (the base of LiberZodiac); glyphs are inline <path>
outlines, exactly like the wheel renderer.

2026-08-24 (user review items 18-20):
- Natal Table renders as SVG with path glyphs (no emoji zodiac signs)
- Dignity column computed via astro_text.dignity.get_dignity
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from astro_text.dignity import get_dignity
from astro_text.format import format_degree

from astro_display.svg.wheel import _path_element

# Column layout: (title, x, width)
COLUMNS: List[Tuple[str, float, float]] = [
    ("Body", 20, 190),
    ("Sign", 210, 170),
    ("Degree", 380, 90),
    ("House", 470, 70),
    ("Dignity", 540, 150),
    ("Speed", 690, 90),
    ("Retro", 780, 60),
]

WIDTH = 880
ROW_HEIGHT = 34
HEADER_HEIGHT = 30
MARGIN_TOP = 12
MARGIN_BOTTOM = 12

_BG_ROW = ("#2a2a2a", "#333333")
_HEADER_BG = "#222222"
_HEADER_FG = "#cccccc"
_TEXT_FG = "#dddddd"
_DIM_FG = "#cccccc"
_RETRO_FG = "#ff8c8c"
_SIGN_GLYPH_FG = "#aaaaaa"
_BODY_GLYPH_FG = "#ffffff"

_FONT = "Liberation Sans, DejaVu Sans, sans-serif"


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _cell_text(x: float, cy: float, text: str, fill: str = _DIM_FG,
               font_size: int = 13) -> str:
    """Emit a left-aligned text cell in the table font."""
    return (
        f'    <text x="{x:.0f}" y="{cy:.1f}" text-anchor="start" '
        f'dominant-baseline="middle" fill="{fill}" font-size="{font_size}" '
        f'font-family="{_FONT}">{_escape(text)}</text>\n'
    )


class TableRenderer:
    """Generates SVG tables (natal planet table) with path glyphs."""

    def __init__(self, width: int = WIDTH, row_height: int = ROW_HEIGHT):
        self.width = width
        self.row_height = row_height

    def render_natal_table(self, chart: Dict) -> str:
        """Return an SVG string for the natal planet table.

        Columns: Body (glyph + name), Sign (glyph + name), Degree,
        House, Dignity, Speed, Retro. Rows are sorted by longitude.
        """
        bodies = sorted(
            chart.get("bodies", []), key=lambda b: b.get("longitude", 0.0)
        )
        n = len(bodies)
        height = MARGIN_TOP + HEADER_HEIGHT + n * self.row_height + MARGIN_BOTTOM

        parts: List[str] = []
        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{height}" viewBox="0 0 {self.width} {height}">\n'
        )
        parts.append(
            f'  <rect width="{self.width}" height="{height}" fill="#1a1a1a"/>\n'
        )

        # Header row
        parts.append(
            f'  <rect x="0" y="{MARGIN_TOP}" width="{self.width}" '
            f'height="{HEADER_HEIGHT}" fill="{_HEADER_BG}"/>\n'
        )
        header_cy = MARGIN_TOP + HEADER_HEIGHT / 2.0
        for title, x, _w in COLUMNS:
            parts.append(
                f'    <text x="{x + 8:.0f}" y="{header_cy:.1f}" '
                f'text-anchor="start" dominant-baseline="middle" '
                f'fill="{_HEADER_FG}" font-size="13" font-weight="bold" '
                f'font-family="{_FONT}">{_escape(title)}</text>\n'
            )

        # Body rows
        for i, b in enumerate(bodies):
            y_top = MARGIN_TOP + HEADER_HEIGHT + i * self.row_height
            cy = y_top + self.row_height / 2.0
            parts.append(
                f'  <rect x="0" y="{y_top:.0f}" width="{self.width}" '
                f'height="{self.row_height}" fill="{_BG_ROW[i % 2]}"/>\n'
            )

            name = str(b.get("name", "?"))
            sign = str(b.get("sign_name", "?"))
            sign_degree = b.get("sign_degree", 0.0)
            house = str(b.get("house", "-"))
            speed = f"{b.get('speed', 0.0):.3f}"
            retro = "R" if b.get("retrograde") else ""

            dignity = ""
            try:
                dignity = get_dignity(name, sign, sign_degree=sign_degree)["label"]
            except Exception:
                dignity = ""

            # Body: glyph + name
            parts.append(_path_element(name, 20 + 18, cy, size=20, fill=_BODY_GLYPH_FG))
            parts.append(_cell_text(20 + 46, cy, name, fill=_TEXT_FG))

            # Sign: glyph + name
            parts.append(_path_element(sign, 210 + 18, cy, size=18, fill=_SIGN_GLYPH_FG))
            parts.append(_cell_text(210 + 44, cy, sign, fill=_TEXT_FG))

            # Degree / House / Dignity / Speed / Retro
            parts.append(_cell_text(380 + 8, cy, format_degree(sign_degree)))
            parts.append(_cell_text(470 + 8, cy, house))
            parts.append(_cell_text(540 + 8, cy, dignity.capitalize()))
            parts.append(_cell_text(690 + 8, cy, speed))
            if retro:
                parts.append(_cell_text(780 + 8, cy, retro, fill=_RETRO_FG))

        parts.append("</svg>\n")
        return "".join(parts)
