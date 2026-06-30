#!/usr/bin/env python3
"""
import_corpus_json.py — Load a corpus JSON backup into astro.db.

Usage:
    cd ~/astro
    python3 scripts/import_corpus_json.py [path/to/Interpretation_Corpus.json]

Resumable: skips duplicate (domain, atom_key) pairs silently.
Stdlib only; no external dependencies beyond the astro project modules.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

_ASTRO_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_ASTRO_SRC))

from astro_data import db


def main():
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
    else:
        json_path = _ASTRO_SRC / "astro_api" / "Interpretation_Corpus.json"

    db_path = Path(os.environ.get("ASTRO_DB_PATH", os.path.expanduser("~/second-brain/data/astro.db")))

    if not json_path.exists():
        print(f"ERROR: JSON backup not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading corpus from: {json_path}")
    print(f"Target database:    {db_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        print("ERROR: JSON root must be an array of corpus entries.", file=sys.stderr)
        sys.exit(1)

    conn = db.init_db(str(db_path))

    total = len(entries)
    inserted = 0
    skipped = 0
    failed = 0

    for entry in entries:
        domain = entry.get("domain")
        atom_key = entry.get("atom_key")
        text = entry.get("text")
        source = entry.get("source", "llm")
        model = entry.get("model")
        tags = entry.get("tags")

        if not domain or not atom_key or not text:
            print(f"  SKIP malformed entry: {entry}", file=sys.stderr)
            failed += 1
            continue

        try:
            ok = db.add_corpus_entry(
                conn,
                domain=domain,
                atom_key=atom_key,
                text=text.strip(),
                tags=tags if isinstance(tags, list) else None,
                source=source,
                model=model,
            )
            if ok:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.Error as e:
            print(f"  ERROR inserting {domain}/{atom_key}: {e}", file=sys.stderr)
            failed += 1

    counts = db.count_corpus_entries(conn)
    conn.close()

    print("")
    print(f"Total entries in backup: {total}")
    print(f"Inserted:              {inserted}")
    print(f"Skipped (duplicates):  {skipped}")
    print(f"Failed / malformed:    {failed}")
    print("")
    print("Final corpus counts per domain:")
    for domain, count in sorted(counts.items()):
        print(f"  {domain}: {count}")


if __name__ == "__main__":
    main()
