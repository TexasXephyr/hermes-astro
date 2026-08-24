"""wheel_hover.py — Markup assembly for the wheel hover inspector.

Turns a hit-tested Hotspot into a markup string for the HoverPanel,
using the chart data and a precomputed cookbook index.

The cookbook index maps (domain, key) -> text, built once per wheel
load from the astro_transit_cookbook builders (natal / transit /
synastry). Keys follow the corpus convention: natal-sign:{body}-{sign},
natal-house:{body}-{house}, aspect:{body}-{aspect}, transit-*,
synastry-*.
"""
from __future__ import annotations

from typing import Dict, List

from astro_text.symbols import symbol_for_body, symbol_for_sign, symbol_for_aspect
from astro_text.format import format_degree


def _glyph_body(name: str) -> str:
    glyph = symbol_for_body(name) or ""
    return f"{glyph} {name}".strip()


def _glyph_sign(name: str) -> str:
    if not name:
        return ""
    try:
        glyph = symbol_for_sign(name)
    except KeyError:
        glyph = ""
    return f"{glyph} {name}".strip()


def _glyph_aspect(name: str) -> str:
    if not name:
        return ""
    try:
        glyph = symbol_for_aspect(name)
    except KeyError:
        glyph = ""
    return f"{glyph} {name}".strip()


