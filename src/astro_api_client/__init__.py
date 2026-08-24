#!/usr/bin/env python3
"""
astro_api_client — Library-first astrology client facade.

Provides AstroClient class that computes natal/transit/period-impact
using the local astro_* packages by default, with optional HTTP backend.

Usage:
    from astro_api_client import AstroClient
    
    # Library backend (default, no server needed)
    client = AstroClient()
    result = client.natal("Test", "2000-01-01", "12:00:00", "UTC", 0.0, 0.0)
    
    # HTTP backend (opt-in)
    client = AstroClient(backend="http", base_url="http://localhost:8081")
    # or set ASTRO_API_URL env var
"""
import os
import re
import uuid
import json
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

from astro_calc import (
    ac_init,
    ac_date_to_jd,
    ac_calc_chart,
    ac_detect_aspect,
    calculate_aspects,
    body_id_from_name,
    orb_preset_from_name,
    AC_ASP_NONE,
)
from astro_data.bodies import BodySet, DEFAULT_POINTS, ALL_POINTS
from astro_analyze.transits import period_impact as _analyze_period_impact


API_BASE = os.environ.get("ASTRO_API_URL", "http://localhost:8081")

ASPECTS = {
    -1: "None",
    0: "Conjunction",
    1: "Semisextile",
    2: "Semisquare",
    3: "Sextile",
    4: "Square",
    5: "Trine",
    6: "Sesquiquadrate",
    7: "Quincunx",
    8: "Opposition",
}

HOUSES = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "i", "q",
]

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ------------------------------------------------------------------
# Library helpers

_ephe_initialized = False

def _ensure_ephe():
    """Initialize Swiss Ephemeris once per process."""
    global _ephe_initialized
    if not _ephe_initialized:
        ac_init()
        _ephe_initialized = True


def _parse_datetime(date: str, time: str, tz_name: str) -> tuple[float, datetime]:
    """Return (jd_ut, naive_dt)."""
    if tz_name not in available_timezones():
        raise ValueError(f"Unknown timezone: {tz_name}")
    dt_naive = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")
    tz = ZoneInfo(tz_name)
    dt = dt_naive.replace(tzinfo=tz)
    offset = dt.utcoffset().total_seconds() / 3600.0
    jd = ac_date_to_jd(dt_naive.year, dt_naive.month, dt_naive.day,
                       dt_naive.hour, dt_naive.minute, dt_naive.second, offset)
    return jd, dt_naive


def _jd_for_date(date_str: str) -> float:
    y, m, d = map(int, date_str.split("-"))
    return ac_date_to_jd(y, m, d, 12, 0, 0, 0.0)


def _validate_lat_lon(lat: float, lon: float) -> None:
    if lat is None or lon is None:
        raise ValueError("latitude and longitude are required")
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"latitude must be in [-90, 90], got {lat}")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"longitude must be in [-180, 180], got {lon}")


def _validate_uuid(chart_id: str) -> None:
    if chart_id is None or not _UUID_RE.match(str(chart_id)):
        raise ValueError(f"Invalid chart_id UUID: {chart_id}")


def _points_to_ids(points: list[str]) -> list[int]:
    """Validate points against BodySet and return C body IDs (South Node excluded)."""
    bs = BodySet(points)
    return [
        body_id_from_name(name)
        for name in bs.to_list()
        if name.lower() != "south node"
    ]


def _find_body(bodies: list[dict], name: str) -> dict | None:
    """Find a body in a list by canonical name (case-insensitive)."""
    low = name.lower()
    for b in bodies:
        if b.get("name", "").lower() == low:
            return b
    return None


