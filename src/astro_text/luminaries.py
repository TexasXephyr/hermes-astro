"""
Luminary helpers for astrology-tool.
"""
import math

from astro_data.loaders import yaml_loader


def _load_phases() -> dict:
    return yaml_loader("moon_phases")


def moon_phase(sun_lon: float, moon_lon: float) -> dict:
    """
    Return the Moon phase based on Sun-Moon angular separation.

    Args:
        sun_lon: Sun longitude in degrees.
        moon_lon: Moon longitude in degrees.

    Returns:
        Dict with keys: name, glyph, percentage, angle.
    """
    angle = (moon_lon - sun_lon) % 360.0

    # Percentage illuminated: 0=new, 50=quarter, 100=full
    percentage = round((1 - math.cos(math.radians(angle))) / 2 * 100, 1)

    phases = _load_phases()
    for key, phase in phases.items():
        min_a = phase.get("min_angle", 0)
        max_a = phase.get("max_angle", 360)
        if min_a <= angle <= max_a:
            return {
                "name": phase.get("name", key),
                "glyph": phase.get("glyph", ""),
                "percentage": percentage,
                "angle": round(angle, 2),
            }

    # Should always match Balsamic at 360, but keep a fallback
    return {
        "name": "Unknown",
        "glyph": "",
        "percentage": percentage,
        "angle": round(angle, 2),
    }
