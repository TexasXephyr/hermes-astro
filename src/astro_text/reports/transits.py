"""
Transit report text builder for astrology-tool.
"""
from astro_text.symbols import symbol_for_body
from astro_text.format import format_longitude, ordinal
from astro_text.aspects import format_aspect


def build_daily_transit_report(chart_data: dict, transit_data: dict) -> str:
    """
    Build a human-readable daily transit report.

    Args:
        chart_data: Natal chart dict with bodies and houses.
        transit_data: Transit chart dict with bodies and aspects.

    Returns:
        Markdown-formatted transit report string.
    """
    lines = ["# Daily Transits", ""]

    # List transiting bodies in signs
    transits = transit_data.get("bodies", [])
    if transits:
        lines.append("## Transiting Bodies")
        for b in transits:
            name = b.get("name", "Unknown")
            glyph = symbol_for_body(name) or name
            lon = format_longitude(b.get("longitude", 0.0))
            house = b.get("house")
            house_str = f"in {ordinal(house)} house" if house else ""
            lines.append(f"- {glyph} {name} at {lon} {house_str}".strip())
        lines.append("")

    # Active aspects to natal
    aspects = transit_data.get("aspects", [])
    if aspects:
        lines.append("## Active Aspects")
        for asp in aspects[:10]:
            lines.append(f"- {format_aspect(asp.get('body_a', ''), asp.get('body_b', ''), asp)}")
        lines.append("")
    else:
        lines.append("No major transits active.\n")

    return "\n".join(lines)


def build_period_impact_summary(active_transits: list[dict]) -> str:
    """
    Build a short text summary of active transit impacts.
    """
    if not active_transits:
        return "No notable transit impacts for this period."

    lines = ["Active transit impacts:"]
    for t in active_transits:
        body_a = t.get("body_a", "?")
        body_b = t.get("body_b", "?")
        aspect = t.get("aspect", {})
        lines.append(f"- {format_aspect(body_a, body_b, aspect)}")
    return "\n".join(lines)
