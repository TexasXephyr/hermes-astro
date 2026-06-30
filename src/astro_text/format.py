"""
General text formatting utilities for astrology-tool.
"""


def ordinal(n: int) -> str:
    """Return the English ordinal suffix for an integer."""
    if not isinstance(n, int):
        raise TypeError("ordinal expects an int")
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_longitude(longitude: float) -> str:
    """
    Format an ecliptic longitude as 'DD° SS' sign' (e.g. '15° 32 ♈').
    """
    if not isinstance(longitude, (int, float)):
        raise TypeError("format_longitude expects a number")
    lon = float(longitude) % 360.0
    sign_index = int(lon // 30)
    degrees = int(lon % 30)
    minutes = int(round((lon % 1) * 60))
    # Avoid 30 minutes wrapping incorrectly
    if minutes >= 60:
        minutes -= 60
        degrees += 1
    if degrees >= 30:
        degrees -= 30
        sign_index = (sign_index + 1) % 12

    from astro_data.loaders import yaml_loader

    signs = yaml_loader("signs")
    sign_names = list(signs.keys())
    sign = sign_names[sign_index]
    glyph = signs[sign]["glyph"]
    return f"{degrees}° {minutes:02d} {glyph}"


def format_degree(degree: float) -> str:
    """Format a degree value as 'DD° MM''."""
    if not isinstance(degree, (int, float)):
        raise TypeError("format_degree expects a number")
    deg = int(degree)
    minutes = int(round((degree - deg) * 60))
    if minutes >= 60:
        minutes -= 60
        deg += 1
    return f"{deg}° {minutes:02d}'"
