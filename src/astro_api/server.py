#!/usr/bin/env python3
"""
Astrology JSON REST API server - Python stdlib only.
Runs on localhost:8081.

Phase 4 updates:
- Full SQLite schema (people, events, charts, interpretations, api_keys)
- New endpoints: /v1/people, /v1/people/{id}, /v1/people/{id}/charts,
  /v1/charts/{chart_id}
- All DB access via astro_data.db with parameterized queries.
"""
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from zoneinfo import ZoneInfo, available_timezones
from urllib.parse import urlparse

# ------------------------------------------------------------------
# Ensure libswe.so can be found before we load our C extension.

_SE_DIR = os.path.expanduser("~/swisseph_test/pyswisseph-2.10.3.2/libswe")
_ld = os.environ.get("LD_LIBRARY_PATH", "")
if _SE_DIR not in (_ld.split(":") if _ld else []):
    os.environ["LD_LIBRARY_PATH"] = _SE_DIR + (":" + _ld if _ld else "")
    os.execv(sys.executable, [sys.executable] + sys.argv)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astro_api.astro_ctypes import (
    ac_init,
    ac_cleanup,
    ac_date_to_jd,
    ac_calc_chart,
    ac_detect_aspect,
    calculate_aspects,
    body_id_from_name,
    orb_preset_from_name,
    HOUSE_SYSTEMS,
    AC_ASP_NONE,
)
from astro_data import db
from astro_analyze.transits import find_transit_events, period_impact
from astro_analyze.scoring import aspect_priority, compute_planetary_grid_weights, MAJOR_ASPECTS
from astro_analyze.analysis import analyze_chart
from astro_analyze.synthesis import get_provider
from astro_analyze.cookbook import enrich_chart, enrich_transit, enrich_synastry

# ------------------------------------------------------------------
# Defaults

DEFAULT_POINTS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Mean Node", "Chiron",
]

# ------------------------------------------------------------------
# Database

_DEFAULT_DB_PATH = os.path.expanduser("~/second-brain/data/astro.db")
DB_PATH = os.environ.get("ASTRO_DB_PATH", _DEFAULT_DB_PATH)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
_db_conn = None


def get_db():
    global _db_conn
    if _db_conn is None:
        _db_conn = db.init_db(DB_PATH)
    return _db_conn


_LEGACY_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "charts.db")


def _migrate_legacy_charts():
    if not os.path.exists(_LEGACY_DB) or os.path.getsize(_LEGACY_DB) == 0:
        return
    try:
        old = sqlite3.connect(_LEGACY_DB, check_same_thread=False)
        rows = old.execute(
            "SELECT chart_id, name, birth_date, birth_time, timezone, latitude, longitude, house_system, points, orb_preset, chart_json, created_at FROM charts"
        ).fetchall()
        conn = get_db()
        for row in rows:
            (cid, name, bdate, btime, tz, lat, lon, hs, pts, orb, cjson, cat) = row
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO charts (chart_id, person_id, chart_type, calc_date, calc_options, positions, dignities, aspects, rendered_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (cid, None, "natal", cat, json.dumps({"house_system": hs, "points": pts, "orb_preset": orb}),
                     cjson, None, json.dumps([]), None, cat),
                )
            except Exception:
                pass
        conn.commit()
        old.close()
    except Exception:
        pass


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------
# Helpers

