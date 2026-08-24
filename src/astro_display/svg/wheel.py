"""wheel.py — SVG natal / transit / synastry wheel generator.

Renders astrological glyphs as inline SVG <path> outlines (from
``astro_display.glyph_data``) instead of font-face text. librsvg — the
rasterizer behind Gdk.Texture in the GTK GUI — fails to rasterize some
LiberZodiac glyphs from an embedded @font-face and silently falls back to
Noto Color Emoji (colored backgrounds / missing signs). Inline paths are
immune to font fallback.

2026-08-23 rendering revision (user review round 2):
- Glyphs are path-based (no font fallback, no colored emoji)
- Chart orientation is standard: Ascendant left, IC bottom, MC top, Desc right
- Outer ring radius fixed; house band is 33% narrower
- Retrograde mark is a small glyph to the RIGHT of the planet (not radial)
- Aspect lines fade with orb (orb 0 = brightest)
- Transit wheel omits the "(T)" suffix
"""

import math
from typing import Dict, List, Tuple

from astro_data.loaders import yaml_loader
from astro_text.aspects import find_aspect
from astro_text.symbols import symbol_for_sign

from astro_display.fonts import find_font
from astro_display.glyph_data import SIGNS, BODIES, ALL, UPM

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

RETROGRADE_GLYPH = "\u211E"  # ℞ (small superscript text, DejaVu)

ASC_LABEL = "Asc"
MC_LABEL = "MC"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_rad(deg: float) -> float:
    return math.radians(deg)


def _display_angle(longitude: float, ascendant: float) -> float:
    return (longitude - ascendant + 360.0) % 360.0


def _polar(cx: float, cy: float, r: float, display_angle: float) -> Tuple[float, float]:
    """Return SVG (x, y) for a display angle.

    Standard chart orientation (display angle = longitude - ascendant):
      0°   -> left   (Ascendant)
      90°  -> bottom (IC / 4th cusp)
      180° -> right  (Descendant)
      270° -> top    (MC / 10th cusp)
    Zodiac increases counter-clockwise as seen on the chart.
    """
    theta = _to_rad(display_angle)
    x = cx - r * math.cos(theta)
    y = cy + r * math.sin(theta)   # SVG y grows downward
    return x, y


def _aspect_color(aspect: Dict) -> str:
    """Resolve aspect color from astro_data with case-insensitive name matching."""
    aspects_data = yaml_loader("aspects")

    raw_name = aspect.get("aspect_name") or aspect.get("aspect") or ""
    name_key = str(raw_name).lower()

    if name_key in aspects_data:
        return aspects_data[name_key].get("color", "#888888")

    for data in aspects_data.values():
        if str(data.get("name", "")).lower() == name_key:
            return data.get("color", "#888888")

    return "#888888"


def _aspect_orb(aspect: Dict) -> float | None:
    """Best-effort orb value for an aspect dict (float or None)."""
    orb = aspect.get("orb")
    if orb is None:
        return None
    try:
        return float(orb)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Glyph path embedding
# ---------------------------------------------------------------------------
def _path_element(name: str, x: float, y: float, size: float,
                  fill: str = "#ffffff", opacity: float = 1.0,
                  anchor: str = "center") -> str:
    """Emit a <path> for a named glyph, centered at (x, y).

    size is the target height in SVG units; the glyph's outline is scaled
    to fit that height while preserving aspect ratio. anchor controls
    horizontal placement: 'center' centers on x, 'right' puts the glyph's
    right edge at x (for retrograde subscript).

    The stored outlines are in y-up font units; SVG is y-down, so the
    transform flips y (scale(s, -s)) and the translate compensates using
    the glyph's stored center (cx, cy) — this keeps glyphs upright.
    """
    entry = ALL.get(name)
    if entry is None:
        return ""
    s = size / entry["h"]
    # y-flip: x' = dx + s*px,  y' = dy - s*py  (font py is y-up)
    if anchor == "right":
        # right edge (cx + w/2) at x, vertical center at y
        dx = x - (entry["cx"] + entry["w"] / 2.0) * s
    else:
        dx = x - entry["cx"] * s
    dy = y + entry["cy"] * s
    op = f' opacity="{opacity:.2f}"' if opacity < 1.0 else ""
    return (
        f'    <path d="{entry["path"]}" fill="{fill}"{op} '
        f'transform="translate({dx:.2f},{dy:.2f}) scale({s:.4f},{-s:.4f})"/>\n'
    )


