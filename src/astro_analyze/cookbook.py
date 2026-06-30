"""
Atomic cookbook enrichment layer.

Attaches pre-computed atomic interpretations to chart / transit / synastry responses.
All lookups are by composite key into the corpus table.

Usage:
    from astro_analyze.cookbook import enrich_chart, enrich_transit, enrich_synastry
    cookbook = enrich_chart(conn, chart_data)
"""
import json
import sqlite3

from astro_data import db

# ------------------------------------------------------------------
# Key builders (must match seed_corpus.py exactly)


def _sign_key(body: str, sign: str) -> str:
    return f"{body}-{sign}"


def _house_key(body: str, house: int | str) -> str:
    return f"{body}-{house}"


def _direction_key(body: str, retrograde: bool, speed: float | None = None) -> str:
    """
    retrograde=True  -> {body}-retrograde
    retrograde=False -> check if speed near zero for stationary
    """
    if retrograde:
        return f"{body}-retrograde"
    # Stationary if speed is very close to zero (±0.05°/day heuristic)
    if speed is not None and abs(speed) < 0.05:
        return f"{body}-stationary"
    return f"{body}-direct"


def _aspect_key(body: str, aspect_name: str) -> str:
    return f"{body}-{aspect_name.lower()}"


def _transit_sign_key(transit_body: str, sign: str) -> str:
    return f"{transit_body}-{sign}"


def _transit_house_key(transit_body: str, house: int | str) -> str:
    return f"{transit_body}-{house}"


def _transit_aspect_key(transit_body: str, aspect_name: str) -> str:
    return f"{transit_body}-{aspect_name.lower()}"


def _synastry_house_key(body_a: str, house_b: int | str) -> str:
    return f"{body_a}-{house_b}"


def _synastry_aspect_key(body_a: str, aspect_name: str) -> str:
    return f"{body_a}-{aspect_name.lower()}"


# ------------------------------------------------------------------
# Lookup helper


def _lookup(conn: sqlite3.Connection, domain: str, atom_key: str) -> dict | None:
    """Fetch a single corpus entry; return dict with key and text, or None."""
    row = db.get_corpus_entry(conn, domain, atom_key)
    if not row:
        return None
    return {"domain": domain, "atom_key": atom_key, "text": row["text"]}


# ------------------------------------------------------------------
# Enrichment functions


def enrich_chart(
    conn: sqlite3.Connection,
    chart_data: dict,
) -> dict:
    """
    Build a cookbook dict for a natal chart.

    chart_data expects keys: bodies (list), houses (list), aspects (list, optional)
    Each body has: name, sign, house, retrograde (bool), speed (float)
    Each aspect has: body_a (or body), body_b, aspect_name
    """
    bodies = chart_data.get("bodies", [])
    aspects = chart_data.get("aspects", [])

    natal_signs = []
    natal_houses = []
    directions = []
    natal_aspects = []

    for b in bodies:
        name = b.get("name", "")
        if not name:
            continue

        # sign
        sign = b.get("sign", "")
        if isinstance(sign, int):
            # convert sign index to name if needed
            sign_names = db.CORPUS_SIGNS
            sign = sign_names[sign] if 0 <= sign < len(sign_names) else str(sign)
        if sign:
            entry = _lookup(conn, "natal-sign", _sign_key(name, sign))
            if entry:
                natal_signs.append({"body": name, "sign": sign, **entry})

        # house
        house = b.get("house")
        if house:
            entry = _lookup(conn, "natal-house", _house_key(name, house))
            if entry:
                natal_houses.append({"body": name, "house": house, **entry})

        # direction
        retrograde = b.get("retrograde", False)
        speed = b.get("speed")
        entry = _lookup(conn, "direction", _direction_key(name, retrograde, speed))
        if entry:
            directions.append({"body": name, "state": entry["atom_key"].split("-", 1)[1], **entry})

    for a in aspects:
        # aspects may have body_a/body_b or a single body key
        # natal aspect list: currently stored as {"body_a": X, "body_b": Y, "aspect_name": Z}
        ba = a.get("body_a") or a.get("body")
        bb = a.get("body_b")
        aspect_name = a.get("aspect_name", "")
        if not ba or not aspect_name:
            continue
        # For natal aspects, lookup for body_a
        entry = _lookup(conn, "aspect", _aspect_key(ba, aspect_name))
        if entry:
            natal_aspects.append({
                "body": ba,
                "aspect": aspect_name,
                "orb": a.get("orb"),
                "applying": a.get("applying"),
                **entry,
            })

    cookbook = {}
    if natal_signs:
        cookbook["natal_signs"] = natal_signs
    if natal_houses:
        cookbook["natal_houses"] = natal_houses
    if natal_aspects:
        cookbook["natal_aspects"] = natal_aspects
    if directions:
        cookbook["directions"] = directions

    return cookbook


