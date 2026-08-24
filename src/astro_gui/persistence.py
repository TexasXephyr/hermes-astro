"""persistence.py — Document-set persistence for the astrology GUI.

A "document set" is the collection of open tabs with their display types,
zoom levels, date settings, and filters, tied to a specific person. Sets
are stored in the library store (~/.cache/astro/library.db) in the
`document_sets` table, using the same 0600 file-mode convention as
AstroClient (cache dir 0700, umask 077 on first create).

Model:
- Each person has exactly one "current" set (reserved name `__auto__`,
  is_default=1) that is auto-saved on person switch and on window close,
  and auto-restored on person switch and app startup.
- Named snapshots (File -> Save Document Set As...) are stored with
  is_default=0 and can be loaded via File -> Load Document Set....
- The last active person is tracked in the `app_state` table so the app
  can restore the previous session on startup.

A partial unique index enforces one default row per person.
"""
import json
import os
import sqlite3
from pathlib import Path


class DocumentSetStore:
    """SQLite-backed store for document sets and app state."""

    AUTO_NAME = "__auto__"
    _RESERVED_PREFIX = "__"
    _LAST_ACTIVE_KEY = "last_active_person"

    def __init__(self, db_path=None):
        self._db_path = Path(db_path) if db_path else self._default_db_path()
        self._init_db()

    # ------------------------------------------------------------------
    # Path / schema
    # ------------------------------------------------------------------
    @staticmethod
    def _default_db_path() -> Path:
        """~/.cache/astro/library.db with the AstroClient 0600 convention."""
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

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_sets (
                    id INTEGER PRIMARY KEY,
                    person_id INTEGER,
                    name TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # One default (current) set per person.
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_document_sets_default
                ON document_sets(person_id) WHERE is_default = 1
                """
            )
            # Named snapshots are unique per (person_id, name).
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_document_sets_name
                ON document_sets(person_id, name)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Document sets
    # ------------------------------------------------------------------
    def save_set(self, person_id: int, name: str, config: dict,
                 is_default: bool = False) -> None:
        """Upsert a document set for a person by (person_id, name).

        When is_default=True the row becomes the person's single default
        (current) set; any previous default row is replaced.
        """
        config_json = json.dumps(config, default=str)
        with self._connect() as conn:
            if is_default:
                conn.execute(
                    """
                    INSERT INTO document_sets (person_id, name, config_json, is_default)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(person_id) WHERE is_default = 1
                    DO UPDATE SET name=excluded.name, config_json=excluded.config_json,
                                  updated_at=CURRENT_TIMESTAMP
                    """,
                    (person_id, name, config_json),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO document_sets (person_id, name, config_json, is_default)
                    VALUES (?, ?, ?, 0)
                    ON CONFLICT(person_id, name) DO UPDATE SET
                        config_json=excluded.config_json,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (person_id, name, config_json),
                )
            conn.commit()

    def save_default(self, person_id: int, config: dict) -> None:
        """Save the person's current/default set (reserved auto slot)."""
        self.save_set(person_id, self.AUTO_NAME, config, is_default=True)

    def load_set(self, person_id: int, name: str) -> dict | None:
        """Return a named set's config dict, or None."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT config_json FROM document_sets WHERE person_id = ? AND name = ?",
                (person_id, name),
            )
            row = cur.fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, ValueError):
            return None

    def load_default(self, person_id: int) -> dict | None:
        """Return the person's current/default set config, or None."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT config_json FROM document_sets WHERE person_id = ? AND is_default = 1",
                (person_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, ValueError):
            return None

    def list_sets(self, person_id: int) -> list[dict]:
        """List named snapshots (excludes the reserved auto/current set)."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id, name, is_default, updated_at
                FROM document_sets
                WHERE person_id = ? AND name NOT GLOB '__*'
                ORDER BY updated_at DESC, id DESC
                """,
                (person_id,),
            )
            rows = cur.fetchall()
        return [
            {"id": r[0], "name": r[1], "is_default": bool(r[2]), "updated_at": r[3]}
            for r in rows
        ]

    def delete_set(self, set_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM document_sets WHERE id = ?", (set_id,))
            conn.commit()

    # ------------------------------------------------------------------
    # App state (last active person)
    # ------------------------------------------------------------------
    def save_last_active(self, person_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (self._LAST_ACTIVE_KEY, str(person_id)),
            )
            conn.commit()

    def load_last_active(self) -> int | None:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT value FROM app_state WHERE key = ?",
                (self._LAST_ACTIVE_KEY,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return None
