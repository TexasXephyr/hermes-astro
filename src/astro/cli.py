"""astro.cli — command-line interface for the astrology-tool suite.

Commands:
    natal, transit, synastry, period-impact,
    luminaries, planetary-hours, wheel, table

Exit codes:
    0 success
    1 validation/runtime error
    2 argparse usage error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import available_timezones

from astro_api_client import AstroClient
from astro_data.bodies import ALL_POINTS
from astro_display import WheelRenderer
from astro_hours.core import planetary_hours_for_date
from astro_text.format import format_longitude
from astro_text.luminaries import moon_phase

DEFAULT_TIME = "12:00:00"

# ---------------------------------------------------------------------------
# Validation / parsing helpers
# ---------------------------------------------------------------------------


def _validate_lat_lon(lat: float | None, lon: float | None) -> None:
    """Ensure latitude/longitude are within valid ranges."""
    if lat is None or lon is None:
        raise ValueError("latitude and longitude are required")
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"latitude must be in [-90, 90], got {lat}")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"longitude must be in [-180, 180], got {lon}")


def _validate_timezone(tz: str | None) -> None:
    """Ensure timezone is a valid IANA name."""
    if tz is None:
        raise ValueError("timezone is required")
    if tz not in available_timezones():
        raise ValueError(f"invalid timezone: {tz}")


def _parse_datetime(date_str: str, time_str: str) -> datetime:
    """Strictly validate date (YYYY-MM-DD) and time (HH:MM:SS)."""
    if not date_str or not time_str:
        raise ValueError("date and time are required")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        raise ValueError(f"invalid date format (expected YYYY-MM-DD): {date_str}")
    if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", time_str):
        raise ValueError(f"invalid time format (expected HH:MM:SS): {time_str}")
    try:
        dt = datetime.fromisoformat(f"{date_str}T{time_str}")
    except ValueError as exc:
        raise ValueError(f"invalid date/time: {exc}") from exc
    if dt.strftime("%Y-%m-%d") != date_str:
        raise ValueError(f"date not in strict YYYY-MM-DD format: {date_str}")
    if dt.strftime("%H:%M:%S") != time_str:
        raise ValueError(f"time not in strict HH:MM:SS format: {time_str}")
    return dt


def _validate_output_path(path_str: str | None) -> Path | None:
    """Validate a destination path and return its resolved path."""
    if not path_str:
        return None
    p = Path(path_str)
    if ".." in p.parts:
        raise ValueError(f"output path must not contain '..' components: {path_str}")

    resolved = p.resolve()

    if p.is_absolute():
        parent = resolved.parent
        if not parent.exists():
            raise ValueError(f"output parent directory does not exist: {parent}")
        if not os.access(parent, os.W_OK):
            raise ValueError(f"output parent directory is not writable: {parent}")
        return resolved

    cwd = Path.cwd().resolve()
    try:
        resolved.relative_to(cwd)
    except ValueError as exc:
        raise ValueError(f"relative output path must not escape cwd: {path_str}") from exc

    parent = resolved.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    if not os.access(parent, os.W_OK):
        raise ValueError(f"output parent directory is not writable: {parent}")
    return resolved


def _points_from_arg(value: str | None) -> list[str] | None:
    """Parse a comma-separated --points list; empty/None returns defaults."""
    if value is None or str(value).strip() == "":
        return None
    points = [p.strip() for p in str(value).split(",") if p.strip()]
    return points or None


def _write_output(text: str, output_path: Path | None) -> None:
    """Write text to stdout or to a validated file path."""
    if output_path is None:
        print(text)
        return
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _load_chart(client: AstroClient, args: argparse.Namespace) -> dict:
    """Load an existing chart or compute a natal chart from birth args."""
    if getattr(args, "chart_id", None):
        return client.get_chart(args.chart_id)

    name = getattr(args, "name", None) or "Unknown"
    date = getattr(args, "date", None)
    time = getattr(args, "time", None) or DEFAULT_TIME
    tz = getattr(args, "timezone", None)
    lat = getattr(args, "latitude", None)
    lon = getattr(args, "longitude", None)

    if not date:
        raise ValueError("--date is required when --chart-id is not provided")
    _parse_datetime(date, time)
    _validate_lat_lon(lat, lon)
    _validate_timezone(tz)
    assert lat is not None and lon is not None and tz is not None

    points = _points_from_arg(getattr(args, "points", None))
    house_system = getattr(args, "house_system", "K")
    orb_preset = getattr(args, "orb_preset", "Modern")

    return client.natal(
        name=name,
        date=date,
        time=time,
        timezone=tz,
        latitude=lat,
        longitude=lon,
        points=points,
        house_system=house_system,
        orb_preset=orb_preset,
    )


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _format_table(chart: dict) -> str:
    """Render a plain-text table of bodies, houses, and aspects."""
    lines: list[str] = []
    lines.append("Chart Table")
    lines.append("=" * 66)
    lines.append(f"{'Body':<15}{'Longitude':<20}{'Sign':<12}{'House':<8}{'Retro':<6}")

    bodies = sorted(chart.get("bodies", []), key=lambda b: b.get("longitude", 0.0))
    for b in bodies:
        name = b.get("name", "?")
        lon = b.get("longitude", 0.0)
        sign = b.get("sign_name") or f"Sign {b.get('sign', 0)}"
        house = b.get("house", "-")
        retro = "R" if b.get("retrograde") else ""
        lines.append(
            f"{name:<15}{format_longitude(lon):<20}{sign:<12}{str(house):<8}{retro:<6}"
        )

    lines.append("")
    lines.append("Houses")
    lines.append("-" * 40)
    for h in sorted(chart.get("houses", []), key=lambda h: h.get("house_num", 0)):
        num = h.get("house_num", 0)
        lon = h.get("longitude", 0.0)
        lines.append(f"House {num:<3}: {format_longitude(lon)}")

    lines.append("")
    lines.append("Aspects")
    lines.append("-" * 40)
    for a in chart.get("aspects", []):
        a_name = a.get("aspect_name") or a.get("aspect", "?")
        lines.append(
            f"{a.get('body_a')} {a_name} {a.get('body_b')} "
            f"(orb {a.get('orb', 0.0):.2f}°)"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _cmd_natal(client: AstroClient, args: argparse.Namespace) -> None:
    _parse_datetime(args.date, args.time)
    _validate_lat_lon(args.latitude, args.longitude)
    _validate_timezone(args.timezone)
    points = _points_from_arg(args.points)
    chart = client.natal(
        name=args.name or "Unknown",
        date=args.date,
        time=args.time,
        timezone=args.timezone,
        latitude=args.latitude,
        longitude=args.longitude,
        points=points,
        house_system=args.house_system,
        orb_preset=args.orb_preset,
    )
    _write_output(json.dumps(chart, indent=2), _validate_output_path(args.output))


def _cmd_transit(client: AstroClient, args: argparse.Namespace) -> None:
    chart_id = args.chart_id
    if not chart_id:
        natal = _load_chart(client, args)
        chart_id = natal["chart_id"]
    if not args.date:
        raise ValueError("--date is required for transit")
    _parse_datetime(args.date, args.time)
    data = client.transit(chart_id, args.date, args.time)
    _write_output(json.dumps(data, indent=2), _validate_output_path(args.output))


def _cmd_synastry(client: AstroClient, args: argparse.Namespace) -> None:
    data = client.synastry(args.chart_id_a, args.chart_id_b)
    _write_output(json.dumps(data, indent=2), _validate_output_path(args.output))


def _cmd_period_impact(client: AstroClient, args: argparse.Namespace) -> None:
    chart_id = args.chart_id
    if not chart_id:
        natal = _load_chart(client, args)
        chart_id = natal["chart_id"]
    if not args.date:
        raise ValueError("--date is required for period-impact")
    data = client.period_impact(chart_id, args.date, orb_days=args.orb_days)
    _write_output(json.dumps(data, indent=2), _validate_output_path(args.output))


def _cmd_luminaries(client: AstroClient, args: argparse.Namespace) -> None:
    if args.chart_id:
        chart = client.get_chart(args.chart_id)
        sun = next((b for b in chart["bodies"] if b["name"] == "Sun"), None)
        moon = next((b for b in chart["bodies"] if b["name"] == "Moon"), None)
        if sun is None or moon is None:
            raise ValueError("chart does not contain Sun and Moon")
        meta = chart.get("meta", {})
        date = meta.get("birth_date", args.date)
        time = meta.get("birth_time", args.time or DEFAULT_TIME)
        tz = meta.get("timezone", args.timezone)
        lat = meta.get("latitude", args.latitude)
        lon = meta.get("longitude", args.longitude)
    else:
        date = args.date
        time = args.time or DEFAULT_TIME
        tz = args.timezone
        lat = args.latitude
        lon = args.longitude
        if not date:
            raise ValueError("--date is required when --chart-id is not provided")
        _parse_datetime(date, time)
        _validate_lat_lon(lat, lon)
        _validate_timezone(tz)
        chart = client.natal(
            "Luminaries", date, time, tz, lat, lon, points=["Sun", "Moon"]
        )
        sun = next((b for b in chart["bodies"] if b["name"] == "Sun"), None)
        moon = next((b for b in chart["bodies"] if b["name"] == "Moon"), None)
        if sun is None or moon is None:
            raise ValueError("could not compute Sun and Moon")

    phase = moon_phase(sun["longitude"], moon["longitude"])
    data = {
        "status": "ok",
        "date": date,
        "time": time,
        "timezone": tz,
        "latitude": lat,
        "longitude": lon,
        "sun": sun,
        "moon": moon,
        "moon_phase": phase,
    }
    _write_output(json.dumps(data, indent=2), _validate_output_path(args.output))


def _cmd_planetary_hours(client: AstroClient, args: argparse.Namespace) -> None:
    if not args.date:
        raise ValueError("--date is required for planetary-hours")
    lat = args.latitude if args.latitude is not None else 44.0521
    lon = args.longitude if args.longitude is not None else -123.0868
    tz = args.timezone or "America/Los_Angeles"
    elev = getattr(args, "elevation", 130.0)
    _validate_lat_lon(lat, lon)
    _validate_timezone(tz)
    hours = planetary_hours_for_date(args.date, lat, lon, elev=elev, tz=tz)
    for h in hours:
        h["start_dt"] = h["start_dt"].isoformat()
        h["end_dt"] = h["end_dt"].isoformat()
    _write_output(json.dumps(hours, indent=2), _validate_output_path(args.output))


def _cmd_wheel(client: AstroClient, args: argparse.Namespace) -> None:
    chart = _load_chart(client, args)
    svg = WheelRenderer().render_natal(chart)
    _write_output(svg, _validate_output_path(args.output))


def _cmd_table(client: AstroClient, args: argparse.Namespace) -> None:
    chart = _load_chart(client, args)
    _write_output(_format_table(chart), _validate_output_path(args.output))


def _cmd_bodies(client: AstroClient, args: argparse.Namespace) -> None:
    _write_output(json.dumps(ALL_POINTS, indent=2), _validate_output_path(args.output))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astro",
        description="Astrology-tool command-line interface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Common birth / output options reused by several commands.
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--date", "-d", default=None, help="YYYY-MM-DD")
    shared.add_argument("--time", "-t", default=DEFAULT_TIME, help="HH:MM:SS")
    shared.add_argument("--timezone", "--tz", "-z", default=None, help="IANA timezone")
    shared.add_argument("--latitude", "--lat", type=float, default=None)
    shared.add_argument("--longitude", "--lon", type=float, default=None)
    shared.add_argument("--name", "-n", default=None)
    shared.add_argument("--points", "-p", default=None, help="comma-separated body names")
    shared.add_argument("--house-system", default="K", help="house system code (default K)")
    shared.add_argument("--orb-preset", default="Modern", help="orb preset (default Modern)")
    shared.add_argument("--output", "-o", default=None, help="output file path")
    shared.add_argument("--json", action="store_true", help="output JSON (default for most commands)")

    # natal
    natal_p = subparsers.add_parser("natal", parents=[shared], help="calculate a natal chart")
    natal_p.set_defaults(func=_cmd_natal)

    # transit
    transit_p = subparsers.add_parser("transit", parents=[shared], help="calculate a transit chart")
    transit_p.add_argument("--chart-id", default=None, help="existing natal chart id")
    transit_p.set_defaults(func=_cmd_transit)

    # synastry
    syn_p = subparsers.add_parser("synastry", parents=[shared], help="cross-aspects between two charts")
    syn_p.add_argument("--chart-id-a", "--person-a", required=True, help="first chart id")
    syn_p.add_argument("--chart-id-b", "--person-b", required=True, help="second chart id")
    syn_p.set_defaults(func=_cmd_synastry)

    # period-impact
    period_p = subparsers.add_parser("period-impact", parents=[shared], help="transit impact for a date")
    period_p.add_argument("--chart-id", default=None, help="existing natal chart id")
    period_p.add_argument("--orb-days", type=int, default=7, help="search window in days")
    period_p.set_defaults(func=_cmd_period_impact)

    # luminaries
    lum_p = subparsers.add_parser("luminaries", parents=[shared], help="Sun/Moon positions and Moon phase")
    lum_p.add_argument("--chart-id", default=None, help="existing chart id")
    lum_p.set_defaults(func=_cmd_luminaries)

    # planetary-hours
    hours_p = subparsers.add_parser(
        "planetary-hours", parents=[shared], help="planetary hours for a date/location"
    )
    hours_p.add_argument("--elevation", type=float, default=130.0, help="elevation in meters")
    hours_p.set_defaults(latitude=44.0521, longitude=-123.0868, timezone="America/Los_Angeles")
    hours_p.set_defaults(func=_cmd_planetary_hours)

    # wheel
    wheel_p = subparsers.add_parser("wheel", parents=[shared], help="render an SVG wheel")
    wheel_p.add_argument("--chart-id", default=None, help="existing chart id")
    wheel_p.set_defaults(func=_cmd_wheel)

    # table
    table_p = subparsers.add_parser("table", parents=[shared], help="print a text table for a chart")
    table_p.add_argument("--chart-id", default=None, help="existing chart id")
    table_p.set_defaults(func=_cmd_table)

    # bodies
    bodies_p = subparsers.add_parser("bodies", help="list available celestial bodies")
    bodies_p.add_argument("--output", "-o", default=None)
    bodies_p.add_argument("--json", action="store_true")
    bodies_p.set_defaults(func=_cmd_bodies)

    return parser


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 2

    try:
        client = AstroClient()
        args.func(client, args)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