def _derive_south_node(north_body: dict) -> dict:
    """Derive South Node from a North/M/True Node result (opposite longitude)."""
    lon = (north_body["longitude"] + 180.0) % 360.0
    sign = int(lon // 30.0)
    sign_degree = lon - sign * 30.0
    return {
        "body_id": None,
        "name": "South Node",
        "longitude": round(lon, 6),
        "latitude": round(north_body.get("latitude", 0.0), 6),
        "distance": 0.0,
        "speed": round(-north_body.get("speed", 0.0), 6),
        "retrograde": not north_body.get("retrograde", False),
        "sign": sign,
        "sign_name": "",  # caller can fill if needed; keep dict thin
        "sign_degree": round(sign_degree, 6),
        "house": north_body.get("house"),
    }


def _insert_south_node(bodies: list[dict]) -> list[dict]:
    """Derive South Node from Mean/True Node and insert after the node pair."""
    if _find_body(bodies, "South Node") is not None:
        return bodies
    # Prefer Mean Node, fallback to True Node per spec (opposite_of: Mean Node).
    source = _find_body(bodies, "Mean Node") or _find_body(bodies, "True Node")
    if source is None:
        return bodies
    south = _derive_south_node(source)
    result = []
    inserted = False
    for b in bodies:
        result.append(b)
        if not inserted and b.get("name") in ("Mean Node", "True Node"):
            result.append(south)
            inserted = True
    return result if inserted else bodies + [south]


# ------------------------------------------------------------------
# HTTP backend

def _api_req(method: str, path: str, base_url: str, data=None):
    """Make an HTTP request to the optional API backend."""
    url = f"{base_url}{path}"
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(data).encode("utf-8") if data else None,
    )
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err = json.loads(body)
        except Exception:
            err = {"message": body}
        return {"status": "error", "code": e.code, "message": err.get("message", body)}
    except urllib.error.URLError as e:
        return {"status": "error", "message": f"Cannot connect to {base_url}: {e.reason}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_chart(chart_id: str, base_url: str = API_BASE):
    return _api_req("GET", f"/v1/charts/{chart_id}", base_url)


def create_person(name: str, birth_date: str, birth_time: str, timezone: str,
                  latitude: float, longitude: float, base_url: str = API_BASE, **extra):
    payload = {
        "name": name,
        "birth_date": birth_date,
        "birth_time": birth_time,
        "timezone": timezone,
        "latitude": latitude,
        "longitude": longitude,
    }
    payload.update(extra)
    return _api_req("POST", "/v1/people", base_url, payload)


def list_people(base_url: str = API_BASE):
    return _api_req("GET", "/v1/people", base_url)


def get_person(person_id: int, base_url: str = API_BASE):
    return _api_req("GET", f"/v1/people/{person_id}", base_url)


def make_natal(name: str, date: str, time: str, timezone: str, latitude: float, longitude: float,
               points=None, house_system="K", orb_preset="Modern", base_url: str = API_BASE):
    payload = {
        "person": {
            "name": name,
            "birth_date": date,
            "birth_time": time,
            "timezone": timezone,
            "latitude": latitude,
            "longitude": longitude,
        },
        "options": {
            "house_system": house_system,
            "points": points or list(DEFAULT_POINTS),
            "orb_preset": orb_preset,
        },
    }
    return _api_req("POST", "/v1/chart/natal", base_url, payload)


def make_transit(chart_id: str, date: str, time: str = "12:00:00", base_url: str = API_BASE):
    payload = {"natal_chart_id": chart_id, "date": date, "time": time}
    return _api_req("POST", "/v1/chart/transit", base_url, payload)


def make_synastry(person_a: str, person_b: str, base_url: str = API_BASE):
    payload = {"person_a": person_a, "person_b": person_b}
    return _api_req("POST", "/v1/chart/synastry", base_url, payload)


def synthesize(chart_id: str, provider: str = "rules", llm_config=None, base_url: str = API_BASE):
    payload = {"chart_id": chart_id, "provider": provider}
    if llm_config:
        payload["llm_config"] = llm_config
    return _api_req("POST", "/v1/analysis/synthesize", base_url, payload)


def transit_events(chart_id: str, start_date: str, end_date: str,
                   include_points=None, include_aspects=None, orb_preset="Modern", base_url: str = API_BASE):
    payload = {
        "chart_id": chart_id,
        "start_date": start_date,
        "end_date": end_date,
        "orb_preset": orb_preset,
    }
    if include_points:
        payload["include_points"] = include_points
    if include_aspects:
        payload["include_aspects"] = include_aspects
    return _api_req("POST", "/v1/analysis/transit-events", base_url, payload)


def period_impact_http(chart_id: str, date: str, orb_days: int = 7,
                       include_points=None, base_url: str = API_BASE):
    payload = {"chart_id": chart_id, "date": date, "orb_days": orb_days}
    if include_points:
        payload["include_points"] = include_points
    return _api_req("POST", "/v1/analysis/period-impact", base_url, payload)


def house_systems(base_url: str = API_BASE):
    return _api_req("GET", "/v1/houses/systems", base_url)


def export_ics(chart_id: str, start_date: str, end_date: str,
               filename: str = None, include_points=None, base_url: str = API_BASE):
    payload = {"chart_id": chart_id, "start_date": start_date, "end_date": end_date}
    if filename:
        payload["filename"] = filename
    if include_points:
        payload["include_points"] = include_points
    return _api_req("POST", "/v1/export/ics", base_url, payload)


def backup_db(output_dir: str = None, filename: str = None, base_url: str = API_BASE):
    payload = {}
    if output_dir:
        payload["output_dir"] = output_dir
    if filename:
        payload["filename"] = filename
    return _api_req("POST", "/v1/backup", base_url, payload)


# ------------------------------------------------------------------
# Public API: AstroClient

class AstroClient:
    """
    Library-first astrology client facade.

    Default backend is 'library' and requires no HTTP server. If the
    environment variable ASTRO_API_URL is set, or if backend='http' is
    passed, requests go to the HTTP API.

    The HTTP backend is intended for local/trusted networks unless
    wrapped by an external reverse proxy with authentication.
    """

    _LIBRARY_CHART_STORE: dict[str, dict] = {}

    def __init__(self, backend: str | None = None, base_url: str | None = None):
        if backend is not None and backend not in ("library", "http"):
            raise ValueError("backend must be 'library' or 'http'")
        env_url = os.environ.get("ASTRO_API_URL")
        if backend is None:
            backend = "http" if env_url else "library"
        self.backend = backend
        self.base_url = base_url or env_url or API_BASE
        if self.backend == "library":
            _ensure_ephe()

    def _validate_birth(self, date: str, time: str, timezone: str, latitude: float, longitude: float) -> None:
        _validate_lat_lon(latitude, longitude)
        datetime.strptime(date, "%Y-%m-%d")
        datetime.strptime(time, "%H:%M:%S")
        if timezone not in available_timezones():
            raise ValueError(f"Unknown timezone: {timezone}")

    def _get_library_db_path(self) -> Path:
        cache_dir = Path.home() / ".cache" / "astro"
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(cache_dir, 0o700)
        except OSError:
            pass
        db_path = cache_dir / "library.db"
        if not db_path.exists():
            # SQLite creates the file when we connect; set umask briefly.
            old_umask = os.umask(0o077)
            try:
                sqlite3.connect(str(db_path)).close()
            finally:
                os.umask(old_umask)
        return db_path

    def _init_library_db(self) -> None:
        db_path = self._get_library_db_path()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS charts (
                    chart_id TEXT PRIMARY KEY,
                    chart_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    chart_id TEXT NOT NULL REFERENCES charts(chart_id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _save_chart(self, chart_id: str, chart: dict) -> None:
        self._LIBRARY_CHART_STORE[chart_id] = chart
        self._init_library_db()
        db_path = self._get_library_db_path()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO charts (chart_id, chart_json) VALUES (?, ?) "
                "ON CONFLICT(chart_id) DO UPDATE SET chart_json=excluded.chart_json",
                (chart_id, json.dumps(chart, default=str)),
            )
            conn.commit()

    def _load_chart(self, chart_id: str) -> dict | None:
        if chart_id in self._LIBRARY_CHART_STORE:
            return self._LIBRARY_CHART_STORE[chart_id]
        self._init_library_db()
        db_path = self._get_library_db_path()
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.execute("SELECT chart_json FROM charts WHERE chart_id = ?", (chart_id,))
            row = cur.fetchone()
        if row is None:
            return None
        chart = json.loads(row[0])
        self._LIBRARY_CHART_STORE[chart_id] = chart
        return chart

    def find_person(self, name: str) -> dict | None:
        """Look up a person by name. Returns {id, name, chart_id} or None."""
        if self.backend == "http":
            people = list_people(base_url=self.base_url)
            if people.get("status") == "error":
                return None
            for p in people.get("people", []):
                if p.get("name") == name:
                    return p
            return None

        self._init_library_db()
        db_path = self._get_library_db_path()
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.execute("SELECT id, name, chart_id FROM people WHERE name = ?", (name,))
            row = cur.fetchone()
        if row is None:
            return None
        return {"id": row[0], "name": row[1], "chart_id": row[2]}

    def list_people(self) -> dict:
        """List all people in the store.

        Returns the same shape as the HTTP backend: {"status": "ok",
        "people": [{"id", "name", "chart_id"}, ...]} so GUI callers work
        against either backend.
        """
        if self.backend == "http":
            return list_people(base_url=self.base_url)

        self._init_library_db()
        db_path = self._get_library_db_path()
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.execute("SELECT id, name, chart_id FROM people ORDER BY name")
            rows = cur.fetchall()
        return {
            "status": "ok",
            "people": [{"id": r[0], "name": r[1], "chart_id": r[2]} for r in rows],
        }

    def create_person(self, name: str, natal_chart_id: str) -> dict:
        """Create or update a person pointing to an existing natal chart."""
        _validate_uuid(natal_chart_id)
        if self.backend == "http":
            payload = {"name": name, "natal_chart_id": natal_chart_id}
            result = _api_req("POST", "/v1/people", self.base_url, payload)
            if result.get("status") == "error":
                raise RuntimeError(result.get("message", "Failed to create person"))
            return result.get("person", result)

        chart = self._load_chart(natal_chart_id)
        if chart is None:
            raise KeyError(f"Chart not found: {natal_chart_id}")
        self._init_library_db()
        db_path = self._get_library_db_path()
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO people (name, chart_id) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET chart_id=excluded.chart_id",
                (name, natal_chart_id),
            )
            conn.commit()
            cur = conn.execute("SELECT id, name, chart_id FROM people WHERE name = ?", (name,))
            row = cur.fetchone()
        return {"id": row[0], "name": row[1], "chart_id": row[2]}

    def get_person_natal_chart(self, name: str) -> dict | None:
        """Return the natal chart dict for a person by name, or None."""
        person = self.find_person(name)
        if person is None:
            return None
        return self.get_chart(person["chart_id"])

    def natal(self, name: str, date: str, time: str, timezone: str,
              latitude: float, longitude: float, points=None,
              house_system: str = "K", orb_preset: str = "Modern") -> dict:
        """Calculate a natal chart."""
        if self.backend == "http":
            return make_natal(
                name=name, date=date, time=time, timezone=timezone,
                latitude=latitude, longitude=longitude,
                points=points, house_system=house_system, orb_preset=orb_preset,
                base_url=self.base_url,
            )

        self._validate_birth(date, time, timezone, latitude, longitude)
        points = points or list(DEFAULT_POINTS)
        body_ids = _points_to_ids(points)
        jd, _ = _parse_datetime(date, time, timezone)
        chart_data = ac_calc_chart(jd, latitude, longitude, body_ids, house_system)
        bodies = _insert_south_node(chart_data["bodies"])
        orb_code = orb_preset_from_name(orb_preset)
        aspects = calculate_aspects(bodies, orb_code)
        chart_id = str(uuid.uuid4())

        result = {
            "status": "ok",
            "chart_id": chart_id,
            "bodies": bodies,
            "houses": chart_data["houses"],
            "angles": {
                "ascendant": chart_data["ascendant"],
                "mc": chart_data["mc"],
                "armc": chart_data["armc"],
                "vertex": chart_data["vertex"],
            },
            "aspects": aspects,
            "meta": {
                "name": name,
                "birth_date": date,
                "birth_time": time,
                "timezone": timezone,
                "latitude": latitude,
                "longitude": longitude,
                "house_system": house_system,
                "orb_preset": orb_preset,
                "points": points,
            },
        }
        self._save_chart(chart_id, result)
        return result

    def transit(self, chart_id: str, date: str, time: str = "12:00:00") -> dict:
        """Calculate transit chart for a given date."""
        if self.backend == "http":
            return make_transit(chart_id, date, time, base_url=self.base_url)

        _validate_uuid(chart_id)
        natal = self._load_chart(chart_id)
        if natal is None:
            raise KeyError(f"Chart not found: {chart_id}")
        meta = natal["meta"]
        datetime.strptime(date, "%Y-%m-%d")
        datetime.strptime(time, "%H:%M:%S")

        jd, _ = _parse_datetime(date, time, meta["timezone"])
        body_ids = [
            body_id_from_name(b["name"])
            for b in natal["bodies"]
            if b.get("name", "").lower() != "south node"
        ]
        transit_data = ac_calc_chart(jd, meta["latitude"], meta["longitude"],
                                     body_ids, meta["house_system"])
        transit_bodies = _insert_south_node(transit_data["bodies"])

        # Cross-aspects: transiting bodies vs natal bodies (review item 14)
        orb_name = meta.get("orb_preset", "Modern")
        preset = orb_preset_from_name(orb_name)
        natal_bodies = natal["bodies"]
        cross_aspects = []
        for tb in transit_bodies:
            for nb in natal_bodies:
                asp = ac_detect_aspect(
                    tb["longitude"], tb["speed"],
                    nb["longitude"], nb["speed"],
                    preset,
                )
                if asp["aspect"] != AC_ASP_NONE:
                    cross_aspects.append({
                        "transit_body": tb["name"],
                        "natal_body": nb["name"],
                        "aspect_id": asp["aspect"],
                        "aspect_name": asp["aspect_name"],
                        "exact_angle": asp["exact_angle"],
                        "actual_angle": asp["actual_angle"],
                        "orb": asp["orb"],
                        "applying": asp["applying"],
                    })

        return {
            "status": "ok",
            "natal_chart_id": chart_id,
            "transit_date": date,
            "transit_time": time,
            "bodies": transit_bodies,
            "houses": transit_data["houses"],
            "angles": {
                "ascendant": transit_data["ascendant"],
                "mc": transit_data["mc"],
            },
            "cross_aspects": cross_aspects,
        }

    def period_impact(self, chart_id: str, date: str, orb_days: int = 7,
                      include_points=None) -> dict:
        """Calculate period impact for a single date."""
        if self.backend == "http":
            return period_impact_http(chart_id, date, orb_days, include_points, base_url=self.base_url)

        _validate_uuid(chart_id)
        natal = self._load_chart(chart_id)
        if natal is None:
            raise KeyError(f"Chart not found: {chart_id}")

        impact = _analyze_period_impact(
            natal_chart=natal,
            date=date,
            orb_days=orb_days,
            include_points=include_points,
        )
        return {
            "status": "ok",
            "chart_id": chart_id,
            "date": date,
            "orb_days": orb_days,
            "impact": {
                "active_transits": impact.get("active_transits", []),
                "summary": f"{len(impact.get('active_transits', []))} active transits within {orb_days} days",
            },
        }

    def get_chart(self, chart_id: str) -> dict:
        """Retrieve a chart by ID."""
        _validate_uuid(chart_id)
        if self.backend == "http":
            result = get_chart(chart_id, base_url=self.base_url)
            if result.get("status") == "error":
                raise KeyError(result.get("message", "Chart not found"))
            return result.get("chart", result)
        chart = self._load_chart(chart_id)
        if chart is None:
            raise KeyError(f"Chart not found: {chart_id}")
        return chart

    def synastry(self, chart_id_a: str, chart_id_b: str) -> dict:
        """Calculate synastry between two stored charts."""
        _validate_uuid(chart_id_a)
        _validate_uuid(chart_id_b)
        chart_a = self._load_chart(chart_id_a)
        if chart_a is None:
            raise KeyError(f"Chart not found: {chart_id_a}")
        chart_b = self._load_chart(chart_id_b)
        if chart_b is None:
            raise KeyError(f"Chart not found: {chart_id_b}")

        bodies_a = chart_a["bodies"]
        bodies_b = chart_b["bodies"]
        orb_name = chart_a["meta"]["orb_preset"]
        preset = orb_preset_from_name(orb_name)
        cross_aspects = []
        for ba in bodies_a:
            for bb in bodies_b:
                asp = ac_detect_aspect(ba["longitude"], ba["speed"],
                                       bb["longitude"], bb["speed"],
                                       preset)
                if asp["aspect"] != AC_ASP_NONE:
                    cross_aspects.append({
                        "body_a": ba["name"],
                        "body_b": bb["name"],
                        "aspect_id": asp["aspect"],
                        "aspect_name": asp["aspect_name"],
                        "exact_angle": asp["exact_angle"],
                        "actual_angle": asp["actual_angle"],
                        "orb": asp["orb"],
                        "applying": asp["applying"],
                    })
        return {
            "status": "ok",
            "person_a": chart_id_a,
            "person_b": chart_id_b,
            "cross_aspects": cross_aspects,
        }


# ------------------------------------------------------------------
# Module-level convenience (for backward compatibility)

_default_client = None

def get_default_client() -> AstroClient:
    """Get or create the default client (library backend)."""
    global _default_client
    if _default_client is None:
        _default_client = AstroClient()
    return _default_client


def natal(*args, **kwargs):
    """Convenience: calculate natal chart using default client."""
    return get_default_client().natal(*args, **kwargs)


def transit(chart_id: str, date: str, time: str = "12:00:00"):
    """Convenience: calculate transit using default client."""
    return get_default_client().transit(chart_id, date, time)


def period_impact(chart_id: str, date: str, orb_days: int = 7, include_points=None):
    """Convenience: calculate period impact using default client."""
    return get_default_client().period_impact(chart_id, date, orb_days, include_points)


__all__ = [
    "AstroClient",
    "get_default_client",
    "natal",
    "transit",
    "period_impact",
    "DEFAULT_POINTS",
    "ALL_POINTS",
    "BodySet",
    "API_BASE",
    "ASPECTS",
    "HOUSES",
    "make_natal",
    "make_transit",
    "make_synastry",
    "synthesize",
    "transit_events",
    "period_impact_http",
    "get_chart",
    "house_systems",
    "export_ics",
    "backup_db",
    "create_person",
    "list_people",
    "get_person",
]