def _zodiac_glyph(name: str, x: float, y: float, size: float) -> str:
    return _path_element(name, x, y, size, fill="#aaaaaa")


def _body_glyph(name: str, x: float, y: float, size: float,
                color: str = "#ffffff", opacity: float = 1.0,
                anchor: str = "center") -> str:
    return _path_element(name, x, y, size, fill=color, opacity=opacity, anchor=anchor)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------
class WheelRenderer:
    """Generates SVG astrology wheels from API JSON chart data."""

    def __init__(self, width: int = 600, height: int = 600):
        self.width = width
        self.height = height
        self.cx = width / 2.0
        self.cy = height / 2.0
        # radii — outer ring fixed; house band is 33% narrower than before
        self.R_outer = 266.0
        self.R_inner_house = 208.0    # was 180; band 266-208=58 vs 266-180=86 (33% smaller)
        self.R_planet = 225.0
        self.R_aspect = 165.0
        self.R_sign = 285.0

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

        parts.append(f'  <rect width="{self.width}" height="{self.height}" fill="#1a1a1a"/>\n')
        parts.append(
            f'  <g transform="translate({self.cx},{self.cy}) scale({scale}) '
            f'translate({-self.cx},{-self.cy})">\n'
        )

        parts.extend(self._render_houses(houses, ascendant))
        parts.extend(self._render_cusp_lines(houses, ascendant))
        parts.extend(self._render_sign_labels(ascendant))

        body_lookup = self._aspectable_lookup(bodies, chart_data.get("angles", {}))
        aspects = self._with_asc_aspects(bodies, chart_data.get("angles", {}), aspects)
        parts.extend(self._render_aspects(aspects, body_lookup, ascendant))

        parts.extend(self._render_planets(bodies, ascendant))
        parts.extend(self._render_angle_points(chart_data.get("angles", {}), ascendant))

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
        """Return an SVG string for a transit wheel (two-ring variant)."""
        old_w, old_h = self.width, self.height
        old_cx, old_cy = self.cx, self.cy
        old_ro, old_rp, old_ra, old_rs = self.R_outer, self.R_planet, self.R_aspect, self.R_sign

        self.width, self.height = width, height
        self.cx, self.cy = width / 2.0, height / 2.0
        self.R_outer = 266.0
        self.R_planet = 225.0
        self.R_aspect = 165.0
        self.R_sign = 285.0

        ascendant = natal_data.get("angles", {}).get("ascendant", 0.0)
        natal_houses = natal_data.get("houses", [])
        natal_bodies = natal_data.get("bodies", [])
        transit_bodies = transit_data.get("bodies", [])
        natal_aspects = natal_data.get("aspects", [])
        natal_angles = natal_data.get("angles", {})

        parts: List[str] = []
        parts.append(self._svg_header())
        parts.append(self._defs())
        parts.append(f'  <rect width="{self.width}" height="{self.height}" fill="#1a1a1a"/>\n')
        parts.append(
            f'  <g transform="translate({self.cx},{self.cy}) scale({scale}) '
            f'translate({-self.cx},{-self.cy})">\n'
        )

        parts.extend(self._render_houses(natal_houses, ascendant))
        parts.extend(self._render_cusp_lines(natal_houses, ascendant))
        parts.extend(self._render_sign_labels(ascendant))

        body_lookup = self._aspectable_lookup(natal_bodies, natal_angles)
        natal_aspects = self._with_asc_aspects(natal_bodies, natal_angles, natal_aspects)
        parts.extend(self._render_aspects(natal_aspects, body_lookup, ascendant))

        parts.extend(self._render_planets(natal_bodies, ascendant))
        parts.extend(self._render_angle_points(natal_angles, ascendant))

        # Transit ring divider
        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer - 18}" '
            f'stroke="#555555" stroke-width="1" fill="none"/>\n'
        )

        # Transit planets on outer ring (no "(T)" suffix)
        self.R_planet = 252.0
        parts.extend(self._render_planets(transit_bodies, ascendant, color="#ffd43b"))

        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer}" '
            f'stroke="#666666" stroke-width="1" fill="none"/>\n'
        )

        parts.append("  </g>\n")
        parts.append("</svg>\n")

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
        """Return an SVG string for a synastry wheel (two-ring variant)."""
        old_w, old_h = self.width, self.height
        old_cx, old_cy = self.cx, self.cy
        old_ro, old_rih, old_rp, old_ra, old_rs = (
            self.R_outer, self.R_inner_house, self.R_planet, self.R_aspect, self.R_sign
        )

        self.width, self.height = width, height
        self.cx, self.cy = width / 2.0, height / 2.0
        self.R_outer = 266.0
        self.R_inner_house = 200.0
        self.R_planet = 205.0
        self.R_aspect = 150.0
        self.R_sign = 285.0

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

        parts.extend(self._render_houses(houses_a, ascendant_a))
        parts.extend(self._render_cusp_lines(houses_a, ascendant_a))
        parts.extend(self._render_sign_labels(ascendant_a))

        lookup_a = {b["name"]: b["longitude"] for b in bodies_a}
        lookup_b = {b["name"]: b["longitude"] for b in bodies_b}
        parts.extend(self._render_cross_aspects(cross_aspects, lookup_a, lookup_b, ascendant_a))

        parts.extend(self._render_planets(bodies_a, ascendant_a, color="#ffffff"))

        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer - 18}" '
            f'stroke="#555555" stroke-width="1" fill="none"/>\n'
        )

        self.R_planet = 245.0
        parts.extend(self._render_planets(bodies_b, ascendant_a, color="#ffd43b"))

        parts.append(
            f'    <circle cx="{self.cx}" cy="{self.cy}" r="{self.R_outer}" '
            f'stroke="#666666" stroke-width="1" fill="none"/>\n'
        )

        parts.append("  </g>\n")
        parts.append("</svg>\n")

        self.width, self.height = old_w, old_h
        self.cx, self.cy = old_cx, old_cy
        self.R_outer, self.R_inner_house, self.R_planet, self.R_aspect, self.R_sign = (
            old_ro, old_rih, old_rp, old_ra, old_rs
        )

        return "".join(parts)

    # ------------------------------------------------------------------
    # Aspectable point helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _aspectable_lookup(bodies: List[Dict], angles: Dict) -> Dict[str, float]:
        lookup = {b["name"]: b["longitude"] for b in bodies}
        asc = angles.get("ascendant")
        mc = angles.get("mc")
        if asc is not None:
            lookup[ASC_LABEL] = float(asc)
        if mc is not None:
            lookup[MC_LABEL] = float(mc)
        return lookup

    def _with_asc_aspects(
        self, bodies: List[Dict], angles: Dict, aspects: List[Dict]
    ) -> List[Dict]:
        extra: List[Dict] = []
        asc = angles.get("ascendant")
        mc = angles.get("mc")
        for b in bodies:
            for label, lon in ((ASC_LABEL, asc), (MC_LABEL, mc)):
                if lon is None:
                    continue
                diff = abs((b["longitude"] - float(lon) + 180.0) % 360.0 - 180.0)
                a = find_aspect(diff)
                if a is None:
                    continue
                extra.append({
                    "body_a": b["name"],
                    "body_b": label,
                    "aspect_name": a["name"],
                    "aspect": a["name"],
                    "orb": a["orb"],
                })
        return list(aspects) + extra

    # ------------------------------------------------------------------
    # Building blocks
    # ------------------------------------------------------------------
    def _svg_header(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}">\n'
        )

    def _defs(self) -> str:
        font_path = find_font("regular")
        return (
            '  <defs>\n'
            '    <style>\n'
            f'      @font-face {{\n'
            f'        font-family: "LiberZodiac";\n'
            f'        src: url("file://{font_path}") format("truetype");\n'
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
        houses_sorted = sorted(houses, key=lambda h: h.get("house_num", 0))
        angles = [_display_angle(h["longitude"], ascendant) for h in houses_sorted]
        angles.append(angles[0])

        fills = ["#2a2a2a", "#333333"]
        parts: List[str] = []
        for i in range(len(houses_sorted)):
            a1 = angles[i]
            a2 = angles[i + 1]
            if a2 < a1:
                a2 += 360.0
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
            lon = sign_idx * 30.0 + 15.0
            a = _display_angle(lon, ascendant)
            x, y = _polar(self.cx, self.cy, self.R_sign, a)
            parts.append(_zodiac_glyph(name, x, y, size=22))
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
            color = _aspect_color(asp)
            orb = _aspect_orb(asp)
            # opacity: orb 0 -> 1.0, fading to 0.25 at orb >= 8
            if orb is None:
                opacity = 0.9
            else:
                opacity = max(0.25, min(1.0, 1.0 - (abs(orb) / 10.0)))
            parts.append(
                f'    <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{color}" stroke-width="1.2" opacity="{opacity:.2f}"/>\n'
            )
        return parts

    def _render_cross_aspects(
        self,
        cross_aspects: List[Dict],
        lookup_a: Dict[str, float],
        lookup_b: Dict[str, float],
        ascendant: float,
    ) -> List[str]:
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
            color = _aspect_color(asp)
            orb = _aspect_orb(asp)
            if orb is None:
                opacity = 0.9
            else:
                opacity = max(0.25, min(1.0, 1.0 - (abs(orb) / 10.0)))
            parts.append(
                f'    <line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{color}" stroke-width="1.2" opacity="{opacity:.2f}"/>\n'
            )
        return parts

    def _render_angle_points(self, angles: Dict, ascendant: float) -> List[str]:
        parts: List[str] = []
        for label, key, color in (
            (ASC_LABEL, "ascendant", "#ffffff"),
            (MC_LABEL, "mc", "#ffffff"),
        ):
            lon = angles.get(key)
            if lon is None:
                continue
            a = _display_angle(float(lon), ascendant)
            x_glyph, y_glyph = _polar(self.cx, self.cy, self.R_planet, a)
            x_aspect, y_aspect = _polar(self.cx, self.cy, self.R_aspect, a)
            parts.append(
                f'    <circle cx="{x_aspect:.2f}" cy="{y_aspect:.2f}" r="3.5" fill="#ffd43b"/>\n'
            )
            # label as text (small, DejaVu — no astro glyph needed)
            parts.append(
                f'    <text x="{x_glyph:.2f}" y="{y_glyph:.2f}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="{color}" font-size="11" '
                f'font-family="DejaVu Sans, sans-serif">{label}</text>\n'
            )
        return parts

    def _render_planets(
        self,
        bodies: List[Dict],
        ascendant: float,
        color: str = "#ffffff",
    ) -> List[str]:
        """Draw planet glyph as path at R_planet, circle at R_aspect, degree text outward."""
        parts: List[str] = []
        for b in bodies:
            lon = b.get("longitude", 0.0)
            a = _display_angle(lon, ascendant)

            x_glyph, y_glyph = _polar(self.cx, self.cy, self.R_planet, a)
            x_aspect, y_aspect = _polar(self.cx, self.cy, self.R_aspect, a)

            name = b.get("name", "?")
            retro = b.get("retrograde", False)
            deg = b.get("sign_degree", 0.0)

            # Filled circle at the aspect convergence radius
            parts.append(
                f'    <circle cx="{x_aspect:.2f}" cy="{y_aspect:.2f}" r="3.5" fill="{color}"/>\n'
            )

            # Planet glyph as path (centered)
            parts.append(_body_glyph(name, x_glyph, y_glyph, size=22, color=color))

            # Retrograde: small subscript to the RIGHT and slightly BELOW the
            # planet glyph, regardless of wheel position (not radial)
            if retro:
                parts.append(
                    f'    <text x="{x_glyph + 14:.2f}" y="{y_glyph + 7:.2f}" text-anchor="middle" '
                    f'dominant-baseline="middle" fill="#ff8c8c" font-size="8" '
                    f'font-family="DejaVu Sans, sans-serif">\u211E</text>\n'
                )

            # Degree text just beyond the glyph
            x_deg, y_deg = _polar(self.cx, self.cy, self.R_planet + 16, a)
            deg_label = f"{deg:.0f}°"
            parts.append(
                f'    <text x="{x_deg:.2f}" y="{y_deg:.2f}" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#cccccc" font-size="9" '
                f'font-family="DejaVu Sans, sans-serif">{deg_label}</text>\n'
            )

        return parts


# Retrograde is a Latin-script ℞ — not an astro glyph; render as small text.
