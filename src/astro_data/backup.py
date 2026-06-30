"""
Backup and restore for astrology tool database (Phase 8).
Python stdlib only: sqlite3, json, tarfile, io, os, datetime.
"""
import io
import json
import os
import sqlite3
import tarfile
from datetime import datetime, timezone


# ------------------------------------------------------------------
# Helpers

def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _get_tables(conn: sqlite3.Connection) -> list[str]:
    """Return list of user-defined table names (excluding sqlite_ internal)."""
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [row[0] for row in cur.fetchall()]


def _dump_table(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Return all rows from table as list of dicts."""
    cur = conn.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in rows]


def _insert_sql(table: str, row: dict) -> str:
    """Generate an INSERT statement for a row dict."""
    cols = []
    vals = []
    for k, v in row.items():
        cols.append(k)
        if v is None:
            vals.append("NULL")
        elif isinstance(v, (int, float)):
            vals.append(str(v))
        else:
            # Escape single quotes
            safe = str(v).replace("'", "''")
            vals.append(f"'{safe}'")
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(vals)});"


# ------------------------------------------------------------------
# SQL dump generation

def _generate_sql_dump(conn: sqlite3.Connection) -> str:
    """Generate a full SQL dump with schema + INSERT statements."""
    lines = []
    lines.append("-- Astrology Tool SQL Backup")
    lines.append(f"-- Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("PRAGMA foreign_keys = OFF;")
    lines.append("")

    tables = _get_tables(conn)
    for table in tables:
        lines.append(f"-- Table: {table}")
        # Schema
        cur = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        row = cur.fetchone()
        if row and row[0]:
            lines.append(row[0] + ";")
        lines.append("")
        # Data
        rows = _dump_table(conn, table)
        for r in rows:
            lines.append(_insert_sql(table, r))
        lines.append("")

    lines.append("PRAGMA foreign_keys = ON;")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------
# JSON export

def _generate_json_export(conn: sqlite3.Connection) -> str:
    """Generate a JSON export of all tables."""
    data = {}
    tables = _get_tables(conn)
    for table in tables:
        data[table] = _dump_table(conn, table)
    payload = {
        "meta": {
            "generator": "astro-tool-backup",
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "tables": data,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------
# Backup

def backup_database(db_path: str, output_path: str) -> str:
    """
    Export SQLite database to a tar.gz containing:
    - .sql dump with INSERT statements
    - .json export for portability

    Returns the path to the created tar.gz file.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        sql_content = _generate_sql_dump(conn)
        json_content = _generate_json_export(conn)
    finally:
        conn.close()

    # Determine output directory and base name
    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.basename(output_path)
    if base_name.endswith(".tar.gz"):
        tar_path = output_path
        stem = base_name[:-7]
    else:
        stem = base_name or f"astro_backup_{_now_str()}"
        tar_path = os.path.join(output_dir, f"{stem}.tar.gz")

    sql_name = f"{stem}.sql"
    json_name = f"{stem}.json"

    # Write tar.gz in memory then to disk
    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode="w:gz") as tar:
        sql_bytes = sql_content.encode("utf-8")
        info = tarfile.TarInfo(name=sql_name)
        info.size = len(sql_bytes)
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        tar.addfile(info, io.BytesIO(sql_bytes))

        json_bytes = json_content.encode("utf-8")
        info2 = tarfile.TarInfo(name=json_name)
        info2.size = len(json_bytes)
        info2.mtime = info.mtime
        tar.addfile(info2, io.BytesIO(json_bytes))

    with open(tar_path, "wb") as f:
        f.write(tar_bytes.getvalue())

    return tar_path


# ------------------------------------------------------------------
# Restore helpers

def _clear_and_restore_sql(conn: sqlite3.Connection, sql_content: str) -> None:
    """Execute SQL dump: drop existing tables, recreate schema, and insert data."""
    conn.execute("PRAGMA foreign_keys = OFF")
    # Drop all existing user tables so CREATE TABLE statements succeed
    existing = _get_tables(conn)
    for table in existing:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()

    # sqlite3 .executescript handles multiple statements well
    conn.executescript(sql_content)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _restore_json(conn: sqlite3.Connection, json_content: str) -> None:
    """Restore from JSON export: clear tables and insert rows."""
    payload = json.loads(json_content)
    tables_data = payload.get("tables", {})

    conn.execute("PRAGMA foreign_keys = OFF")
    existing = _get_tables(conn)
    # Clear existing data
    for table in existing:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()

    # Insert rows from JSON
    for table, rows in tables_data.items():
        if not rows:
            continue
        # Determine columns from first row
        cols = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        for row in rows:
            vals = [row.get(c) for c in cols]
            conn.execute(sql, vals)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def restore_database(db_path: str, backup_path: str) -> dict:
    """
    Restore from backup:
    - If backup_path ends in .sql — execute SQL statements
    - If backup_path ends in .json — parse and recreate tables
    - If backup_path ends in .tar.gz — extract and restore both formats

    Returns {"status": "ok", "tables_restored": N, "format": "..."}
    """
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        if backup_path.endswith(".tar.gz"):
            return _restore_tar(conn, backup_path)
        elif backup_path.endswith(".sql"):
            with open(backup_path, "r", encoding="utf-8") as f:
                sql = f.read()
            _clear_and_restore_sql(conn, sql)
            tables = _get_tables(conn)
            return {"status": "ok", "tables_restored": len(tables), "format": "sql"}
        elif backup_path.endswith(".json"):
            with open(backup_path, "r", encoding="utf-8") as f:
                json_content = f.read()
            _restore_json(conn, json_content)
            tables = _get_tables(conn)
            return {"status": "ok", "tables_restored": len(tables), "format": "json"}
        else:
            raise ValueError("Unsupported backup format. Use .sql, .json, or .tar.gz")
    finally:
        conn.close()


def _restore_tar(conn: sqlite3.Connection, tar_path: str) -> dict:
    """Extract tar.gz and restore SQL first, then JSON as verification."""
    sql_content = None
    json_content = None
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith(".sql"):
                sql_content = tar.extractfile(member).read().decode("utf-8")
            elif member.name.endswith(".json"):
                json_content = tar.extractfile(member).read().decode("utf-8")

    if sql_content:
        _clear_and_restore_sql(conn, sql_content)
    elif json_content:
        _restore_json(conn, json_content)
    else:
        raise ValueError("No .sql or .json file found inside tar.gz")

    tables = _get_tables(conn)
    return {"status": "ok", "tables_restored": len(tables), "format": "tar.gz"}
