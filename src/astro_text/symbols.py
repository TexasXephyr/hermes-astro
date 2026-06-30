"""
Symbol lookup tables for astrology-tool.

All lookups are backed by astro_data.loaders so the central YAML corpus
remains the single source of truth for glyphs and names.
"""
from astro_data.loaders import yaml_loader


def _load_bodies() -> dict:
    return yaml_loader("bodies")


def _load_signs() -> dict:
    return yaml_loader("signs")


def _load_aspects() -> dict:
    return yaml_loader("aspects")


def _retrograde_symbol() -> str:
    """Internal retrograde glyph; isolated for testing/overrides."""
    return "℞"


def symbol_for_body(name: str) -> str | None:
    """Return the glyph for a canonical body name, or None if unknown."""
    bodies = _load_bodies()
    body = bodies.get(name)
    return body.get("glyph") if body else None


def body_for_symbol(glyph: str) -> str | None:
    """Return the canonical body name for a glyph, or None if unknown."""
    bodies = _load_bodies()
    for name, data in bodies.items():
        if data.get("glyph") == glyph:
            return name
    return None


def symbol_for_sign(name: str) -> str:
    """Return the glyph for a canonical sign name."""
    signs = _load_signs()
    if name not in signs:
        raise KeyError(f"Unknown sign '{name}'")
    return signs[name]["glyph"]


def sign_for_symbol(glyph: str) -> str | None:
    """Return the canonical sign name for a glyph, or None if unknown."""
    signs = _load_signs()
    for name, data in signs.items():
        if data.get("glyph") == glyph:
            return name
    return None


def symbol_for_aspect(name: str) -> str:
    """Return the glyph for a canonical aspect name."""
    aspects = _load_aspects()
    if name not in aspects:
        raise KeyError(f"Unknown aspect '{name}'")
    return aspects[name]["glyph"]


def aspect_for_symbol(glyph: str) -> str | None:
    """Return the canonical aspect name for a glyph, or None if unknown."""
    aspects = _load_aspects()
    for name, data in aspects.items():
        if data.get("glyph") == glyph:
            return name
    return None


def retrograde_symbol() -> str:
    """Return the retrograde glyph."""
    return _retrograde_symbol()
