"""
House helper functions for astrology-tool.
"""
import math


def find_house(longitude: float, houses: list[dict]) -> int:
    """
    Determine which house a longitude falls into given a list of cusps.

    Args:
        longitude: Ecliptic longitude in degrees (0-360, normalized automatically).
        houses: List of dicts with at least 'house_num' and 'longitude' keys,
                ordered by ascending cusp longitude.

    Returns:
        The house number containing the longitude.

    Raises:
        ValueError: If houses is empty or malformed.
    """
    if not houses:
        raise ValueError("houses list cannot be empty")

    # Normalize to [0, 360)
    lon = longitude % 360.0
    if lon < 0:
        lon += 360.0

    # Pair and sort cusps by longitude, preserving house_num
    cusps = sorted(
        ((float(h.get("longitude", 0.0)) % 360.0, h.get("house_num", i + 1)) for i, h in enumerate(houses)),
        key=lambda x: x[0],
    )
    n = len(cusps)

    # Determine the active house: the one whose cusp is the largest
    # cusp value still <= lon, wrapping past the last cusp back to first.
    for i in range(n - 1, -1, -1):
        cusp_lon, house_num = cusps[i]
        if lon >= cusp_lon:
            return house_num

    # lon is before the first cusp: it belongs to the last house (wrap-around).
    return cusps[-1][1]


def day_of_sign(degree: float) -> int:
    """Return the day (1-30) within a sign for a given sign degree."""
    deg = max(0.0, min(degree, 29.999999))
    return int(math.floor(deg)) + 1


def day_of_house(degree_in_house: float, cusp_longitude: float = 0.0, house_span: float = 30.0) -> int:
    """
    Return the day (1-N) within a house for a given offset.

    Args:
        degree_in_house: Degrees from the cusp of the house.
        cusp_longitude: Optional cusp longitude for normalization.
        house_span: Total size of the house in degrees (defaults to 30).
    """
    if house_span <= 0:
        raise ValueError("house_span must be positive")
    offset = (degree_in_house - cusp_longitude) % house_span
    return int(math.floor(offset)) + 1