def enrich_transit(
    conn: sqlite3.Connection,
    natal_chart: dict,
    transit_data: dict,
    cross_aspects: list,
) -> dict:
    """
    Build cookbook for a transit snapshot.

    transit_data expects: bodies (list) — the transiting positions
    natal_chart expects: bodies (list) — natal positions (for house overlay)
    cross_aspects expects: list of {"natal_body": ..., "transit_body": ..., "aspect_name": ...}
    """
    transit_bodies = transit_data.get("bodies", [])
    natal_bodies = natal_chart.get("bodies", [])

    # Build natal house lookup for each transit body
    natal_houses = {b["name"]: b["house"] for b in natal_bodies if b.get("house")}

    transit_signs = []
    transit_houses = []
    transit_aspects = []

    for tb in transit_bodies:
        name = tb.get("name", "")
        if not name:
            continue

        # transit-sign
        sign = tb.get("sign", "")
        if isinstance(sign, int):
            sign_names = db.CORPUS_SIGNS
            sign = sign_names[sign] if 0 <= sign < len(sign_names) else str(sign)
        if sign:
            entry = _lookup(conn, "transit-sign", _transit_sign_key(name, sign))
            if entry:
                transit_signs.append({"body": name, "sign": sign, **entry})

        # transit-house (which natal house is this transiting body in?)
        house = natal_houses.get(name)
        if house:
            entry = _lookup(conn, "transit-house", _transit_house_key(name, house))
            if entry:
                transit_houses.append({"body": name, "house": house, **entry})

    for asp in cross_aspects:
        transit_body = asp.get("transit_body", "")
        aspect_name = asp.get("aspect_name", "")
        if not transit_body or not aspect_name:
            continue
        entry = _lookup(conn, "transit-aspect", _transit_aspect_key(transit_body, aspect_name))
        if entry:
            transit_aspects.append({
                "transit_body": transit_body,
                "natal_body": asp.get("natal_body"),
                "aspect": aspect_name,
                "orb": asp.get("orb"),
                "applying": asp.get("applying"),
                **entry,
            })

    cookbook = {}
    if transit_signs:
        cookbook["transit_signs"] = transit_signs
    if transit_houses:
        cookbook["transit_houses"] = transit_houses
    if transit_aspects:
        cookbook["transit_aspects"] = transit_aspects
    return cookbook


def enrich_synastry(
    conn: sqlite3.Connection,
    chart_a_bodies: list,
    chart_b_bodies: list,
    cross_aspects: list,
) -> dict:
    """
    Build cookbook for synastry analysis.

    chart_a_bodies: person A's natal bodies (used for synastry-houses: body_a in body_b's houses)
    chart_b_bodies: person B's natal bodies (used for house mapping)
    cross_aspects: list of {"body_a": ..., "body_b": ..., "aspect_name": ...}
    """
    # Person B's houses, indexed by body
    b_houses = {b["name"]: b["house"] for b in chart_b_bodies if b.get("house")}

    synastry_houses = []
    synastry_aspects = []

    for ba in chart_a_bodies:
        name_a = ba.get("name", "")
        if not name_a:
            continue
        house_b = b_houses.get(name_a)
        if house_b:
            entry = _lookup(conn, "synastry-house", _synastry_house_key(name_a, house_b))
            if entry:
                synastry_houses.append({
                    "body_a": name_a,
                    "house_b": house_b,
                    **entry,
                })

    for asp in cross_aspects:
        body_a = asp.get("body_a", "")
        aspect_name = asp.get("aspect_name", "")
        if not body_a or not aspect_name:
            continue
        entry = _lookup(conn, "synastry-aspect", _synastry_aspect_key(body_a, aspect_name))
        if entry:
            synastry_aspects.append({
                "body_a": body_a,
                "body_b": asp.get("body_b"),
                "aspect": aspect_name,
                "orb": asp.get("orb"),
                **entry,
            })

    cookbook = {}
    if synastry_houses:
        cookbook["synastry_houses"] = synastry_houses
    if synastry_aspects:
        cookbook["synastry_aspects"] = synastry_aspects
    return cookbook
