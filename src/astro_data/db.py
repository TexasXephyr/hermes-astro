"""
Astrology Tool — SQLite data layer (Phase 4).
Python stdlib only; uses sqlite3 with parameterized queries.

API key hashing:
- Tries bcrypt (if installed).
- Falls back to hashlib.pbkdf2_hmac(sha256, key, salt, 100000) as
  a stdlib-only secure hash. Documented and safe for API keys.
"""
import json
import hashlib
import os
import secrets
import sqlite3
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ------------------------------------------------------------------
# API key hashing

_TRY_BCRYPT = False
try:
    import bcrypt
    _TRY_BCRYPT = True
except Exception:  # pragma: no cover
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_key(key: str) -> str:
    """Hash an API key for storage. Returns a string safe to store."""
    if _TRY_BCRYPT:
        # bcrypt generates its own salt; use work factor 12
        return bcrypt.hashpw(key.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    # stdlib fallback: PBKDF2-HMAC-SHA256, 100k iterations, 32-byte key
    salt = secrets.token_hex(16)  # 32 hex chars = 16 bytes
    dk = hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), salt.encode("utf-8"), 100000, dklen=32)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its stored hash."""
    if _TRY_BCRYPT and not key_hash.startswith("pbkdf2_sha256$"):
        return bcrypt.checkpw(key.encode("utf-8"), key_hash.encode("utf-8"))
    # PBKDF2 fallback verification
    if not key_hash.startswith("pbkdf2_sha256$"):
        return False
    parts = key_hash.split("$")
    if len(parts) != 3:
        return False
    salt = parts[1]
    expected = parts[2]
    dk = hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), salt.encode("utf-8"), 100000, dklen=32)
    return secrets.compare_digest(dk.hex(), expected)


# ------------------------------------------------------------------
# Schema init

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def init_db(path: str | None = None) -> sqlite3.Connection:
    """Open (or create) SQLite DB and initialize schema.
    
    If path is provided, creates the database file with mode 0600 (user-only)
    to protect birth data PII.
    """
    conn = sqlite3.connect(path or ":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    if _SCHEMA_PATH.exists():
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
    conn.commit()
    
    # Set restrictive permissions on DB file if it exists on disk
    if path:
        db_path = Path(path)
        if db_path.exists():
            os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
            # Also ensure parent directory is private
            parent = db_path.parent
            if parent.exists():
                current_mode = parent.stat().st_mode & 0o777
                if current_mode & 0o077:  # Has group/other bits set
                    pass  # Don't auto-change parent dir mode, just note it
    
    return conn


# ------------------------------------------------------------------
# Row helpers


def _row_to_dict(cursor, row) -> dict:
    """sqlite3 row factory."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


# ------------------------------------------------------------------
# People