def _esc(text) -> str:
    """Escape text for Pango markup."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _cookbook_text(index: Dict, domain: str, key: str) -> str | None:
    return index.get((domain, key))


def _aspect_rows_for_body(index: Dict, domain: str, body: str,
                          aspects: List[Dict], a_key: str, b_key: str) -> List[str]:
    """Cookbook rows for aspects involving `body` (domain e.g. 'aspect')."""
    rows = []
    for asp in aspects:
        a = str(asp.get(a_key) or "")
        b = str(asp.get(b_key) or "")
        if body not in (a, b):
            continue
        aspect = str(asp.get("aspect_name") or asp.get("aspect") or "")
        other = b if a == body else a
        text = _cookbook_text(index, domain, f"{body}-{aspect.lower()}")
        orb = asp.get("orb")
        orb_s = f" · orb {float(orb):.2f}°" if orb is not None else ""
        if text:
            rows.append(
                f"<b>{_glyph_body(body)} {_glyph_aspect(aspect)} {_glyph_body(other)}</b>"
                f"{orb_s}\n{_esc(text)}"
            )
        else:
            rows.append(
                f"<b>{_glyph_body(body)} {_glyph_aspect(aspect)} {_glyph_body(other)}</b>"
                f"{orb_s}\n<span color='#d4a72c'>No corpus entry — do not guess.</span>"
            )
    return rows


def _planet_markup(hotspot, ctx: Dict) -> str:
    body = hotspot.data.get("body", "?")
    color = hotspot.data.get("color", "#ffffff")
    parts = [f"<b><span color='{color}'>{_glyph_body(body)}</span></b>"]

    # Status
    bodies = ctx.get("bodies", [])
    b = next((x for x in bodies if x.get("name") == body), None)
    if b is not None:
        sign = b.get("sign_name", "")
        deg = b.get("sign_degree", 0.0)
        house = b.get("house")
        retro = " (R)" if b.get("retrograde") else ""
        speed = b.get("speed")
        status = f"{_glyph_sign(sign)} {format_degree(deg)}{retro}"
        if house:
            status += f" · House {house}"
        if speed is not None:
            status += f" · {float(speed):.3f}°/day"
        parts.append(f"<span color='#cccccc'>{status}</span>")

    # Aspects
    aspects = ctx.get("aspects", [])
    domain = ctx.get("aspect_domain", "aspect")
    a_key = ctx.get("a_key", "body_a")
    b_key = ctx.get("b_key", "body_b")
    rows = _aspect_rows_for_body(ctx.get("cookbook", {}), domain, body,
                                 aspects, a_key, b_key)
    if rows:
        parts.append("<b>Aspects</b>")
        parts.extend(rows)

    # Sign + house cookbook
    cb = ctx.get("cookbook", {})
    if b is not None:
        sign = b.get("sign_name", "")
        if sign:
            t = _cookbook_text(cb, ctx.get("sign_domain", "natal-sign"),
                               f"{body}-{sign}")
            if t:
                parts.append(f"<b>{_glyph_body(body)} in {_glyph_sign(sign)}</b>\n{_esc(t)}")
        house = b.get("house")
        if house:
            t = _cookbook_text(cb, ctx.get("house_domain", "natal-house"),
                               f"{body}-{house}")
            if t:
                parts.append(f"<b>{_glyph_body(body)} in house {house}</b>\n{_esc(t)}")

    return "\n\n".join(parts)


def _aspect_markup(hotspot, ctx: Dict) -> str:
    a = hotspot.data.get("body_a", "?")
    b = hotspot.data.get("body_b", "?")
    aspect = hotspot.data.get("aspect", "?")
    orb = hotspot.data.get("orb")
    applying = hotspot.data.get("applying")

    parts = [f"<b>{_glyph_body(a)} {_glyph_aspect(aspect)} {_glyph_body(b)}</b>"]
    meta = []
    if orb is not None:
        meta.append(f"orb {float(orb):.2f}°")
    if applying is not None:
        meta.append("applying" if applying else "separating")
    if meta:
        parts.append(f"<span color='#cccccc'>{' · '.join(meta)}</span>")

    domain = ctx.get("aspect_domain", "aspect")
    text = _cookbook_text(ctx.get("cookbook", {}), domain, f"{a}-{str(aspect).lower()}")
    if text:
        parts.append(_esc(text))
    else:
        parts.append("<span color='#d4a72c'>No corpus entry — do not guess.</span>")
    return "\n\n".join(parts)


def _sign_markup(hotspot, ctx: Dict) -> str:
    sign = hotspot.data.get("sign", "?")
    parts = [f"<b>{_glyph_sign(sign)}</b>"]

    bodies = ctx.get("bodies", [])
    in_sign = [b for b in bodies if b.get("sign_name") == sign]
    if in_sign:
        parts.append("<b>Bodies in this sign</b>")
        for b in in_sign:
            name = b.get("name", "?")
            deg = b.get("sign_degree", 0.0)
            parts.append(f"{_glyph_body(name)} {format_degree(deg)}")

    cb = ctx.get("cookbook", {})
    for b in in_sign:
        name = b.get("name", "?")
        t = _cookbook_text(cb, ctx.get("sign_domain", "natal-sign"), f"{name}-{sign}")
        if t:
            parts.append(f"<b>{_glyph_body(name)} in {_glyph_sign(sign)}</b>\n{_esc(t)}")
    return "\n\n".join(parts)


def _house_markup(hotspot, ctx: Dict) -> str:
    house = hotspot.data.get("house", "?")
    parts = [f"<b>House {house}</b>"]

    bodies = ctx.get("bodies", [])
    in_house = [b for b in bodies if b.get("house") == house]
    if in_house:
        parts.append("<b>Bodies in this house</b>")
        for b in in_house:
            name = b.get("name", "?")
            sign = b.get("sign_name", "")
            deg = b.get("sign_degree", 0.0)
            parts.append(f"{_glyph_body(name)} {_glyph_sign(sign)} {format_degree(deg)}")

    cb = ctx.get("cookbook", {})
    for b in in_house:
        name = b.get("name", "?")
        t = _cookbook_text(cb, ctx.get("house_domain", "natal-house"), f"{name}-{house}")
        if t:
            parts.append(f"<b>{_glyph_body(name)} in house {house}</b>\n{_esc(t)}")
    return "\n\n".join(parts)


def _angle_markup(hotspot, ctx: Dict) -> str:
    label = hotspot.data.get("angle", "?")
    lon = hotspot.data.get("longitude", 0.0)
    sign_idx = int(float(lon) // 30.0) % 12
    from astro_display.svg.wheel import SIGN_NAMES
    sign = SIGN_NAMES[sign_idx]
    deg = float(lon) % 30.0
    return (
        f"<b>{label}</b>\n"
        f"<span color='#cccccc'>{_glyph_sign(sign)} {format_degree(deg)} "
        f"({float(lon):.2f}° longitude)</span>"
    )


def render_target_markup(hotspot, ctx: Dict) -> str:
    """Render the hover panel markup for a hotspot."""
    if hotspot.kind == "planet":
        return _planet_markup(hotspot, ctx)
    if hotspot.kind == "aspect":
        return _aspect_markup(hotspot, ctx)
    if hotspot.kind == "sign":
        return _sign_markup(hotspot, ctx)
    if hotspot.kind == "house":
        return _house_markup(hotspot, ctx)
    if hotspot.kind == "angle":
        return _angle_markup(hotspot, ctx)
    return f"<b>{_esc(hotspot.label)}</b>"


# ---------------------------------------------------------------------------
# Cookbook index builders (reuse the cookbook package)
# ---------------------------------------------------------------------------

def build_cookbook_index(snapshot, cookbook: Dict) -> Dict:
    """Flatten a cookbook dict into {(domain, key): text} for fast lookups.

    Works for natal / transit / synastry cookbooks (the entry shapes
    differ, so each section is indexed with its own domain).
    """
    index: Dict = {}

    def _add(domain, key, text):
        if text:
            index[(domain, key)] = text

    for e in cookbook.get("natal_signs", []):
        _add("natal-sign", f"{e['body']}-{e['sign']}", e["text"])
    for e in cookbook.get("natal_houses", []):
        _add("natal-house", f"{e['body']}-{e['house']}", e["text"])
    for e in cookbook.get("natal_aspects", []):
        _add("aspect", f"{e['body_a']}-{e['aspect']}", e["text"])

    for e in cookbook.get("transit_signs", []):
        _add("transit-sign", f"{e['body']}-{e['sign']}", e["text"])
    for e in cookbook.get("transit_houses", []):
        _add("transit-house", f"{e['body']}-{e['house']}", e["text"])
    for e in cookbook.get("transit_aspects", []):
        _add("transit-aspect", f"{e['transit_body']}-{e['aspect']}", e["text"])

    for e in cookbook.get("synastry_houses", []):
        _add("synastry-house", f"{e['body']}-{e['house']}", e["text"])
    for e in cookbook.get("synastry_aspects", []):
        _add("synastry-aspect", f"{e['body_a']}-{e['aspect']}", e["text"])

    return index
