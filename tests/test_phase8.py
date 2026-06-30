#!/usr/bin/env python3
"""
Phase 8 Tests: Calendar export (ICS/CSV) + Backup/Restore.
Run with: python3 tests/test_phase8.py -v
"""
import json
import os
import sqlite3
import sys
import tarfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from astro_analyze.calendar import export_to_ics, export_to_csv, export_to_csv_string
from astro_data.backup import backup_database, restore_database, _get_tables, _dump_table


# ------------------------------------------------------------------
# Calendar export tests

class TestICSExport(unittest.TestCase):
    def test_export_creates_valid_ics(self):
        events = [
            {
                "date": "2026-05-20",
                "transiting_body": "Saturn",
                "natal_body": "Sun",
                "aspect": "conjunction",
                "orb": 0.5,
                "applying": True,
                "angle": 0.0,
            },
            {
                "date": "2026-05-21",
                "transiting_body": "Uranus",
                "natal_body": "Moon",
                "aspect": "opposition",
                "orb": 1.2,
                "applying": False,
                "angle": 178.5,
            },
        ]
        path = "/tmp/test_transits.ics"
        if os.path.exists(path):
            os.remove(path)
        export_to_ics(events, path)
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("BEGIN:VCALENDAR", content)
        self.assertIn("VERSION:2.0", content)
        self.assertIn("PRODID:-//Astrology Tool//EN", content)
        self.assertIn("BEGIN:VEVENT", content)
        self.assertIn("END:VEVENT", content)
        self.assertIn("END:VCALENDAR", content)
        self.assertIn("DTSTART;VALUE=DATE:20260520", content)
        self.assertIn("SUMMARY:Saturn conjunction natal Sun", content)
        self.assertIn("UID:saturn-sun-2026-05-20-0@astro-tool", content)
        self.assertIn("TRANSP:TRANSPARENT", content)
        os.remove(path)

    def test_empty_events(self):
        path = "/tmp/test_empty.ics"
        if os.path.exists(path):
            os.remove(path)
        export_to_ics([], path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("BEGIN:VCALENDAR", content)
        self.assertIn("END:VCALENDAR", content)
        self.assertNotIn("BEGIN:VEVENT", content)
        os.remove(path)


class TestCSVExport(unittest.TestCase):
    def test_export_csv_matches_events(self):
        events = [
            {
                "date": "2026-05-20",
                "transiting_body": "Saturn",
                "natal_body": "Sun",
                "aspect": "conjunction",
                "orb": 0.5,
                "applying": True,
            },
            {
                "date": "2026-05-21",
                "transiting_body": "Uranus",
                "natal_body": "Moon",
                "aspect": "opposition",
                "orb": 1.2,
                "applying": False,
            },
        ]
        path = "/tmp/test_transits.csv"
        if os.path.exists(path):
            os.remove(path)
        export_to_csv(events, path)
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
        self.assertEqual(lines[0], "date,transiting_body,natal_body,aspect,orb,applying")
        self.assertEqual(lines[1], "2026-05-20,Saturn,Sun,conjunction,0.5,1")
        self.assertEqual(lines[2], "2026-05-21,Uranus,Moon,opposition,1.2,0")
        os.remove(path)

    def test_csv_string(self):
        events = [
            {
                "date": "2026-05-20",
                "transiting_body": "Saturn",
                "natal_body": "Sun",
                "aspect": "conjunction",
                "orb": 0.5,
                "applying": True,
            },
        ]
        s = export_to_csv_string(events)
        self.assertIn("date,transiting_body,natal_body,aspect,orb,applying", s)
        self.assertIn("2026-05-20,Saturn,Sun,conjunction,0.5,1", s)


# ------------------------------------------------------------------
# Backup / Restore tests

class TestBackupRestore(unittest.TestCase):
    def setUp(self):
        self.db_path = "/tmp/test_astro_backup.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        schema_path = Path(__file__).parent.parent / "src" / "astro_data" / "schema.sql"
        conn = sqlite3.connect(self.db_path)
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute(
            "INSERT INTO people (name, birth_date, birth_time, timezone, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("Alice", "1990-01-15", "12:00:00", "UTC", 40.0, -74.0),
        )
        conn.execute(
            "INSERT INTO charts (chart_id, chart_type, positions, aspects) VALUES (?, ?, ?, ?)",
            ("chart-a", "natal", "{}", "[]"),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        for p in ["/tmp/test_backup.tar.gz", "/tmp/test_backup.sql", "/tmp/test_backup.json"]:
            if os.path.exists(p):
                os.remove(p)

    def test_backup_tar_gz_exists_with_sql_and_json(self):
        tar_path = backup_database(self.db_path, "/tmp/test_backup.tar.gz")
        self.assertTrue(os.path.exists(tar_path))
        with tarfile.open(tar_path, "r:gz") as tar:
            names = tar.getnames()
        self.assertTrue(any(n.endswith(".sql") for n in names), "Missing .sql in tar.gz")
        self.assertTrue(any(n.endswith(".json") for n in names), "Missing .json in tar.gz")

    def test_restore_from_sql(self):
        backup_database(self.db_path, "/tmp/test_backup.tar.gz")
        # Extract SQL
        with tarfile.open("/tmp/test_backup.tar.gz", "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".sql"):
                    sql = tar.extractfile(member).read().decode("utf-8")
                    break
        with open("/tmp/test_backup.sql", "w", encoding="utf-8") as f:
            f.write(sql)

        # Clear DB and restore
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM people")
        conn.execute("DELETE FROM charts")
        conn.commit()
        conn.close()

        result = restore_database(self.db_path, "/tmp/test_backup.sql")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["format"], "sql")

        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT name FROM people")
        names = [r[0] for r in cur.fetchall()]
        conn.close()
        self.assertIn("Alice", names)

    def test_restore_from_json(self):
        backup_database(self.db_path, "/tmp/test_backup.tar.gz")
        with tarfile.open("/tmp/test_backup.tar.gz", "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".json"):
                    json_content = tar.extractfile(member).read().decode("utf-8")
                    break
        with open("/tmp/test_backup.json", "w", encoding="utf-8") as f:
            f.write(json_content)

        # Clear DB and restore
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM people")
        conn.execute("DELETE FROM charts")
        conn.commit()
        conn.close()

        result = restore_database(self.db_path, "/tmp/test_backup.json")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["format"], "json")

        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT chart_id FROM charts")
        charts = [r[0] for r in cur.fetchall()]
        conn.close()
        self.assertIn("chart-a", charts)

    def test_restore_from_tar_gz(self):
        tar_path = backup_database(self.db_path, "/tmp/test_backup.tar.gz")
        # Clear DB
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM people")
        conn.execute("DELETE FROM charts")
        conn.commit()
        conn.close()

        result = restore_database(self.db_path, tar_path)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["format"], "tar.gz")

        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT name FROM people")
        names = [r[0] for r in cur.fetchall()]
        cur = conn.execute("SELECT chart_id FROM charts")
        charts = [r[0] for r in cur.fetchall()]
        conn.close()
        self.assertIn("Alice", names)
        self.assertIn("chart-a", charts)


# ------------------------------------------------------------------
# API endpoint tests

class TestAPIPhase8(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from astro_api import server as srv
        from astro_api.astro_ctypes import ac_init, ac_date_to_jd, ac_calc_chart, calculate_aspects, body_id_from_name, orb_preset_from_name
        from astro_data import db

        ac_init()
        jd = ac_date_to_jd(1969, 11, 30, 20, 43, 0, -6.0)
        points = [
            "Sun", "Moon", "Mercury", "Venus", "Mars",
            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
            "Mean Node", "Chiron",
        ]
        body_ids = [body_id_from_name(p) for p in points]
        chart = ac_calc_chart(jd, 35.2167, -101.8167, body_ids, "K")
        aspects = calculate_aspects(chart["bodies"], orb_preset_from_name("Modern"))
        chart["aspects"] = aspects
        cls.chart_id = "xephyr-natal"

        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        schema_path = Path(__file__).parent.parent / "src" / "astro_data" / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        cls.conn = conn
        db.add_chart(
            conn,
            chart_id=cls.chart_id,
            chart_type="natal",
            calc_date="2026-05-17T21:00:00+00:00",
            calc_options={"house_system": "K", "points": points, "orb_preset": "Modern"},
            positions={
                "bodies": chart["bodies"],
                "houses": chart["houses"],
                "angles": {
                    "ascendant": chart["ascendant"],
                    "mc": chart["mc"],
                    "armc": chart["armc"],
                    "vertex": chart["vertex"],
                },
                "latitude": 35.2167,
                "longitude": -101.8167,
            },
            aspects=aspects,
        )
        srv._db_conn = conn
        srv._migrate_legacy_charts()
        cls.server = srv.HTTPServer(("localhost", 8082), srv.AstroHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.conn.close()

    def test_export_ics_endpoint(self):
        req = {
            "chart_id": self.chart_id,
            "start_date": "2026-05-01",
            "end_date": "2026-05-05",
            "include_points": ["Saturn", "Uranus"],
            "filename": "test-xephyr.ics",
        }
        body = json.dumps(req).encode("utf-8")
        import urllib.request
        request = urllib.request.Request(
            "http://localhost:8082/v1/export/ics",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("chart_id"), self.chart_id)
        self.assertIn("filepath", data)
        self.assertIn("events_count", data)
        filepath = data["filepath"]
        self.assertTrue(os.path.exists(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("BEGIN:VCALENDAR", content)
        os.remove(filepath)

    def test_export_csv_endpoint(self):
        req = {
            "chart_id": self.chart_id,
            "start_date": "2026-05-01",
            "end_date": "2026-05-05",
            "include_points": ["Saturn", "Uranus"],
            "filename": "test-xephyr.csv",
        }
        body = json.dumps(req).encode("utf-8")
        import urllib.request
        request = urllib.request.Request(
            "http://localhost:8082/v1/export/csv",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("filepath", data)
        filepath = data["filepath"]
        self.assertTrue(os.path.exists(filepath))
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("date,transiting_body,natal_body,aspect,orb,applying", content)
        os.remove(filepath)

    def test_backup_endpoint(self):
        req = {}
        body = json.dumps(req).encode("utf-8")
        import urllib.request
        request = urllib.request.Request(
            "http://localhost:8082/v1/backup",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("backup_path", data)
        backup_path = data["backup_path"]
        self.assertTrue(os.path.exists(backup_path))
        os.remove(backup_path)

    def test_restore_endpoint(self):
        # Create a source DB with data to back up
        src_db = "/tmp/test_api_restore.db"
        if os.path.exists(src_db):
            os.remove(src_db)
        schema_path = Path(__file__).parent.parent / "src" / "astro_data" / "schema.sql"
        conn = sqlite3.connect(src_db)
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute(
            "INSERT INTO people (name, birth_date, birth_time, timezone, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)",
            ("Bob", "1985-03-10", "08:30:00", "UTC", 51.0, 0.0),
        )
        conn.commit()
        conn.close()

        # Create a backup first via direct call
        from astro_data.backup import backup_database
        tar_path = backup_database(src_db, "/tmp/test_api_restore.tar.gz")
        # Create an empty DB to restore into
        empty_db = "/tmp/test_api_restore_target.db"
        if os.path.exists(empty_db):
            os.remove(empty_db)
        schema_path = Path(__file__).parent.parent / "src" / "astro_data" / "schema.sql"
        conn = sqlite3.connect(empty_db)
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.close()

        # Point server at new DB temporarily? Instead test direct restore, then verify endpoint via server using original DB.
        req = {"backup_path": tar_path}
        body = json.dumps(req).encode("utf-8")
        import urllib.request
        request = urllib.request.Request(
            "http://localhost:8082/v1/restore",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # This will restore into the server's current in-memory DB (which has the chart).
        # To avoid messing up other tests, we just verify the endpoint returns OK and tables_restored > 0.
        with urllib.request.urlopen(request, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data.get("status"), "ok")
        self.assertGreater(data.get("tables_restored", 0), 0)
        os.remove(tar_path)
        if os.path.exists(empty_db):
            os.remove(empty_db)
        if os.path.exists(src_db):
            os.remove(src_db)


if __name__ == "__main__":
    unittest.main(verbosity=2)
