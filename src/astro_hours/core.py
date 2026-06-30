"""
astro_hours.core — Planetary hour calculations.

Pure Python. Uses `ephem` for accurate sunrise/sunset when available;
falls back to a simple solar-noon approximation otherwise.
"""
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional

try:
    import ephem
except ImportError:  # pragma: no cover
    ephem = None  # type: ignore


PLANET_ORDER = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# Python weekday: Monday=0 ... Sunday=6. Maps to first hour planet of the day.
DAY_RULERS = ["Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun"]

PLANET_QUALITIES = {
    "Saturn": "structure, endings, discipline",
    "Jupiter": "expansion, growth, generosity",
    "Mars": "action, courage, conflict",
    "Sun": "vitality, clarity, self",
    "Venus": "love, beauty, harmony",
    "Mercury": "communication, travel, mind",
    "Moon": "emotion, intuition, cycles",
}

PLANET_PROMPTS = {
    "Saturn": "The gate closes. What ends?",
    "Jupiter": "The gate opens wide. What expands?",
    "Mars": "The gate is forced. What action is needed?",
    "Sun": "The gate is luminous. What is seen?",
    "Venus": "The gate is adorned. What is loved?",
    "Mercury": "The gate speaks. What is communicated?",
    "Moon": "The gate reflects. What is felt?",
}


def _as_date(d) -> date:
    """Normalize date/datetime/string to date."""
    if isinstance(d, str):
        return date.fromisoformat(d)
    if isinstance(d, datetime):
        return d.date()
    return d


def _resolve_tz(tz) -> ZoneInfo:
    """Resolve a timezone string or ZoneInfo, defaulting to UTC."""
    if tz is None:
        return ZoneInfo("UTC")
    if isinstance(tz, str):
        return ZoneInfo(tz)
    return tz


def ephem_to_utc_dt(ephem_date) -> datetime:
    """Convert an ephem.Date to a timezone-aware UTC datetime."""
    if ephem is None:
        raise RuntimeError("ephem is required")
    y, mn, d, h, m, s = ephem.Date(ephem_date).tuple()
    return datetime(int(y), int(mn), int(d), int(h), int(m), int(s), tzinfo=timezone.utc)


def _ephem_sunrise_sunset(target_date: date, lat: float, lon: float, elev: float,
                          tz: ZoneInfo) -> tuple[datetime, datetime, datetime]:
    """Use PyEphem to compute sunrise, sunset, and next sunrise in local time."""
    if ephem is None:
        raise RuntimeError("ephem is required for accurate sunrise/sunset")

    observer = ephem.Observer()
    observer.lat = str(lat)
    observer.lon = str(lon)
    observer.elevation = elev

    noon_utc = datetime(target_date.year, target_date.month, target_date.day,
                        12, 0, 0, tzinfo=timezone.utc)
    observer.date = ephem.Date(noon_utc)

    sunrise_utc = ephem_to_utc_dt(observer.next_rising(ephem.Sun()))
    sunset_utc = ephem_to_utc_dt(observer.next_setting(ephem.Sun()))

    observer.date = ephem.Date(sunset_utc)
    next_sunrise_utc = ephem_to_utc_dt(observer.next_rising(ephem.Sun()))

    return (
        sunrise_utc.astimezone(tz),
        sunset_utc.astimezone(tz),
        next_sunrise_utc.astimezone(tz),
    )


def _fallback_sunrise_sunset(target_date: date, lat: float, tz: ZoneInfo) -> tuple[datetime, datetime, datetime]:
    """Very rough fallback when ephem is unavailable (not for production use)."""
    day_of_year = target_date.timetuple().tm_yday
    daylight_hours = 8 + 4 * math.cos((day_of_year - 15) * 2 * math.pi / 365)
    solar_noon = datetime(target_date.year, target_date.month, target_date.day,
                          12, 0, 0, tzinfo=tz)
    half_day = timedelta(hours=daylight_hours / 2)
    sunrise = solar_noon - half_day
    sunset = solar_noon + half_day
    next_sunrise = sunrise + timedelta(days=1)
    return sunrise, sunset, next_sunrise