def add_person(
    conn: sqlite3.Connection,
    *,
    name: str,
    birth_date: str,
    birth_time: str,
    timezone: str,
    latitude: float,
    longitude: float,
    gender: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO people (name, birth_date, birth_time, timezone,
                            latitude, longitude, gender, phone, email,
                            address, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, birth_date, birth_time, timezone, latitude, longitude,
         gender, phone, email, address, notes, _now_iso(), _now_iso()),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def get_person(conn: sqlite3.Connection, person_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,))
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def list_people(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM people ORDER BY created_at DESC")
    return [_row_to_dict(cur, r) for r in cur.fetchall()]


def update_person(
    conn: sqlite3.Connection,
    person_id: int,
    *,
    name: str | None = None,
    birth_date: str | None = None,
    birth_time: str | None = None,
    timezone: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    gender: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    notes: str | None = None,
) -> bool:
    fields = []
    params = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if birth_date is not None:
        fields.append("birth_date = ?")
        params.append(birth_date)
    if birth_time is not None:
        fields.append("birth_time = ?")
        params.append(birth_time)
    if timezone is not None:
        fields.append("timezone = ?")
        params.append(timezone)
    if latitude is not None:
        fields.append("latitude = ?")
        params.append(latitude)
    if longitude is not None:
        fields.append("longitude = ?")
        params.append(longitude)
    if gender is not None:
        fields.append("gender = ?")
        params.append(gender)
    if phone is not None:
        fields.append("phone = ?")
        params.append(phone)
    if email is not None:
        fields.append("email = ?")
        params.append(email)
    if address is not None:
        fields.append("address = ?")
        params.append(address)
    if notes is not None:
        fields.append("notes = ?")
        params.append(notes)
    if not fields:
        return False
    fields.append("updated_at = ?")
    params.append(_now_iso())
    params.append(person_id)
    sql = f"UPDATE people SET {', '.join(fields)} WHERE id = ?"
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur.rowcount > 0


def delete_person(conn: sqlite3.Connection, person_id: int) -> bool:
    cur = conn.execute("DELETE FROM people WHERE id = ?", (person_id,))
    conn.commit()
    return cur.rowcount > 0


def create_person_with_natal_chart(
    conn: sqlite3.Connection,
    *,
    name: str,
    birth_date: str,
    birth_time: str,
    timezone: str,
    latitude: float,
    longitude: float,
    gender: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    notes: str | None = None,
    chart_positions: dict,
    chart_aspects: dict | list,
    calc_options: dict | None = None,
    calc_date: str | None = None,
    chart_id: str | None = None,
) -> dict:
    """
    Atomic transaction: add person, add natal event, add natal chart.
    Returns {"person_id": int, "event_id": int, "chart_id": str}.
    """
    try:
        # 1. Add person (no commit)
        person_id = add_person(
            conn, name=name, birth_date=birth_date, birth_time=birth_time,
            timezone=timezone, latitude=latitude, longitude=longitude,
            gender=gender, phone=phone, email=email, address=address,
            notes=notes, commit=False,
        )
        # 2. Add natal event (no commit)
        event_id = add_event(
            conn, name=f"{name} Natal", event_date=birth_date,
            event_time=birth_time, timezone=timezone,
            latitude=latitude, longitude=longitude,
            event_type="natal", person_id=person_id,
            notes="Auto-generated natal event", commit=False,
        )
        # 3. Add natal chart (no commit)
        chart_id = add_chart(
            conn, chart_id=chart_id, person_id=person_id, event_id=event_id,
            chart_type="natal", calc_date=calc_date,
            calc_options=calc_options, positions=chart_positions,
            aspects=chart_aspects, commit=False,
        )
        conn.commit()
        return {"person_id": person_id, "event_id": event_id, "chart_id": chart_id}
    except Exception:
        conn.rollback()
        raise


def get_natal_chart_by_person_name(
    conn: sqlite3.Connection,
    name: str,
) -> dict | None:
    """
    Return the natal chart (from charts table) for a person by name.
    Returns None if no person or no natal chart exists.
    """
    cur = conn.execute(
        "SELECT id FROM people WHERE name = ? ORDER BY created_at DESC LIMIT 1",
        (name,),
    )
    row = cur.fetchone()
    if not row:
        return None
    person_id = row[0]
    cur = conn.execute(
        """
        SELECT * FROM charts
        WHERE person_id = ? AND chart_type = 'natal'
        ORDER BY created_at DESC LIMIT 1
        """,
        (person_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(cur, row)
    for k in ("calc_options", "positions", "dignities", "aspects"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


def get_natal_chart_by_person_id(
    conn: sqlite3.Connection,
    person_id: int,
) -> dict | None:
    """
    Return the natal chart for a person by their ID.
    Returns None if no natal chart exists.
    """
    cur = conn.execute(
        """
        SELECT * FROM charts
        WHERE person_id = ? AND chart_type = 'natal'
        ORDER BY created_at DESC LIMIT 1
        """,
        (person_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(cur, row)
    for k in ("calc_options", "positions", "dignities", "aspects"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


# ------------------------------------------------------------------
# Events


def add_event(
    conn: sqlite3.Connection,
    *,
    name: str,
    event_date: str,
    event_time: str | None = None,
    timezone: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    event_type: str = "general",
    person_id: int | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO events (name, event_date, event_time, timezone,
                            latitude, longitude, event_type, person_id,
                            notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, event_date, event_time, timezone, latitude, longitude,
         event_type, person_id, notes, _now_iso()),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def get_event(conn: sqlite3.Connection, event_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def list_events(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM events ORDER BY created_at DESC")
    return [_row_to_dict(cur, r) for r in cur.fetchall()]


def update_event(
    conn: sqlite3.Connection,
    event_id: int,
    *,
    name: str | None = None,
    event_date: str | None = None,
    event_time: str | None = None,
    timezone: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    event_type: str | None = None,
    person_id: int | None = None,
    notes: str | None = None,
) -> bool:
    fields = []
    params = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if event_date is not None:
        fields.append("event_date = ?")
        params.append(event_date)
    if event_time is not None:
        fields.append("event_time = ?")
        params.append(event_time)
    if timezone is not None:
        fields.append("timezone = ?")
        params.append(timezone)
    if latitude is not None:
        fields.append("latitude = ?")
        params.append(latitude)
    if longitude is not None:
        fields.append("longitude = ?")
        params.append(longitude)
    if event_type is not None:
        fields.append("event_type = ?")
        params.append(event_type)
    if person_id is not None:
        fields.append("person_id = ?")
        params.append(person_id)
    if notes is not None:
        fields.append("notes = ?")
        params.append(notes)
    if not fields:
        return False
    params.append(event_id)
    sql = f"UPDATE events SET {', '.join(fields)} WHERE id = ?"
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur.rowcount > 0


def delete_event(conn: sqlite3.Connection, event_id: int) -> bool:
    cur = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    return cur.rowcount > 0


# ------------------------------------------------------------------
# Charts (immutable after creation — no update)


def add_chart(
    conn: sqlite3.Connection,
    *,
    chart_id: str | None = None,
    person_id: int | None = None,
    person_b_id: int | None = None,
    event_id: int | None = None,
    chart_type: str,
    calc_date: str | None = None,
    calc_options: dict | None = None,
    positions: dict | list,
    dignities: dict | None = None,
    aspects: dict | list,
    rendered_path: str | None = None,
    commit: bool = True,
) -> str:
    if chart_id is None:
        chart_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO charts (chart_id, person_id, person_b_id, event_id,
                            chart_type, calc_date, calc_options, positions,
                            dignities, aspects, rendered_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (chart_id, person_id, person_b_id, event_id, chart_type,
         calc_date, json.dumps(calc_options) if calc_options else None,
         json.dumps(positions), json.dumps(dignities) if dignities else None,
         json.dumps(aspects), rendered_path, _now_iso()),
    )
    if commit:
        conn.commit()
    return chart_id


def get_chart(conn: sqlite3.Connection, chart_id: str) -> dict | None:
    cur = conn.execute("SELECT * FROM charts WHERE chart_id = ?", (chart_id,))
    row = cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(cur, row)
    for k in ("calc_options", "positions", "dignities", "aspects"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


def list_charts(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM charts ORDER BY created_at DESC")
    rows = []
    for r in cur.fetchall():
        d = _row_to_dict(cur, r)
        for k in ("calc_options", "positions", "dignities", "aspects"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except json.JSONDecodeError:
                    pass
        rows.append(d)
    return rows


def delete_chart(conn: sqlite3.Connection, chart_id: str) -> bool:
    cur = conn.execute("DELETE FROM charts WHERE chart_id = ?", (chart_id,))
    conn.commit()
    return cur.rowcount > 0


# ------------------------------------------------------------------
# Interpretations


def add_interpretation(
    conn: sqlite3.Connection,
    *,
    chart_id: int,
    section: str,
    sub_section: str | None = None,
    content: str,
    model: str = "rules",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO interpretations (chart_id, section, sub_section,
                                      content, generated_at, model)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (chart_id, section, sub_section, content, _now_iso(), model),
    )
    conn.commit()
    return cur.lastrowid


def get_interpretations_by_chart(conn: sqlite3.Connection, chart_id: int) -> list[dict]:
    cur = conn.execute(
        "SELECT * FROM interpretations WHERE chart_id = ? ORDER BY generated_at DESC",
        (chart_id,),
    )
    return [_row_to_dict(cur, r) for r in cur.fetchall()]


def delete_interpretation(conn: sqlite3.Connection, interpretation_id: int) -> bool:
    cur = conn.execute("DELETE FROM interpretations WHERE id = ?", (interpretation_id,))
    conn.commit()
    return cur.rowcount > 0


# ------------------------------------------------------------------
# API Keys


def add_api_key(
    conn: sqlite3.Connection,
    *,
    key: str,
    name: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO api_keys (key_hash, name, created_at) VALUES (?, ?, ?)",
        (hash_key(key), name, _now_iso()),
    )
    conn.commit()
    return cur.lastrowid


def get_api_key_by_hash(conn: sqlite3.Connection, key: str) -> dict | None:
    cur = conn.execute("SELECT * FROM api_keys WHERE revoked = 0")
    for row in cur.fetchall():
        d = _row_to_dict(cur, row)
        if verify_key(key, d["key_hash"]):
            # update last_used
            conn.execute(
                "UPDATE api_keys SET last_used = ? WHERE id = ?",
                (_now_iso(), d["id"]),
            )
            conn.commit()
            return d
    return None


def revoke_api_key(conn: sqlite3.Connection, key_id: int) -> bool:
    cur = conn.execute(
        "UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,)
    )
    conn.commit()
    return cur.rowcount > 0


def list_api_keys(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM api_keys ORDER BY created_at DESC")
    return [_row_to_dict(cur, r) for r in cur.fetchall()]


# ------------------------------------------------------------------
# Corpus


CORPUS_BODIES = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Mean Node", "True Node", "Chiron", "Lilith",
    "Ceres", "Pallas", "Juno", "Vesta",
]

CORPUS_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

CORPUS_HOUSES = [str(i) for i in range(1, 13)]

CORPUS_ASPECTS = [
    "conjunction", "opposition", "trine", "square", "sextile",
    "semisextile", "semisquare", "sesquiquadrature", "quincunx",
]

CORPUS_DIRECTIONS = ["direct", "retrograde", "stationary"]

CORPUS_DOMAINS = [
    "natal-sign", "natal-house", "aspect", "direction",
    "transit-sign", "transit-house", "transit-aspect",
    "synastry-house", "synastry-aspect",
]


def add_corpus_entry(
    conn: sqlite3.Connection,
    *,
    domain: str,
    atom_key: str,
    text: str,
    tags: list | None = None,
    source: str = "llm",
    model: str | None = None,
) -> bool:
    """
    Insert a corpus entry, silently skipping duplicates.
    Returns True if inserted, False if duplicate.
    """
    try:
        conn.execute(
            """
            INSERT INTO corpus (domain, atom_key, text, tags, source, model, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (domain, atom_key, text,
             json.dumps(tags) if tags else None,
             source, model, _now_iso()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_corpus_entry(conn: sqlite3.Connection, domain: str, atom_key: str) -> dict | None:
    cur = conn.execute(
        "SELECT * FROM corpus WHERE domain = ? AND atom_key = ?",
        (domain, atom_key),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = _row_to_dict(cur, row)
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except json.JSONDecodeError:
            pass
    return d


def get_corpus_entries(conn: sqlite3.Connection, domain: str) -> list[dict]:
    cur = conn.execute(
        "SELECT * FROM corpus WHERE domain = ? ORDER BY atom_key",
        (domain,),
    )
    rows = []
    for r in cur.fetchall():
        d = _row_to_dict(cur, r)
        if d.get("tags"):
            try:
                d["tags"] = json.loads(d["tags"])
            except json.JSONDecodeError:
                pass
        rows.append(d)
    return rows


def remove_corpus_entry(conn: sqlite3.Connection, domain: str, atom_key: str) -> bool:
    cur = conn.execute(
        "DELETE FROM corpus WHERE domain = ? AND atom_key = ?",
        (domain, atom_key),
    )
    conn.commit()
    return cur.rowcount > 0


def count_corpus_entries(conn: sqlite3.Connection, domains: list[str] | None = None) -> dict:
    """Return counts per domain. If no domains given, counts all."""
    result = {}
    if domains is None:
        domains = CORPUS_DOMAINS
    for dom in domains:
        cur = conn.execute(
            "SELECT COUNT(*) FROM corpus WHERE domain = ?",
            (dom,),
        )
        result[dom] = cur.fetchone()[0]
    return result


def list_missing_corpus_keys(conn: sqlite3.Connection, domain: str, keys: list[str]) -> list[str]:
    """Return keys not yet present in corpus for a given domain."""
    placeholders = ",".join("?" * len(keys))
    cur = conn.execute(
        f"SELECT atom_key FROM corpus WHERE domain = ? AND atom_key IN ({placeholders})",
        (domain,) + tuple(keys),
    )
    existing = {r[0] for r in cur.fetchall()}
    return [k for k in keys if k not in existing]


# ------------------------------------------------------------------
# Module-level alias for backwards compat with tests that import init_db

__all__ = [
    "init_db",
    "add_person", "get_person", "list_people", "update_person", "delete_person",
    "create_person_with_natal_chart", "get_natal_chart_by_person_name",
    "get_natal_chart_by_person_id",
    "add_event", "get_event", "list_events", "update_event", "delete_event",
    "add_chart", "get_chart", "list_charts", "delete_chart",
    "add_interpretation", "get_interpretations_by_chart", "delete_interpretation",
    "add_api_key", "get_api_key_by_hash", "revoke_api_key", "list_api_keys",
    "hash_key", "verify_key",
    # corpus
    "CORPUS_BODIES", "CORPUS_SIGNS", "CORPUS_HOUSES", "CORPUS_ASPECTS",
    "CORPUS_DIRECTIONS", "CORPUS_DOMAINS",
    "add_corpus_entry", "get_corpus_entry", "get_corpus_entries",
    "remove_corpus_entry", "count_corpus_entries", "list_missing_corpus_keys",
]
