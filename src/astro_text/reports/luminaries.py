"""
Luminaries report text builder for astrology-tool.
"""
from astro_text.luminaries import moon_phase
from astro_text.symbols import symbol_for_body
from astro_text.format import format_longitude


def build_luminaries_report(sun: dict, moon: dict) -> str:
    """
    Build a human-readable luminaries report from Sun and Moon data.

    Args:
        sun: Dict with 'longitude' and 'name' (optional).
        moon: Dict with 'longitude' and 'name' (optional).

    Returns:
        Markdown-formatted report string.
    """
    sun_lon = sun.get("longitude", 0.0)
    moon_lon = moon.get("longitude", 0.0)
    phase = moon_phase(sun_lon, moon_lon)

    sun_symbol = symbol_for_body(sun.get("name", "Sun")) or "☉"
    moon_symbol = symbol_for_body(moon.get("name", "Moon")) or "☽"

    lines = [
        "# Luminaries",
        "",
        f"- {sun_symbol} Sun at {format_longitude(sun_lon)}",
        f"- {moon_symbol} Moon at {format_longitude(moon_lon)}",
        "",
        f"Moon phase: {phase['glyph']} {phase['name']} ({phase['percentage']}% illuminated)",
        f"Sun-Moon angle: {phase['angle']}°",
    ]
    return "\n".join(lines)


def build_moon_only_report(moon: dict, sun_lon: float = 0.0) -> str:
    """Build a concise Moon-phase report from Moon data and Sun longitude."""
    moon_lon = moon.get("longitude", 0.0)
    phase = moon_phase(sun_lon, moon_lon)
    moon_symbol = symbol_for_body(moon.get("name", "Moon")) or "☽"
    lines = [
        f"{moon_symbol} Moon at {format_longitude(moon_lon)}",
        f"Phase: {phase['glyph']} {phase['name']} — {phase['percentage']}% illuminated",
    ]
    return "\n".join(lines)
