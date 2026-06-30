"""
Aspect helpers for astrology-tool.

Functions for finding, filtering, and formatting aspects using the
YAML-backed aspect corpus.
"""
import math

from astro_data.loaders import yaml_loader
from astro_text.symbols import symbol_for_aspect, symbol_for_body


def _load_aspects() -> dict:
    return yaml_loader("aspects")


def _shortest_angle(a: float, b: float) -> float:
    """Return the smallest angular distance between two longitudes."""
    diff = abs((a - b) % 360.0)
    return min(diff, 360.0 - diff)


def find_aspect(angle: float) -> dict | None:
    """
    Find the closest matching aspect for a given angle in degrees.

    Returns:
        A dict describing the nearest aspect, or None if no aspect matches
        within its default orb.
    """
    aspects = _load_aspects()
    best = None
    best_orb = 999.0

    for name, data in aspects.items():
        target = float(data.get("angle", 0))
        orb = float(data.get("default_orb", 0))
        delta = abs((angle - target + 180) % 360 - 180)
        if delta <= orb and delta < best_orb:
            best_orb = delta
            best = {
                "name": name,
                "glyph": data.get("glyph", ""),
                "angle": target,
                "quality": data.get("quality", ""),
                "major": bool(data.get("major", False)),
                "orb": round(delta, 2),
            }

    return best


def filter_major(aspects: list[dict]) -> list[dict]:
    """Filter a list of aspect dicts to only major aspects."""
    return [asp for asp in aspects if asp.get("major", False)]


def format_aspect(body_a: str, body_b: str, aspect: dict) -> str:
    """
    Format a human-readable aspect string.

    Args:
        body_a: Name of the first body.
        body_b: Name of the second body.
        aspect: Dict with keys: name, glyph (optional), orb (optional), quality (optional).
    """
    glyph = aspect.get("glyph") or symbol_for_aspect(aspect.get("name", ""))
    orb = aspect.get("orb")
    quality = aspect.get("quality")
    ba = symbol_for_body(body_a) or body_a
    bb = symbol_for_body(body_b) or body_b
    parts = [f"{ba} {glyph} {bb}"]
    if orb is not None:
        parts.append(f"orb {orb:.2f}°")
    if quality:
        parts.append(f"({quality})")
    return " ".join(parts)
