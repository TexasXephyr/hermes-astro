"""wheel_renderer.py — SVG natal / transit / synastry wheel generator."""

import math
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ASPECT_COLORS = {
    "Conjunction": "#ffff00",
    "Opposition": "#ff6b6b",
    "Trine": "#4dabf7",
    "Square": "#ff8787",
    "Sextile": "#69db7c",
}

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Unicode astrological glyphs
PLANET_GLYPHS = {
    "Sun": "\u2609",
    "Moon": "\u263D",
    "Mercury": "\u263F",
    "Venus": "\u2640",
    "Mars": "\u2642",
    "Jupiter": "\u2643",
    "Saturn": "\u2644",
    "Uranus": "\u2645",
    "Neptune": "\u2646",
    "Pluto": "\u2647",
    "Mean Node": "\u260A",
    "True Node": "\u260A",
    "Chiron": "\u26B7",
    "Lilith": "\u26B8",
}

SIGN_GLYPHS = {
    "Aries": "\u2648",
    "Taurus": "\u2649",
    "Gemini": "\u264A",
    "Cancer": "\u264B",
    "Leo": "\u264C",
    "Virgo": "\u264D",
    "Libra": "\u264E",
    "Scorpio": "\u264F",
    "Sagittarius": "\u2650",
    "Capricorn": "\u2651",
    "Aquarius": "\u2652",
    "Pisces": "\u2653",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_rad(deg: float) -> float:
    return math.radians(deg)


def _display_angle(longitude: float, ascendant: float) -> float:
    return (longitude - ascendant + 360.0) % 360.0


def _polar(cx: float, cy: float, r: float, display_angle: float) -> Tuple[float, float]:
    """Return SVG (x, y) for a display angle.

    0° = left, increases CCW.
    """
    theta = _to_rad(display_angle + 180.0)
    x = cx + r * math.cos(theta)
    y = cy + r * math.sin(theta)
    return x, y


class WheelRenderer:
    """Generates SVG astrology wheels from API JSON chart data."""

    def __init__(self, width: int = 600, height: int = 600):
        self.width = width
        self.height = height
        self.cx = width / 2.0
        self.cy = height / 2.0
        # radii
        self.R_outer = 280.0
        self.R_inner_house = 180.0
        self.R_planet = 230.0
        self.R_aspect = 100.0
        self.R_sign = 295.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def render_natal(self, chart_data: Dict, scale: float = 1.0) -> str:
        """Return an SVG string for a natal wheel."""
        ascendant = chart_data.get("angles", {}).get("ascendant", 0.0)
        houses = chart_data.get("houses", [])
        bodies = chart_data.get("bodies", [])
        aspects = chart_data.get("aspects", [])

        parts: List[str] = []
        parts.append(self._svg_header())
        parts.append(self._defs())

        # Background
        parts.append(f'  <rect width="{self.width}" height="{self.height}" fill="#1a1a1a"/>\n')

        # Zoomable root group
        parts.append(
            f'  <g transform="translate({self.cx},{self.cy}) scale({scale}) '
            f'translate({-self.cx},{-self.cy})">\n'
        )

        # House segments
        parts.extend(self._render_houses(houses, ascendant))

        # Cusp lines
        parts.extend(self._render_cusp_lines(houses, ascendant))

        # Sign labels
        parts.extend(self._render_sign_labels(ascendant))

        # Aspect lines (inner)
        body_lookup = {b["name"]: b["longitude"] for b in bodies}
        parts.extend(self._render_aspects(aspects, body_lookup, ascendant))

        # Planets
        parts.extend(self._render_planets(bodies, ascendant))

        # Outer rim circle
        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer}" '
            f'stroke="#666666" stroke-width="1" fill="none"/>\n'
        )

        parts.append("  </g>\n")
        parts.append("</svg>\n")
        return "".join(parts)

    def render_transit(
        self,
        natal_data: Dict,
        transit_data: Dict,
        width: int = 600,
        height: int = 600,
        scale: float = 1.0,
    ) -> str:
        """Return an SVG string for a transit wheel (two-ring variant).

        Inner ring = natal, outer ring = transit.
        Simplified V1: render natal inner, overlay transit planets on outer radius.
        """
        # Save current dims
        old_w, old_h = self.width, self.height
        old_cx, old_cy = self.cx, self.cy
        old_ro, old_rp, old_ra, old_rs = self.R_outer, self.R_planet, self.R_aspect, self.R_sign

        self.width, self.height = width, height
        self.cx, self.cy = width / 2.0, height / 2.0
        self.R_outer = 280.0
        self.R_planet = 220.0          # natal planets a bit inward
        self.R_aspect = 90.0
        self.R_sign = 295.0

        ascendant = natal_data.get("angles", {}).get("ascendant", 0.0)
        natal_houses = natal_data.get("houses", [])
        natal_bodies = natal_data.get("bodies", [])
        transit_bodies = transit_data.get("bodies", [])
        natal_aspects = natal_data.get("aspects", [])

        parts: List[str] = []
        parts.append(self._svg_header())
        parts.append(self._defs())
        parts.append(f'  <rect width="{self.width}" height="{self.height}" fill="#1a1a1a"/>\n')
        parts.append(
            f'  <g transform="translate({self.cx},{self.cy}) scale({scale}) '
            f'translate({-self.cx},{-self.cy})">\n'
        )

        # Natal houses (inner)
        parts.extend(self._render_houses(natal_houses, ascendant))
        parts.extend(self._render_cusp_lines(natal_houses, ascendant))
        parts.extend(self._render_sign_labels(ascendant))

        # Natal aspects (inner)
        body_lookup = {b["name"]: b["longitude"] for b in natal_bodies}
        parts.extend(self._render_aspects(natal_aspects, body_lookup, ascendant))

        # Natal planets
        parts.extend(self._render_planets(natal_bodies, ascendant))

        # Transit ring divider
        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer - 20}" '
            f'stroke="#555555" stroke-width="1" fill="none"/>\n'
        )

        # Transit planets on outer ring
        self.R_planet = 260.0
        parts.extend(self._render_planets(transit_bodies, ascendant, suffix=" (T)", color="#ffd43b"))

        # Outer rim
        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer}" '
            f'stroke="#666666" stroke-width="1" fill="none"/>\n'
        )

        parts.append("  </g>\n")
        parts.append("</svg>\n")

        # Restore
        self.width, self.height = old_w, old_h
        self.cx, self.cy = old_cx, old_cy
        self.R_outer, self.R_planet, self.R_aspect, self.R_sign = old_ro, old_rp, old_ra, old_rs

        return "".join(parts)

    def render_synastry(
        self,
        chart_a_data: Dict,
        chart_b_data: Dict,
        cross_aspects: List[Dict],
        width: int = 600,
        height: int = 600,
        scale: float = 1.0,
    ) -> str:
        """Return an SVG string for a synastry wheel (two-ring variant).

        Inner ring = Person A natal, outer ring = Person B natal overlaid.
        Cross aspects drawn between the two rings.
        """
        # Save current dims
        old_w, old_h = self.width, self.height
        old_cx, old_cy = self.cx, self.cy
        old_ro, old_rih, old_rp, old_ra, old_rs = (
            self.R_outer, self.R_inner_house, self.R_planet, self.R_aspect, self.R_sign
        )

        self.width, self.height = width, height
        self.cx, self.cy = width / 2.0, height / 2.0
        self.R_outer = 280.0
        self.R_inner_house = 160.0   # slightly smaller inner
        self.R_planet = 200.0        # Person A planets inward
        self.R_aspect = 120.0
        self.R_sign = 295.0

        ascendant_a = chart_a_data.get("angles", {}).get("ascendant", 0.0)
        houses_a = chart_a_data.get("houses", [])
        bodies_a = chart_a_data.get("bodies", [])
        bodies_b = chart_b_data.get("bodies", [])

        parts: List[str] = []
        parts.append(self._svg_header())
        parts.append(self._defs())
        parts.append(f'  <rect width="{self.width}" height="{self.height}" fill="#1a1a1a"/>\n')
        parts.append(
            f'  <g transform="translate({self.cx},{self.cy}) scale({scale}) '
            f'translate({-self.cx},{-self.cy})">\n'
        )

        # Person A houses (inner)
        parts.extend(self._render_houses(houses_a, ascendant_a))
        parts.extend(self._render_cusp_lines(houses_a, ascendant_a))
        parts.extend(self._render_sign_labels(ascendant_a))

        # Cross aspects between Person A and Person B
        lookup_a = {b["name"]: b["longitude"] for b in bodies_a}
        lookup_b = {b["name"]: b["longitude"] for b in bodies_b}
        parts.extend(self._render_cross_aspects(cross_aspects, lookup_a, lookup_b, ascendant_a))

        # Person A planets (inner ring)
        parts.extend(self._render_planets(bodies_a, ascendant_a, suffix="", color="#ffffff"))

        # Person B ring divider
        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer - 20}" '
            f'stroke="#555555" stroke-width="1" fill="none"/>\n'
        )

        # Person B planets (outer ring)
        self.R_planet = 260.0
        parts.extend(self._render_planets(bodies_b, ascendant_a, suffix=" (B)", color="#ffd43b"))

        # Outer rim
        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer}" '
            f'stroke="#666666" stroke-width="1" fill="none"/>\n'
        )

        parts.append("  </g>\n")
        parts.append("</svg>\n")

        # Restore
        self.width, self.height = old_w, old_h
        self.cx, self.cy = old_cx, old_cy
        self.R_outer, self.R_inner_house, self.R_planet, self.R_aspect, self.R_sign = (
            old_ro, old_rih, old_rp, old_ra, old_rs
        )

        return "".join(parts)

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------
    def _svg_header(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}">\n'
        )

    _FONT_PATH = "/home/xephyr/.local/share/fonts/LiberZodiac-Regular.ttf"

    def _defs(self) -> str:
        return (
            '  <defs>\n'
            '    <style>\n'
            f'      @font-face {{\n'
            f'        font-family: "LiberZodiac";\n'
            f'        src: url("file://{self._FONT_PATH}") format("truetype");\n'
            f'        font-weight: normal;\n'
            f'        font-style: normal;\n'
            f'      }}\n'
            '    </style>\n'
            '    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">\n'
            '      <feGaussianBlur stdDeviation="1.5" result="blur"/>\n'
            '      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>\n'
            '    </filter>\n'
            '  </defs>\n'
        )

    def _render_houses(self, houses: List[Dict], ascendant: float) -> List[str]:
        if not houses:
            return []
        # Sort by house number, compute display angles
        houses_sorted = sorted(houses, key=lambda h: h.get("house_num", 0))
        angles = [_display_angle(h["longitude"], ascendant) for h in houses_sorted]
        # Append first angle again to close the circle
        angles.append(angles[0])

        fills = ["#2a2a2a", "#333333"]
        parts: List[str] = []
        for i in range(len(houses_sorted)):
            a1 = angles[i]
            a2 = angles[i + 1]
            # Wrap-around fix: if a2 < a1, add 360
            if a2 < a1:
                a2 += 360.0
            # Draw wedge as polygon
            p1_out = _polar(self.cx, self.cy, self.R_outer, a1)
            p2_out = _polar(self.cx, self.cy, self.R_outer, a2)
            p2_in = _polar(self.cx, self.cy, self.R_inner_house, a2)
            p1_in = _polar(self.cx, self.cy, self.R_inner_house, a1)
            pts = f"{p1_out[0]:.2f},{p1_out[1]:.2f} {p2_out[0]:.2f},{p2_out[1]:.2f} {p2_in[0]:.2f},{p2_in[1]:.2f} {p1_in[0]:.2f},{p1_in[1]:.2f}"
            fill = fills[i % 2]
            parts.append(
                f'    <polygon points="{pts}" fill="{fill}" stroke="none" opacity="0.6"/>\n'
            )
        return parts

    def _render_cusp_lines(self, houses: List[Dict], ascendant: float) -> List[str]:
        parts: List[str] = []
        for h in houses:
            a = _display_angle(h["longitude"], ascendant)
            x1, y1 = _polar(self.cx, self.cy, self.R_inner_house, a)
            x2, y2 = _polar(self.cx, self.cy, self.R_outer, a)
            parts.append(
                f'    <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="#666666" stroke-width="0.8"/>\n'
            )
        return parts

    def _render_sign_labels(self, ascendant: float) -> List[str]:
        parts: List[str] = []
        for sign_idx, name in enumerate(SIGN_NAMES):
            lon = sign_idx * 30.0 + 15.0  # midpoint of sign
            a = _display_angle(lon, ascendant)
            x, y = _polar(self.cx, self.cy, self.R_sign, a)
            glyph = SIGN_GLYPHS.get(name, name[:3])
            parts.append(
                f'    <text x="{x:.2f}" y="{y:.2f}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#aaaaaa" font-size="18" '
                f'font-family="LiberZodiac, DejaVu Sans, sans-serif">{glyph}</text>\n'
            )
        return parts

    def _render_aspects(
        self, aspects: List[Dict], body_lookup: Dict[str, float], ascendant: float
    ) -> List[str]:
        parts: List[str] = []
        for asp in aspects:
            a_name = asp.get("body_a")
            b_name = asp.get("body_b")
            lon_a = body_lookup.get(str(a_name))
            lon_b = body_lookup.get(str(b_name))
            if lon_a is None or lon_b is None:
                continue
            ang_a = _display_angle(lon_a, ascendant)
            ang_b = _display_angle(lon_b, ascendant)
            x1, y1 = _polar(self.cx, self.cy, self.R_aspect, ang_a)
            x2, y2 = _polar(self.cx, self.cy, self.R_aspect, ang_b)
            color = ASPECT_COLORS.get(asp.get("aspect_name", ""), "#888888")
            parts.append(
                f'    <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{color}" stroke-width="1.2" opacity="0.9"/>\n'
            )
        return parts

    def _render_cross_aspects(
        self,
        cross_aspects: List[Dict],
        lookup_a: Dict[str, float],
        lookup_b: Dict[str, float],
        ascendant: float,
    ) -> List[str]:
        """Draw synastry cross-aspects: natal body A on inner ring, body B on outer ring."""
        parts: List[str] = []
        for asp in cross_aspects:
            a_name = asp.get("body_a") or asp.get("natal_body")
            b_name = asp.get("body_b") or asp.get("transit_body")
            lon_a = lookup_a.get(str(a_name))
            lon_b = lookup_b.get(str(b_name))
            if lon_a is None or lon_b is None:
                continue
            ang_a = _display_angle(lon_a, ascendant)
            ang_b = _display_angle(lon_b, ascendant)
            x1, y1 = _polar(self.cx, self.cy, self.R_aspect - 20, ang_a)
            x2, y2 = _polar(self.cx, self.cy, self.R_aspect + 20, ang_b)
            color = ASPECT_COLORS.get(asp.get("aspect_name", ""), "#888888")
            parts.append(
                f'    <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{color}" stroke-width="1.2" opacity="0.9"/>\n'
            )
        return parts

    def _render_planets(
        self,
        bodies: List[Dict],
        ascendant: float,
        suffix: str = "",
        color: str = "#ffffff",
    ) -> List[str]:
        """Draw planet glyph at R_planet, filled circle at R_aspect, degree text outward."""
        parts: List[str] = []
        for b in bodies:
            lon = b.get("longitude", 0.0)
            a = _display_angle(lon, ascendant)

            # Coordinates at different radii
            x_glyph, y_glyph = _polar(self.cx, self.cy, self.R_planet, a)
            x_aspect, y_aspect = _polar(self.cx, self.cy, self.R_aspect, a)

            name = b.get("name", "?")
            retro = b.get("retrograde", False)
            sign = b.get("sign_name", "?")
            deg = b.get("sign_degree", 0.0)

            glyph = PLANET_GLYPHS.get(name, name[:2])
            if retro:
                glyph = str(glyph) + "\u211E"  # ℞ retrograde

            # Filled circle at the aspect convergence radius
            parts.append(
                f'    <circle cx="{x_aspect:.2f}" cy="{y_aspect:.2f}" r="3.5" fill="{color}"/>\n'
            )

            # Planet glyph at R_planet (farther out)
            parts.append(
                f'    <text x="{x_glyph:.2f}" y="{y_glyph:.2f}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="{color}" font-size="18" '
                f'font-family="LiberZodiac, DejaVu Sans, sans-serif">{glyph}</text>\n'
            )

            # Degree text just beyond the glyph
            x_deg, y_deg = _polar(self.cx, self.cy, self.R_planet + 18, a)
            deg_label = f"{deg:.0f}°"
            parts.append(
                f'    <text x="{x_deg:.2f}" y="{y_deg:.2f}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#cccccc" font-size="9" '
                f'font-family="DejaVu Sans, sans-serif">{deg_label}</text>\n'
            )

        return parts