def get_sunrise_sunset(target_date, lat: float, lon: float, elev: float = 0.0,
                       tz=None) -> tuple[datetime, datetime, datetime]:
    """
    Return (sunrise_local, sunset_local, next_sunrise_local) as timezone-aware datetimes.

    Args:
        target_date: date or datetime
        lat: latitude in degrees
        lon: longitude in degrees
        elev: elevation in meters (default 0)
        tz: timezone (ZoneInfo or str). Defaults to UTC if None.
    """
    tz = _resolve_tz(tz)
    d = _as_date(target_date)
    if ephem is not None:
        try:
            return _ephem_sunrise_sunset(d, lat, lon, elev, tz)
        except Exception:
            return _fallback_sunrise_sunset(d, lat, tz)
    return _fallback_sunrise_sunset(d, lat, tz)


def compute_planetary_hours(target_date, lat: float, lon: float, elev: float = 0.0,
                            tz=None) -> list[dict]:
    """
    Backward-compatible alias for planetary_hours_for_date.
    """
    return planetary_hours_for_date(target_date, lat, lon, elev, tz)


def planetary_hours_for_date(target_date, lat: float, lon: float, elev: float = 0.0,
                             tz=None) -> list[dict]:
    """
    Compute all 24 planetary hours for the given local date.

    Returns a list of dicts with:
        hour_number, period, planet, start_time, end_time,
        quality, prompt, start_dt, end_dt.
    """
    tz = _resolve_tz(tz)
    d = _as_date(target_date)
    sunrise, sunset, next_sunrise = get_sunrise_sunset(d, lat, lon, elev, tz)

    day_length = sunset - sunrise
    night_length = next_sunrise - sunset
    day_hour_len = day_length / 12
    night_hour_len = night_length / 12

    weekday = d.weekday()
    first_planet = DAY_RULERS[weekday]
    first_idx = PLANET_ORDER.index(first_planet)

    hours = []
    for i in range(12):
        planet = PLANET_ORDER[(first_idx + i) % 7]
        start = sunrise + i * day_hour_len
        end = sunrise + (i + 1) * day_hour_len
        hours.append(_make_hour(i + 1, "day", planet, start, end))

    night_first_idx = (first_idx + 12) % 7
    for i in range(12):
        planet = PLANET_ORDER[(night_first_idx + i) % 7]
        start = sunset + i * night_hour_len
        end = sunset + (i + 1) * night_hour_len
        hours.append(_make_hour(i + 1, "night", planet, start, end))

    return hours


def _make_hour(number: int, period: str, planet: str, start: datetime, end: datetime) -> dict:
    return {
        "hour_number": number,
        "period": period,
        "planet": planet,
        "start_time": start.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "start_dt": start,
        "end_dt": end,
        "quality": PLANET_QUALITIES[planet],
        "prompt": PLANET_PROMPTS[planet],
    }


def get_current_hour(hours: list[dict], when: Optional[datetime] = None) -> Optional[dict]:
    """Return the planetary hour containing `when` (default: now in the first hour's timezone)."""
    if not hours:
        return None
    if when is None:
        tz = hours[0]["start_dt"].tzinfo
        when = datetime.now(tz)
    for h in hours:
        if h["start_dt"] <= when < h["end_dt"]:
            return h
    return hours[-1]


def current_planetary_hour(hours: Optional[list[dict]] = None,
                            lat: Optional[float] = None,
                            lon: Optional[float] = None,
                            elev: float = 0.0,
                            tz=None,
                            when: Optional[datetime] = None) -> Optional[dict]:
    """
    Return the planetary hour containing `when`.

    Convenience overloads:
        current_planetary_hour(hours_list)
        current_planetary_hour(lat=..., lon=..., tz=..., when=...)
    """
    tz = _resolve_tz(tz)
    if when is None:
        when = datetime.now(tz)
    if hours is None:
        if lat is None or lon is None:
            raise ValueError("lat and lon are required when hours list is not provided")
        hours = planetary_hours_for_date(when, lat, lon, elev, tz)
    return get_current_hour(hours, when)
