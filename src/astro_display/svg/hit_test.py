"""hit_test.py — Hover hit-testing for the wheel views.

Builds a set of hotspots that mirror the geometry the SVG renderer draws
(identical polar math, radii, and labels), then answers "what is under
(x, y)?" for the hover inspector.

Hotspot kinds:
  planet  — glyph position (R_planet) + aspect dot (R_aspect)
  aspect  — a line segment between two aspect-ring dots
  sign    — the zodiac glyph at R_sign
  house   — the angular wedge in the house band (R_inner_house..R_outer)
  angle   — Asc / MC point

Priority for ties: planet > aspect > angle > sign > house (a planet
sitting in a house band should win over the house itself).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from astro_display.svg.wheel import (
    _polar,
    _display_angle,
    ASC_LABEL,
    MC_LABEL,
    SIGN_NAMES,
)

# Radii mirroring wheel.py (natal defaults; transit/synastry override)
R_PLANET_NATAL = 225.0
R_ASPECT_NATAL = 165.0
R_SIGN = 285.0
R_OUTER = 266.0
R_INNER_HOUSE = 208.0
R_PLANET_TRANSIT = 252.0
R_PLANET_SYNASTRY_A = 205.0
R_PLANET_SYNASTRY_B = 245.0
R_ASPECT_SYNASTRY = 150.0
R_INNER_HOUSE_SYNASTRY = 200.0

# Hit radii (SVG units)
PLANET_HIT_R = 16.0
ASPECT_DOT_HIT_R = 10.0
SIGN_HIT_R = 18.0
ANGLE_HIT_R = 12.0
ASPECT_LINE_HIT = 6.0
HOUSE_HIT_R = 12.0  # angular tolerance in degrees for house wedges


@dataclass
class Hotspot:
    kind: str            # planet | aspect | sign | house | angle
    label: str
    x: float
    y: float
    data: dict = field(default_factory=dict)
    priority: int = 0    # higher wins ties
    # For aspect lines: the two endpoints (for point-to-segment distance)
    x2: float | None = None
    y2: float | None = None


def _dist(px: float, py: float, qx: float, qy: float) -> float:
    return math.hypot(px - qx, py - qy)


def _seg_dist(px: float, py: float, x1: float, y1: float,
              x2: float, y2: float) -> float:
    """Distance from point P to segment (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return _dist(px, py, x1, y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return _dist(px, py, x1 + t * dx, y1 + t * dy)


def _planet_hotspots(bodies: List[Dict], ascendant: float, cx: float, cy: float,
                     r_planet: float, r_aspect: float, color: str = "#ffffff",
                     kind: str = "planet", priority: int = 4) -> List[Hotspot]:
    out = []
    for b in bodies:
        lon = float(b.get("longitude", 0.0))
        a = _display_angle(lon, ascendant)
        xg, yg = _polar(cx, cy, r_planet, a)
        xa, ya = _polar(cx, cy, r_aspect, a)
        name = b.get("name", "?")
        out.append(Hotspot(
            kind=kind, label=name, x=xg, y=yg, priority=priority,
            data={"body": name, "longitude": lon, "color": color,
                  "dot_x": xa, "dot_y": ya},
        ))
    return out


def _aspect_hotspots(aspects: List[Dict], lookup: Dict[str, float],
                     ascendant: float, cx: float, cy: float,
                     r: float, kind: str = "aspect") -> List[Hotspot]:
    out = []
    for asp in aspects:
        a_name = str(asp.get("body_a") or asp.get("transit_body") or "")
        b_name = str(asp.get("body_b") or asp.get("natal_body") or "")
        lon_a = lookup.get(a_name)
        lon_b = lookup.get(b_name)
        if lon_a is None or lon_b is None:
            continue
        ang_a = _display_angle(lon_a, ascendant)
        ang_b = _display_angle(lon_b, ascendant)
        x1, y1 = _polar(cx, cy, r, ang_a)
        x2, y2 = _polar(cx, cy, r, ang_b)
        out.append(Hotspot(
            kind=kind, label=f"{a_name} {asp.get('aspect_name') or asp.get('aspect')} {b_name}",
            x=(x1 + x2) / 2.0, y=(y1 + y2) / 2.0, priority=3,
            x2=x2, y2=y2,
            data={"body_a": a_name, "body_b": b_name,
                  "aspect": asp.get("aspect_name") or asp.get("aspect"),
                  "orb": asp.get("orb"), "applying": asp.get("applying"),
                  "x1": x1, "y1": y1},
        ))
    return out


def _sign_hotspots(ascendant: float, cx: float, cy: float) -> List[Hotspot]:
    out = []
    for sign_idx, name in enumerate(SIGN_NAMES):
        lon = sign_idx * 30.0 + 15.0
        a = _display_angle(lon, ascendant)
        x, y = _polar(cx, cy, R_SIGN, a)
        out.append(Hotspot(
            kind="sign", label=name, x=x, y=y, priority=1,
            data={"sign": name, "longitude": lon},
        ))
    return out


def _house_hotspots(houses: List[Dict], ascendant: float, cx: float, cy: float,
                    r_inner: float = R_INNER_HOUSE,
                    r_outer: float = R_OUTER) -> List[Hotspot]:
    """House wedges: a hotspot at the wedge centroid (mid-angle, mid-radius)."""
    out = []
    if not houses:
        return out
    houses_sorted = sorted(houses, key=lambda h: h.get("house_num", 0))
    angles = [_display_angle(h["longitude"], ascendant) for h in houses_sorted]
    for i, h in enumerate(houses_sorted):
        a1 = angles[i]
        a2 = angles[(i + 1) % len(angles)]
        if a2 <= a1:
            a2 += 360.0
        mid = (a1 + a2) / 2.0
        r_mid = (r_inner + r_outer) / 2.0
        x, y = _polar(cx, cy, r_mid, mid)
        out.append(Hotspot(
            kind="house", label=f"House {h.get('house_num', i + 1)}",
            x=x, y=y, priority=0,
            data={"house": h.get("house_num", i + 1), "a1": a1, "a2": a2,
                  "r_inner": r_inner, "r_outer": r_outer,
                  "cx": cx, "cy": cy},
        ))
    return out


def _angle_hotspots(angles: Dict, ascendant: float, cx: float, cy: float,
                    r_planet: float, r_aspect: float) -> List[Hotspot]:
    out = []
    for label, key in ((ASC_LABEL, "ascendant"), (MC_LABEL, "mc")):
        lon = angles.get(key)
        if lon is None:
            continue
        a = _display_angle(float(lon), ascendant)
        xg, yg = _polar(cx, cy, r_planet, a)
        xa, ya = _polar(cx, cy, r_aspect, a)
        out.append(Hotspot(
            kind="angle", label=label, x=xg, y=yg, priority=2,
            data={"angle": label, "longitude": float(lon),
                  "dot_x": xa, "dot_y": ya},
        ))
    return out


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------

def build_natal_hotspots(chart: Dict, cx: float = 300.0, cy: float = 300.0) -> List[Hotspot]:
    ascendant = float(chart.get("angles", {}).get("ascendant", 0.0))
    bodies = chart.get("bodies", [])
    houses = chart.get("houses", [])
    aspects = chart.get("aspects", [])
    lookup = {b["name"]: b["longitude"] for b in bodies}
    asc = chart.get("angles", {}).get("ascendant")
    mc = chart.get("angles", {}).get("mc")
    if asc is not None:
        lookup[ASC_LABEL] = float(asc)
    if mc is not None:
        lookup[MC_LABEL] = float(mc)

    out = []
    out.extend(_planet_hotspots(bodies, ascendant, cx, cy,
                                R_PLANET_NATAL, R_ASPECT_NATAL))
    out.extend(_aspect_hotspots(aspects, lookup, ascendant, cx, cy, R_ASPECT_NATAL))
    out.extend(_sign_hotspots(ascendant, cx, cy))
    out.extend(_house_hotspots(houses, ascendant, cx, cy))
    out.extend(_angle_hotspots(chart.get("angles", {}), ascendant, cx, cy,
                               R_PLANET_NATAL, R_ASPECT_NATAL))
    return out


def build_transit_hotspots(natal: Dict, transit: Dict, cx: float = 300.0,
                           cy: float = 300.0) -> List[Hotspot]:
    ascendant = float(natal.get("angles", {}).get("ascendant", 0.0))
    natal_bodies = natal.get("bodies", [])
    transit_bodies = transit.get("bodies", [])
    houses = natal.get("houses", [])
    cross = transit.get("cross_aspects", [])

    natal_lookup = {b["name"]: b["longitude"] for b in natal_bodies}
    transit_lookup = {b["name"]: b["longitude"] for b in transit_bodies}

    out = []
    # Natal planets (inner ring) + transit planets (outer ring).
    # Transit planets get HIGHER priority than natal planets: the two
    # rings are only 27px apart with 16px hit circles, so a conjunct
    # transit/natal pair overlaps — the outer ring should win the hover
    # (2026-08-24: hovering a transiting planet showed natal info).
    out.extend(_planet_hotspots(natal_bodies, ascendant, cx, cy,
                                R_PLANET_NATAL, R_ASPECT_NATAL, color="#ffffff",
                                priority=4))
    out.extend(_planet_hotspots(transit_bodies, ascendant, cx, cy,
                                R_PLANET_TRANSIT, R_ASPECT_NATAL, color="#ffd43b",
                                kind="planet", priority=5))
    # Cross aspects (transit-natal) on the aspect ring
    out.extend(_aspect_hotspots(cross, {**transit_lookup, **natal_lookup},
                                ascendant, cx, cy, R_ASPECT_NATAL))
    out.extend(_sign_hotspots(ascendant, cx, cy))
    out.extend(_house_hotspots(houses, ascendant, cx, cy))
    out.extend(_angle_hotspots(natal.get("angles", {}), ascendant, cx, cy,
                               R_PLANET_NATAL, R_ASPECT_NATAL))
    return out


def build_synastry_hotspots(chart_a: Dict, chart_b: Dict, cross: List[Dict],
                            cx: float = 300.0, cy: float = 300.0) -> List[Hotspot]:
    ascendant = float(chart_a.get("angles", {}).get("ascendant", 0.0))
    bodies_a = chart_a.get("bodies", [])
    bodies_b = chart_b.get("bodies", [])
    houses_a = chart_a.get("houses", [])

    lookup_a = {b["name"]: b["longitude"] for b in bodies_a}
    lookup_b = {b["name"]: b["longitude"] for b in bodies_b}

    out = []
    # Person A (inner) vs person B (outer) — same overlap concern as the
    # transit wheel, so B wins the hover on a conjunct pair.
    out.extend(_planet_hotspots(bodies_a, ascendant, cx, cy,
                                R_PLANET_SYNASTRY_A, R_ASPECT_SYNASTRY, color="#ffffff",
                                priority=4))
    out.extend(_planet_hotspots(bodies_b, ascendant, cx, cy,
                                R_PLANET_SYNASTRY_B, R_ASPECT_SYNASTRY, color="#ffd43b",
                                priority=5))
    out.extend(_aspect_hotspots(cross, {**lookup_a, **lookup_b},
                                ascendant, cx, cy, R_ASPECT_SYNASTRY))
    out.extend(_sign_hotspots(ascendant, cx, cy))
    out.extend(_house_hotspots(houses_a, ascendant, cx, cy,
                               R_INNER_HOUSE_SYNASTRY, R_OUTER))
    out.extend(_angle_hotspots(chart_a.get("angles", {}), ascendant, cx, cy,
                               R_PLANET_SYNASTRY_A, R_ASPECT_SYNASTRY))
    return out


# ---------------------------------------------------------------------------
# Hit testing
# ---------------------------------------------------------------------------

def hit_test(x: float, y: float, hotspots: List[Hotspot],
             threshold: float = 24.0) -> List[Hotspot]:
    """Return hotspots under (x, y), best first.

    Planets/aspect-dots/signs/angles use point distance; aspect lines use
    point-to-segment distance; houses use angular wedge membership (only
    when the point is inside the house band). Ties break by priority.
    """
    hits = []
    for h in hotspots:
        if h.kind == "aspect" and h.x2 is not None:
            d = _seg_dist(x, y, h.x, h.y, h.x2, h.y2)
            if d <= ASPECT_LINE_HIT:
                hits.append((d, h))
        elif h.kind == "house":
            cx = h.data.get("cx") or 0.0
            cy = h.data.get("cy") or 0.0
            r = math.hypot(x - cx, y - cy)
            r_inner = h.data.get("r_inner") or 0.0
            r_outer = h.data.get("r_outer") or 0.0
            if r_inner <= r <= r_outer:
                ang = math.degrees(math.atan2(y - cy, cx - x)) % 360.0
                a1 = h.data["a1"] % 360.0
                a2 = h.data["a2"] % 360.0
                if a1 <= a2:
                    inside = a1 <= ang <= a2
                else:
                    inside = ang >= a1 or ang <= a2
                if inside:
                    hits.append((0.0, h))
        else:
            r = PLANET_HIT_R if h.kind == "planet" else (
                ASPECT_DOT_HIT_R if h.kind == "angle" else
                SIGN_HIT_R if h.kind == "sign" else 0.0)
            d = _dist(x, y, h.x, h.y)
            if d <= r:
                hits.append((d, h))

    hits.sort(key=lambda t: (-t[1].priority, t[0]))
    return [h for _, h in hits]


# ---------------------------------------------------------------------------
# Widget -> SVG coordinate conversion (Gtk.Picture CONTAIN fit)
# ---------------------------------------------------------------------------

def widget_to_svg(x: float, y: float, widget_w: float, widget_h: float,
                  svg_w: float = 600.0, svg_h: float = 600.0) -> Tuple[float | None, float | None]:
    """Map widget coordinates to SVG coordinates for a CONTAIN-fit Picture.

    The SVG is scaled to fit inside the widget while preserving aspect
    ratio, then centered. Returns (svg_x, svg_y) or (None, None) when
    the point is outside the rendered image.
    """
    if widget_w <= 0 or widget_h <= 0:
        return None, None
    scale = min(widget_w / svg_w, widget_h / svg_h)
    draw_w = svg_w * scale
    draw_h = svg_h * scale
    off_x = (widget_w - draw_w) / 2.0
    off_y = (widget_h - draw_h) / 2.0
    if not (off_x <= x <= off_x + draw_w and off_y <= y <= off_y + draw_h):
        return None, None
    return (x - off_x) / scale, (y - off_y) / scale
