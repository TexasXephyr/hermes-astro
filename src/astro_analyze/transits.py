"""
Transit event finder and period impact analyzer.
Python stdlib only — uses existing ctypes wrapper + datetime.
"""
from datetime import datetime, timedelta

from astro_api.astro_ctypes import (
    ac_date_to_jd,
    ac_calc_chart,
    ac_detect_aspect,
    body_id_from_name,
    orb_preset_from_name,
    AC_ASP_NONE,
)

# ------------------------------------------------------------------
# Defaults

_DEFAULT_POINTS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Mean Node", "Chiron",
]

# ------------------------------------------------------------------
# Helpers

def _parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _jd_for_date(date_str: str) -> float:
    y, m, d = map(int, date_str.split("-"))
    return ac_date_to_jd(y, m, d, 12, 0, 0, 0.0)


def _calc_positions_for_date(date_str: str, body_ids: list, lat: float = 0.0, lon: float = 0.0, house_system: str = "K") -> list:
    jd = _jd_for_date(date_str)
    chart = ac_calc_chart(jd, lat, lon, body_ids, house_system)
    return chart["bodies"]


# ------------------------------------------------------------------
# Public API

def find_transit_events(natal_chart: dict,
                        start_date: str, end_date: str,
                        include_points: list = None,
                        include_aspects: list = None,
                        orb_preset: str = "Modern") -> list:
    """
    Find all transit events for a person over a date range.

    For each day between start_date and end_date:
    - Calculate transiting body positions
    - Check aspects against natal positions
    - Return events where aspects match include_aspects with include_points

    Each event:
    {
        "date": "2026-05-18",
        "transiting_body": "Saturn",
        "natal_body": "Sun",
        "aspect": "conjunction",
        "angle": 0.0,
        "orb": 0.5,
        "applying": true
    }
    """
    natal_bodies = natal_chart.get("bodies", [])
    if not natal_bodies:
        return []

    if include_points is None:
        include_points = _DEFAULT_POINTS
    include_points_lower = {p.lower() for p in include_points}

    if include_aspects is None:
        include_aspects = ["conjunction", "opposition", "square", "trine", "sextile"]
    include_aspects_lower = {a.lower() for a in include_aspects}

    preset = orb_preset_from_name(orb_preset)

    # Pick transiting bodies to calculate
    transiting_names = [p for p in _DEFAULT_POINTS if p.lower() in include_points_lower]
    if not transiting_names:
        return []
    body_ids = [body_id_from_name(p) for p in transiting_names]

    # Extract location from natal_chart if available
    lat = natal_chart.get("latitude", 0.0)
    lon = natal_chart.get("longitude", 0.0)
    hs = natal_chart.get("house_system", "K")

    events = []
    cache = {}

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    current = start
    while current <= end:
        dstr = _date_str(current)
        key = (dstr, lat, lon, hs)
        if key not in cache:
            cache[key] = _calc_positions_for_date(dstr, body_ids, lat, lon, hs)

        transiting_bodies = cache[key]
        for tb in transiting_bodies:
            if tb["name"].lower() not in include_points_lower:
                continue
            for nb in natal_bodies:
                asp = ac_detect_aspect(
                    nb["longitude"], 0.0,   # natal fixed for transit applying logic
                    tb["longitude"], tb["speed"],
                    preset,
                )
                if asp["aspect"] == AC_ASP_NONE:
                    continue
                aname = asp["aspect_name"].lower()
                if aname not in include_aspects_lower:
                    continue
                events.append({
                    "date": dstr,
                    "transiting_body": tb["name"],
                    "natal_body": nb["name"],
                    "aspect": aname,
                    "angle": round(asp["actual_angle"], 4),
                    "orb": round(asp["orb"], 4),
                    "applying": asp["applying"],
                })
        current += timedelta(days=1)

    return events


def period_impact(natal_chart: dict,
                  date: str,
                  orb_days: int = 7,
                  include_points: list = None) -> dict:
    """
    Show all transits in effect on a given date.

    For each transiting body:
    - Calculate position on `date`
    - Check aspects against natal positions
    - Include aspects that are within orb and will be active for `orb_days` around date

    Return:
    {
        "date": "2026-05-18",
        "active_transits": [
            {
                "transiting_body": "Saturn",
                "natal_body": "Sun",
                "aspect": "conjunction",
                "exact_date": "2026-05-20",  # when exact
                "days_to_exact": 2,
                "orb": 0.5,
                "in_effect": true
            }
        ]
    }
    """
    natal_bodies = natal_chart.get("bodies", [])
    if not natal_bodies:
        return {"date": date, "active_transits": []}

    if include_points is None:
        include_points = _DEFAULT_POINTS
    include_points_lower = {p.lower() for p in include_points}

    preset = orb_preset_from_name("Modern")

    transiting_names = [p for p in _DEFAULT_POINTS if p.lower() in include_points_lower]
    if not transiting_names:
        return {"date": date, "active_transits": []}
    body_ids = [body_id_from_name(p) for p in transiting_names]

    lat = natal_chart.get("latitude", 0.0)
    lon = natal_chart.get("longitude", 0.0)
    hs = natal_chart.get("house_system", "K")

    target_dt = _parse_date(date)

    # Pre-calculate all days in the search window to reuse cache
    search_start = target_dt - timedelta(days=orb_days)
    search_end = target_dt + timedelta(days=orb_days)
    window_dates = []
    s = search_start
    while s <= search_end:
        window_dates.append(_date_str(s))
        s += timedelta(days=1)

    # Cache positions for every day in window
    cache = {}
    for dstr in window_dates:
        key = (dstr, lat, lon, hs)
        if key not in cache:
            cache[key] = _calc_positions_for_date(dstr, body_ids, lat, lon, hs)

    target_bodies = cache.get((date, lat, lon, hs))
    if target_bodies is None:
        target_bodies = _calc_positions_for_date(date, body_ids, lat, lon, hs)

    active = []

    for tb in target_bodies:
        if tb["name"].lower() not in include_points_lower:
            continue
        for nb in natal_bodies:
            asp = ac_detect_aspect(
                nb["longitude"], 0.0,
                tb["longitude"], tb["speed"],
                preset,
            )
            if asp["aspect"] == AC_ASP_NONE:
                continue

            aspect_type = asp["aspect"]
            best_orb = asp["orb"]
            exact_date_str = date

            # Search window for minimum orb of the same aspect type
            for dstr in window_dates:
                if dstr == date:
                    continue
                bodies = cache[(dstr, lat, lon, hs)]
                tbi = next((b for b in bodies if b["name"] == tb["name"]), None)
                if tbi is None:
                    continue
                a2 = ac_detect_aspect(
                    nb["longitude"], 0.0,
                    tbi["longitude"], tbi["speed"],
                    preset,
                )
                if a2["aspect"] == aspect_type and a2["orb"] < best_orb:
                    best_orb = a2["orb"]
                    exact_date_str = dstr

            days_to_exact = (_parse_date(exact_date_str) - target_dt).days

            active.append({
                "transiting_body": tb["name"],
                "natal_body": nb["name"],
                "aspect": asp["aspect_name"].lower(),
                "exact_date": exact_date_str,
                "days_to_exact": days_to_exact,
                "orb": round(asp["orb"], 4),
                "in_effect": True,
            })

    return {
        "date": date,
        "active_transits": active,
    }