def _json_response(handler, data, status=200):
    body = json.dumps(data, indent=None, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _error(handler, message, status=400):
    _json_response(handler, {"status": "error", "message": message}, status)


def parse_datetime(date_str, time_str, tz_name):
    if tz_name not in available_timezones():
        raise ValueError(f"Unknown timezone: {tz_name}")
    dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    tz = ZoneInfo(tz_name)
    dt = dt_naive.replace(tzinfo=tz)
    offset = dt.utcoffset().total_seconds() / 3600.0
    jd = ac_date_to_jd(dt_naive.year, dt_naive.month, dt_naive.day,
                       dt_naive.hour, dt_naive.minute, dt_naive.second, offset)
    return jd


# ------------------------------------------------------------------
# Route dispatch

class AstroHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/v1/houses/systems":
            self._handle_house_systems()
        elif path == "/v1/people":
            self._handle_list_people()
        elif path.startswith("/v1/people/"):
            self._dispatch_people_get(path)
        elif path.startswith("/v1/charts/"):
            self._handle_get_chart(path[len("/v1/charts/"):])
        else:
            _error(self, "Not found", 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            _error(self, f"Invalid JSON: {e}")
            return

        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/v1/chart/transit":
            self._handle_transit(payload)
        elif path == "/v1/chart/synastry":
            self._handle_synastry(payload)
        elif path == "/v1/chart/calculate":
            self._handle_chart_calculate(payload)
        elif path == "/v1/analysis/transit-events":
            self._handle_transit_events(payload)
        elif path == "/v1/analysis/period-impact":
            self._handle_period_impact(payload)
        elif path == "/v1/people":
            self._handle_create_person(payload)
        elif path == "/v1/people/with-natal-chart":
            self._handle_create_person_with_natal_chart(payload)
        elif path.startswith("/v1/people/") and "/charts" in path:
            self._dispatch_people_post(path, payload)
        elif path == "/v1/analysis/synthesize":
            self._handle_synthesize(payload)
        elif path == "/v1/export/ics":
            self._handle_export_ics(payload)
        elif path == "/v1/export/csv":
            self._handle_export_csv(payload)
        elif path == "/v1/backup":
            self._handle_backup(payload)
        elif path == "/v1/restore":
            self._handle_restore(payload)
        else:
            _error(self, "Not found", 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/v1/charts/"):
            self._handle_delete_chart(path[len("/v1/charts/"):])
        else:
            _error(self, "Not found", 404)

    # --------------------------------------------------------------
    # Sub-dispatch

    def _dispatch_people_get(self, path):
        rest = path[len("/v1/people/"):]
        parts = rest.split("/")
        if len(parts) == 2 and parts[1] == "charts":
            # GET /v1/people/{id}/charts is not implemented; chart creation is POST
            _error(self, "Method not allowed", 405)
        elif len(parts) == 2 and parts[1] == "natal-chart":
            self._handle_get_natal_chart_for_person(parts[0])
        elif len(parts) == 1:
            self._handle_get_person(parts[0])
        else:
            _error(self, "Not found", 404)

    def _dispatch_people_post(self, path, payload):
        rest = path[len("/v1/people/"):]
        parts = rest.split("/")
        if len(parts) == 2 and parts[1] == "charts":
            self._handle_calc_chart_for_person(parts[0], payload)
        else:
            _error(self, "Not found", 404)

    # --------------------------------------------------------------
    # House systems

    def _handle_house_systems(self):
        systems = [{"code": code, "name": name} for code, name in HOUSE_SYSTEMS.items()]
        systems.sort(key=lambda x: x["code"])
        _json_response(self, {"status": "ok", "systems": systems})

    # --------------------------------------------------------------
    # People endpoints

    def _handle_create_person(self, payload):
        required = ["name", "birth_date", "birth_time", "timezone", "latitude", "longitude"]
        missing = [f for f in required if payload.get(f) is None]
        if missing:
            _error(self, f"Missing required fields: {', '.join(missing)}")
            return
        try:
            pid = db.add_person(
                get_db(),
                name=payload["name"],
                birth_date=payload["birth_date"],
                birth_time=payload["birth_time"],
                timezone=payload["timezone"],
                latitude=payload["latitude"],
                longitude=payload["longitude"],
                gender=payload.get("gender"),
                phone=payload.get("phone"),
                email=payload.get("email"),
                address=payload.get("address"),
                notes=payload.get("notes"),
            )
            p = db.get_person(get_db(), pid)
            _json_response(self, {"status": "ok", "person": p})
        except Exception as e:
            _error(self, str(e), 500)

    def _handle_get_person(self, person_id_str):
        try:
            pid = int(person_id_str)
        except ValueError:
            _error(self, "Invalid person ID", 400)
            return
        p = db.get_person(get_db(), pid)
        if not p:
            _error(self, "Person not found", 404)
            return
        _json_response(self, {"status": "ok", "person": p})

    def _handle_list_people(self):
        people = db.list_people(get_db())
        _json_response(self, {"status": "ok", "people": people})

    def _handle_get_natal_chart_for_person(self, person_id_str):
        try:
            pid = int(person_id_str)
        except ValueError:
            _error(self, "Invalid person ID", 400)
            return
        p = db.get_person(get_db(), pid)
        if not p:
            _error(self, "Person not found", 404)
            return
        natal_chart = db.get_natal_chart_by_person_id(get_db(), pid)
        if not natal_chart:
            _json_response(self, {"status": "ok", "person_id": pid, "natal_chart": None})
            return
        _json_response(self, {"status": "ok", "person_id": pid, "natal_chart": natal_chart})

    def _handle_create_person_with_natal_chart(self, payload):
        """
        Create a person, their natal event, and natal chart in one atomic operation.
        """
        required = ["name", "birth_date", "birth_time", "timezone", "latitude", "longitude"]
        missing = [f for f in required if payload.get(f) is None]
        if missing:
            _error(self, f"Missing required fields: {', '.join(missing)}")
            return
        options = payload.get("options", {})
        hs = options.get("house_system", "K")
        points_names = options.get("points", DEFAULT_POINTS)
        orb_name = options.get("orb_preset", "Modern")
        try:
            jd = parse_datetime(
                payload["birth_date"], payload["birth_time"], payload["timezone"]
            )
        except Exception as e:
            _error(self, str(e), 400)
            return
        try:
            body_ids = [body_id_from_name(pn) for pn in points_names]
            chart_data = ac_calc_chart(jd, payload["latitude"], payload["longitude"], body_ids, hs)
            orb_preset = orb_preset_from_name(orb_name)
            aspects = calculate_aspects(chart_data["bodies"], orb_preset)
            positions = {
                "bodies": chart_data["bodies"],
                "houses": chart_data["houses"],
                "angles": {
                    "ascendant": chart_data["ascendant"],
                    "mc": chart_data["mc"],
                    "armc": chart_data["armc"],
                    "vertex": chart_data["vertex"],
                },
                "latitude": payload["latitude"],
                "longitude": payload["longitude"],
            }
            result = db.create_person_with_natal_chart(
                get_db(),
                name=payload["name"],
                birth_date=payload["birth_date"],
                birth_time=payload["birth_time"],
                timezone=payload["timezone"],
                latitude=payload["latitude"],
                longitude=payload["longitude"],
                gender=payload.get("gender"),
                phone=payload.get("phone"),
                email=payload.get("email"),
                address=payload.get("address"),
                notes=payload.get("notes"),
                chart_positions=positions,
                chart_aspects=aspects,
                calc_options={"house_system": hs, "points": points_names, "orb_preset": orb_name},
                calc_date=_now_iso(),
            )
            _json_response(self, {"status": "ok", "person_id": result["person_id"], "event_id": result["event_id"], "chart_id": result["chart_id"]})
        except Exception as e:
            _error(self, str(e), 500)

    # --------------------------------------------------------------
    # Chart-for-person endpoint

    def _handle_calc_chart_for_person(self, person_id_str, options):
        try:
            pid = int(person_id_str)
        except ValueError:
            _error(self, "Invalid person ID", 400)
            return
        p = db.get_person(get_db(), pid)
        if not p:
            _error(self, "Person not found", 404)
            return

        hs = options.get("house_system", "K")
        points_names = options.get("points", DEFAULT_POINTS)
        orb_name = options.get("orb_preset", "Modern")

        try:
            jd = parse_datetime(p["birth_date"], p["birth_time"], p["timezone"])
        except Exception as e:
            _error(self, str(e), 400)
            return

        try:
            body_ids = [body_id_from_name(pn) for pn in points_names]
            chart_data = ac_calc_chart(jd, p["latitude"], p["longitude"], body_ids, hs)
            orb_preset = orb_preset_from_name(orb_name)
            aspects = calculate_aspects(chart_data["bodies"], orb_preset)

            chart_id = str(uuid.uuid4())
            positions = {
                "bodies": chart_data["bodies"],
                "houses": chart_data["houses"],
                "angles": {
                    "ascendant": chart_data["ascendant"],
                    "mc": chart_data["mc"],
                    "armc": chart_data["armc"],
                    "vertex": chart_data["vertex"],
                },
                "latitude": p["latitude"],
                "longitude": p["longitude"],
            }
            db.add_chart(
                get_db(),
                chart_id=chart_id,
                person_id=pid,
                chart_type="natal",
                calc_date=_now_iso(),
                calc_options={"house_system": hs, "points": points_names, "orb_preset": orb_name},
                positions=positions,
                aspects=aspects,
            )

            cookbook = enrich_chart(get_db(), {"bodies": chart_data["bodies"], "aspects": aspects})

            response = {
                "status": "ok",
                "chart_id": chart_id,
                "person_id": pid,
                "bodies": chart_data["bodies"],
                "houses": chart_data["houses"],
                "aspects": aspects,
                "angles": positions["angles"],
                "cookbook": cookbook,
            }
            _json_response(self, response)
        except Exception as e:
            _error(self, str(e), 500)

    # --------------------------------------------------------------
    # Chart retrieval / deletion

    def _handle_get_chart(self, chart_id):
        c = db.get_chart(get_db(), chart_id)
        if not c:
            _error(self, "Chart not found", 404)
            return
        # Enrich with cookbook if positions exist
        try:
            cookbook = enrich_chart(get_db(), c.get("positions", {}))
            c["cookbook"] = cookbook
        except Exception:
            pass
        _json_response(self, {"status": "ok", "chart": c})

    def _handle_delete_chart(self, chart_id):
        ok = db.delete_chart(get_db(), chart_id)
        if not ok:
            _error(self, "Chart not found", 404)
            return
        _json_response(self, {"status": "ok", "deleted": chart_id})

    def _handle_transit(self, payload):
        try:
            natal_id = payload.get("natal_chart_id")
            date = payload.get("date")
            time = payload.get("time")
            options = payload.get("options", {})
            event_type = payload.get("event")

            if not natal_id or not date or not time:
                _error(self, "Missing natal_chart_id, date, or time")
                return

            natal_row = db.get_chart(get_db(), natal_id)
            if not natal_row:
                _error(self, "Natal chart not found", 404)
                return

            calc_opts = natal_row.get("calc_options") or {}
            hs = calc_opts.get("house_system", "K")
            points_names = calc_opts.get("points", DEFAULT_POINTS)
            orb_name = calc_opts.get("orb_preset", "Modern")

            lat = lon = tz = None
            person_id = None
            if natal_row.get("person_id"):
                person = db.get_person(get_db(), natal_row["person_id"])
                if person:
                    lat = person["latitude"]
                    lon = person["longitude"]
                    tz = person["timezone"]
                    person_id = person["id"]
            if lat is None:
                _error(self, "Natal chart missing location data", 400)
                return

            jd = parse_datetime(date, time, tz)
            body_ids = [body_id_from_name(p) for p in points_names]
            transiting = ac_calc_chart(jd, lat, lon, body_ids, hs)
            orb_preset = orb_preset_from_name(orb_name)

            natal_bodies = natal_row["positions"]["bodies"]
            transit_bodies = transiting["bodies"]

            cross_aspects = []
            for nb in natal_bodies:
                for tb in transit_bodies:
                    asp = ac_detect_aspect(nb["longitude"], nb["speed"],
                                           tb["longitude"], tb["speed"],
                                           orb_preset)
                    if asp["aspect"] != AC_ASP_NONE:
                        cross_aspects.append({
                            "natal_body": nb["name"],
                            "transit_body": tb["name"],
                            "aspect_id": asp["aspect"],
                            "aspect_name": asp["aspect_name"],
                            "exact_angle": asp["exact_angle"],
                            "actual_angle": asp["actual_angle"],
                            "orb": asp["orb"],
                            "applying": asp["applying"],
                        })

            # Attach composite priority (relative value) to each cross aspect.
            # days_to_exact is approximated from the applying flag: applying
            # aspects are scored as approaching (days=+1), separating as past
            # (days=-1); exact aspects get days=0.
            natal_signs = {b["name"]: b.get("sign_name", "") for b in natal_bodies}
            transit_signs = {b["name"]: b.get("sign_name", "") for b in transit_bodies}
            grid_weights = compute_planetary_grid_weights({
                "bodies": transit_bodies,
                "aspects": [
                    {
                        "body_a": a["transit_body"],
                        "body_b": a["natal_body"],
                        "aspect_name": a["aspect_name"],
                        "orb": a["orb"],
                    }
                    for a in cross_aspects
                ],
            })
            for a in cross_aspects:
                aspect_name = (a.get("aspect_name") or "").lower()
                if aspect_name not in MAJOR_ASPECTS:
                    continue
                days = 0 if a.get("orb", 999) < 0.5 else (1 if a.get("applying") else -1)
                a["priority"] = aspect_priority(
                    a["transit_body"], transit_signs.get(a["transit_body"], ""),
                    a["natal_body"], natal_signs.get(a["natal_body"], ""),
                    a["orb"], days, aspect_name,
                    grid_weight=grid_weights.get(a["transit_body"], 1.0),
                )
            cross_aspects.sort(key=lambda x: (-x.get("priority", 0), x.get("orb", 999)))

            response = {
                "status": "ok",
                "natal_chart_id": natal_id,
                "bodies": natal_bodies,
                "transiting_bodies": transit_bodies,
                "cross_aspects": cross_aspects,
            }

            try:
                cookbook = enrich_transit(
                    get_db(),
                    natal_chart={"bodies": natal_bodies},
                    transit_data={"bodies": transit_bodies},
                    cross_aspects=cross_aspects,
                )
                response["cookbook"] = cookbook
            except Exception:
                pass

            if event_type and person_id:
                event_id = db.add_event(
                    get_db(),
                    name=f"{event_type} on {date}",
                    event_date=date,
                    event_time=time,
                    timezone=tz,
                    latitude=lat,
                    longitude=lon,
                    event_type=event_type,
                    person_id=person_id,
                    notes=f"Transit chart for natal chart {natal_id}",
                )
                transit_chart_id = str(uuid.uuid4())
                positions = {
                    "bodies": transit_bodies,
                    "houses": transiting["houses"],
                    "angles": {
                        "ascendant": transiting["ascendant"],
                        "mc": transiting["mc"],
                        "armc": transiting["armc"],
                        "vertex": transiting["vertex"],
                    },
                    "latitude": lat,
                    "longitude": lon,
                }
                db.add_chart(
                    get_db(),
                    chart_id=transit_chart_id,
                    person_id=person_id,
                    event_id=event_id,
                    chart_type="transit",
                    calc_date=_now_iso(),
                    calc_options={"house_system": hs, "points": points_names, "orb_preset": orb_name},
                    positions=positions,
                    aspects=cross_aspects,
                )
                response["transit_event_id"] = event_id
                response["transit_chart_id"] = transit_chart_id

            _json_response(self, response)
        except Exception as e:
            _error(self, str(e), 500)

    def _handle_chart_calculate(self, payload):
        """Ad-hoc chart calculation — does NOT persist to database."""
        try:
            person = payload.get("person", {})
            options = payload.get("options", {})

            name = person.get("name", "Unknown")
            date = person.get("birth_date")
            time = person.get("birth_time")
            tz = person.get("timezone")
            lat = person.get("latitude")
            lon = person.get("longitude")

            if not all([date, time, tz, lat is not None, lon is not None]):
                _error(self, "Missing required person fields")
                return

            hs = options.get("house_system", "K")
            points_names = options.get("points", DEFAULT_POINTS)
            orb_name = options.get("orb_preset", "Modern")

            jd = parse_datetime(date, time, tz)
            body_ids = [body_id_from_name(p) for p in points_names]
            chart_data = ac_calc_chart(jd, lat, lon, body_ids, hs)
            orb_preset = orb_preset_from_name(orb_name)
            aspects = calculate_aspects(chart_data["bodies"], orb_preset)

            response = {
                "status": "ok",
                "name": name,
                "bodies": chart_data["bodies"],
                "houses": chart_data["houses"],
                "aspects": aspects,
                "angles": {
                    "ascendant": chart_data["ascendant"],
                    "mc": chart_data["mc"],
                    "armc": chart_data["armc"],
                    "vertex": chart_data["vertex"],
                },
                "latitude": lat,
                "longitude": lon,
            }
            _json_response(self, response)
        except Exception as e:
            _error(self, str(e), 500)

    def _handle_synastry(self, payload):
        try:
            a_id = payload.get("person_a")
            b_id = payload.get("person_b")
            options = payload.get("options", {})

            if not a_id or not b_id:
                _error(self, "Missing person_a or person_b chart IDs")
                return

            chart_a = db.get_chart(get_db(), a_id)
            chart_b = db.get_chart(get_db(), b_id)
            if not chart_a:
                _error(self, "Chart A not found", 404)
                return
            if not chart_b:
                _error(self, "Chart B not found", 404)
                return

            calc_opts = chart_a.get("calc_options") or {}
            orb_name = options.get("orb_preset", calc_opts.get("orb_preset", "Modern"))
            orb_preset = orb_preset_from_name(orb_name)

            bodies_a = chart_a["positions"]["bodies"]
            bodies_b = chart_b["positions"]["bodies"]

            cross_aspects = []
            for ba in bodies_a:
                for bb in bodies_b:
                    asp = ac_detect_aspect(ba["longitude"], ba["speed"],
                                           bb["longitude"], bb["speed"],
                                           orb_preset)
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

            response = {
                "status": "ok",
                "person_a": a_id,
                "person_b": b_id,
                "cross_aspects": cross_aspects,
            }

            try:
                cookbook = enrich_synastry(
                    get_db(),
                    chart_a_bodies=bodies_a,
                    chart_b_bodies=bodies_b,
                    cross_aspects=cross_aspects,
                )
                response["cookbook"] = cookbook
            except Exception:
                pass

            _json_response(self, response)
        except Exception as e:
            _error(self, str(e), 500)



    # --------------------------------------------------------------
    # Transit analysis endpoints (Phase 6)

    def _handle_transit_events(self, payload):
        try:
            chart_id = payload.get("chart_id")
            start_date = payload.get("start_date")
            end_date = payload.get("end_date")
            include_points = payload.get("include_points")
            include_aspects = payload.get("include_aspects")
            orb_preset = payload.get("orb_preset", "Modern")

            if not chart_id or not start_date or not end_date:
                _error(self, "Missing chart_id, start_date, or end_date")
                return

            natal_row = db.get_chart(get_db(), chart_id)
            if not natal_row:
                _error(self, "Chart not found", 404)
                return

            natal_chart = natal_row.get("positions", {})
            if not natal_chart.get("bodies"):
                _error(self, "Chart has no body positions", 400)
                return

            # attach metadata so transits module can pick it up
            calc_opts = natal_row.get("calc_options") or {}
            natal_chart["latitude"] = natal_chart.get("latitude", 0.0)
            natal_chart["longitude"] = natal_chart.get("longitude", 0.0)
            natal_chart["house_system"] = calc_opts.get("house_system", "K")

            events = find_transit_events(
                natal_chart,
                start_date,
                end_date,
                include_points=include_points,
                include_aspects=include_aspects,
                orb_preset=orb_preset,
            )
            _json_response(self, {
                "status": "ok",
                "chart_id": chart_id,
                "start_date": start_date,
                "end_date": end_date,
                "events": events,
                "count": len(events),
            })
        except Exception as e:
            _error(self, str(e), 500)

    def _handle_period_impact(self, payload):
        try:
            chart_id = payload.get("chart_id")
            date = payload.get("date")
            orb_days = payload.get("orb_days", 7)
            include_points = payload.get("include_points")

            if not chart_id or not date:
                _error(self, "Missing chart_id or date")
                return

            natal_row = db.get_chart(get_db(), chart_id)
            if not natal_row:
                _error(self, "Chart not found", 404)
                return

            natal_chart = natal_row.get("positions", {})
            if not natal_chart.get("bodies"):
                _error(self, "Chart has no body positions", 400)
                return

            calc_opts = natal_row.get("calc_options") or {}
            natal_chart["latitude"] = natal_chart.get("latitude", 0.0)
            natal_chart["longitude"] = natal_chart.get("longitude", 0.0)
            natal_chart["house_system"] = calc_opts.get("house_system", "K")

            impact = period_impact(
                natal_chart,
                date,
                orb_days=orb_days,
                include_points=include_points,
            )
            _json_response(self, {
                "status": "ok",
                "chart_id": chart_id,
                "date": date,
                "orb_days": orb_days,
                "impact": impact,
            })
        except Exception as e:
            _error(self, str(e), 500)


    # --------------------------------------------------------------
    # Synthesis endpoint (Phase 7)

    def _handle_synthesize(self, payload):
        try:
            chart_id = payload.get("chart_id")
            provider_name = payload.get("provider", "rules")
            llm_config = payload.get("llm_config", {})

            if not chart_id:
                _error(self, "Missing chart_id")
                return

            natal_row = db.get_chart(get_db(), chart_id)
            if not natal_row:
                _error(self, "Chart not found", 404)
                return

            natal_chart = natal_row.get("positions", {})
            if not natal_chart.get("bodies"):
                _error(self, "Chart has no body positions", 400)
                return

            # Attach aspects if stored separately
            aspects = natal_row.get("aspects", [])
            if isinstance(aspects, str):
                try:
                    aspects = json.loads(aspects)
                except Exception:
                    aspects = []
            natal_chart["aspects"] = aspects

            analysis = analyze_chart(natal_chart)
            cookbook = enrich_chart(get_db(), natal_chart)

            provider = get_provider({"provider": provider_name, "llm_config": llm_config})
            # Merge cookbook into analysis so RulesProvider can compose from atoms
            enriched_analysis = dict(analysis)
            enriched_analysis["cookbook"] = cookbook
            interpretation = provider.generate(enriched_analysis)

            _json_response(self, {
                "status": "ok",
                "chart_id": chart_id,
                "provider": provider_name,
                "cookbook": cookbook,
                "interpretation": interpretation,
            })
        except Exception as e:
            _error(self, str(e), 500)

    # --------------------------------------------------------------
    # Export endpoints (Phase 8)

    def _handle_export_ics(self, payload):
        try:
            chart_id = payload.get("chart_id")
            start_date = payload.get("start_date")
            end_date = payload.get("end_date")
            include_points = payload.get("include_points")
            filename = payload.get("filename", "transits.ics")
            orb_preset = payload.get("orb_preset", "Modern")

            if not chart_id or not start_date or not end_date:
                _error(self, "Missing chart_id, start_date, or end_date")
                return

            natal_row = db.get_chart(get_db(), chart_id)
            if not natal_row:
                _error(self, "Chart not found", 404)
                return

            natal_chart = natal_row.get("positions", {})
            if not natal_chart.get("bodies"):
                _error(self, "Chart has no body positions", 400)
                return

            calc_opts = natal_row.get("calc_options") or {}
            natal_chart["latitude"] = natal_chart.get("latitude", 0.0)
            natal_chart["longitude"] = natal_chart.get("longitude", 0.0)
            natal_chart["house_system"] = calc_opts.get("house_system", "K")

            events = find_transit_events(
                natal_chart,
                start_date,
                end_date,
                include_points=include_points,
                orb_preset=orb_preset,
            )

            from astro_analyze.calendar import export_to_ics
            filepath = os.path.join(os.path.dirname(DB_PATH), filename)
            export_to_ics(events, filepath)
            _json_response(self, {
                "status": "ok",
                "chart_id": chart_id,
                "events_count": len(events),
                "filepath": filepath,
            })
        except Exception as e:
            _error(self, str(e), 500)

    def _handle_export_csv(self, payload):
        try:
            chart_id = payload.get("chart_id")
            start_date = payload.get("start_date")
            end_date = payload.get("end_date")
            include_points = payload.get("include_points")
            filename = payload.get("filename", "transits.csv")
            orb_preset = payload.get("orb_preset", "Modern")

            if not chart_id or not start_date or not end_date:
                _error(self, "Missing chart_id, start_date, or end_date")
                return

            natal_row = db.get_chart(get_db(), chart_id)
            if not natal_row:
                _error(self, "Chart not found", 404)
                return

            natal_chart = natal_row.get("positions", {})
            if not natal_chart.get("bodies"):
                _error(self, "Chart has no body positions", 400)
                return

            calc_opts = natal_row.get("calc_options") or {}
            natal_chart["latitude"] = natal_chart.get("latitude", 0.0)
            natal_chart["longitude"] = natal_chart.get("longitude", 0.0)
            natal_chart["house_system"] = calc_opts.get("house_system", "K")

            events = find_transit_events(
                natal_chart,
                start_date,
                end_date,
                include_points=include_points,
                orb_preset=orb_preset,
            )

            from astro_analyze.calendar import export_to_csv_string
            csv_content = export_to_csv_string(events)

            # Return CSV as raw content or file path based on preference
            if payload.get("download", False):
                body = csv_content.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            filepath = os.path.join(os.path.dirname(DB_PATH), filename)
            from astro_analyze.calendar import export_to_csv
            export_to_csv(events, filepath)
            _json_response(self, {
                "status": "ok",
                "chart_id": chart_id,
                "events_count": len(events),
                "filepath": filepath,
            })
        except Exception as e:
            _error(self, str(e), 500)

    # --------------------------------------------------------------
    # Backup / Restore endpoints (Phase 8)

    def _handle_backup(self, payload):
        try:
            output_dir = payload.get("output_dir", os.path.dirname(DB_PATH))
            filename = payload.get("filename", f"astro_backup_{_now_iso().replace(':', '-')}.tar.gz")
            from astro_data.backup import backup_database
            output_path = os.path.join(output_dir, filename)
            backup_path = backup_database(DB_PATH, output_path)
            _json_response(self, {
                "status": "ok",
                "backup_path": backup_path,
            })
        except Exception as e:
            _error(self, str(e), 500)

    def _handle_restore(self, payload):
        try:
            backup_path = payload.get("backup_path")
            if not backup_path:
                _error(self, "Missing backup_path")
                return
            from astro_data.backup import restore_database
            result = restore_database(DB_PATH, backup_path)
            _json_response(self, result)
        except Exception as e:
            _error(self, str(e), 500)

# ------------------------------------------------------------------
# Main

def run_server(host="localhost", port=8081):
    # Primary ephemeris path — inside ~/.hermes/ephemeris/ (self-contained, backup-safe)
    # Fallback: /home/xephyr/dev/astrolog/ast78src/ephem/ (original location)
    EPHE_PATH = "/home/xephyr/.hermes/ephemeris"
    if not os.path.isdir(EPHE_PATH) or not os.path.isfile(os.path.join(EPHE_PATH, "se00015s.se1")):
        EPHE_PATH = "/home/xephyr/dev/astrolog/ast78src/ephem/"
    ac_init(EPHE_PATH)
    _migrate_legacy_charts()
    server = HTTPServer((host, port), AstroHandler)
    print(f"Astrology API server listening on http://{host}:{port}")
    print(f"Ephemeris path: {EPHE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        ac_cleanup()
        global _db_conn
        if _db_conn:
            _db_conn.close()
            _db_conn = None


if __name__ == "__main__":
    run_server()
