#!/usr/bin/env python3
"""
Phase 4 Tests: SQLite data model, CRUD layer, security, FK constraints.
Uses unittest (stdlib only — no external deps).
Run with: python3 tests/test_phase4.py -v
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from astro_data import db


class TestPeopleCRUD(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_add_and_get_person(self):
        pid = db.add_person(
            self.conn,
            name="Xephyr",
            birth_date="1969-11-30",
            birth_time="20:43:00",
            timezone="America/Chicago",
            latitude=35.2167,
            longitude=-101.8167,
        )
        self.assertIsInstance(pid, int)
        p = db.get_person(self.conn, pid)
        self.assertIsNotNone(p)
        self.assertEqual(p["name"], "Xephyr")
        self.assertEqual(p["birth_date"], "1969-11-30")
        self.assertEqual(p["timezone"], "America/Chicago")

    def test_list_people(self):
        db.add_person(self.conn, name="A", birth_date="2000-01-01", birth_time="12:00:00",
                      timezone="UTC", latitude=0.0, longitude=0.0)
        db.add_person(self.conn, name="B", birth_date="2000-01-02", birth_time="12:00:00",
                      timezone="UTC", latitude=0.0, longitude=0.0)
        people = db.list_people(self.conn)
        self.assertEqual(len(people), 2)
        names = {p["name"] for p in people}
        self.assertEqual(names, {"A", "B"})

    def test_update_person(self):
        pid = db.add_person(self.conn, name="Old", birth_date="2000-01-01", birth_time="12:00:00",
                            timezone="UTC", latitude=0.0, longitude=0.0)
        ok = db.update_person(self.conn, pid, name="New", email="new@example.com")
        self.assertTrue(ok)
        p = db.get_person(self.conn, pid)
        self.assertEqual(p["name"], "New")
        self.assertEqual(p["email"], "new@example.com")

    def test_delete_person(self):
        pid = db.add_person(self.conn, name="ToDelete", birth_date="2000-01-01", birth_time="12:00:00",
                            timezone="UTC", latitude=0.0, longitude=0.0)
        self.assertTrue(db.delete_person(self.conn, pid))
        self.assertIsNone(db.get_person(self.conn, pid))

    def test_delete_person_cascades_to_event_fk(self):
        pid = db.add_person(self.conn, name="Parent", birth_date="2000-01-01", birth_time="12:00:00",
                            timezone="UTC", latitude=0.0, longitude=0.0)
        eid = db.add_event(self.conn, name="Wedding", event_date="2020-06-01", person_id=pid)
        db.delete_person(self.conn, pid)
        ev = db.get_event(self.conn, eid)
        self.assertIsNone(ev["person_id"])


class TestEventsCRUD(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_add_and_get_event(self):
        eid = db.add_event(self.conn, name="Move", event_date="2021-03-15",
                           event_type="move", latitude=34.0, longitude=-118.0)
        ev = db.get_event(self.conn, eid)
        self.assertEqual(ev["name"], "Move")
        self.assertEqual(ev["event_type"], "move")

    def test_update_event(self):
        eid = db.add_event(self.conn, name="Old", event_date="2021-01-01")
        db.update_event(self.conn, eid, name="New", notes="updated")
        ev = db.get_event(self.conn, eid)
        self.assertEqual(ev["name"], "New")
        self.assertEqual(ev["notes"], "updated")

    def test_delete_event(self):
        eid = db.add_event(self.conn, name="X", event_date="2021-01-01")
        self.assertTrue(db.delete_event(self.conn, eid))
        self.assertIsNone(db.get_event(self.conn, eid))


class TestChartsCRUD(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_add_and_get_chart(self):
        cid = db.add_chart(
            self.conn,
            chart_type="natal",
            positions=[{"name": "Sun", "lon": 120.0}],
            aspects=[{"body_a": "Sun", "body_b": "Moon", "aspect": "trine"}],
        )
        c = db.get_chart(self.conn, cid)
        self.assertIsNotNone(c)
        self.assertEqual(c["chart_type"], "natal")
        self.assertIsInstance(c["positions"], list)
        self.assertIsInstance(c["aspects"], list)

    def test_list_charts(self):
        db.add_chart(self.conn, chart_type="natal", positions=[], aspects=[])
        db.add_chart(self.conn, chart_type="transit", positions=[], aspects=[])
        charts = db.list_charts(self.conn)
        self.assertEqual(len(charts), 2)

    def test_delete_chart(self):
        cid = db.add_chart(self.conn, chart_type="natal", positions=[], aspects=[])
        self.assertTrue(db.delete_chart(self.conn, cid))
        self.assertIsNone(db.get_chart(self.conn, cid))

    def test_chart_with_person_fk(self):
        pid = db.add_person(self.conn, name="Person", birth_date="2000-01-01", birth_time="12:00:00",
                            timezone="UTC", latitude=0.0, longitude=0.0)
        cid = db.add_chart(self.conn, chart_type="natal", person_id=pid, positions=[], aspects=[])
        c = db.get_chart(self.conn, cid)
        self.assertEqual(c["person_id"], pid)


class TestInterpretations(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_add_and_get_interpretation(self):
        chart_uuid = db.add_chart(self.conn, chart_type="natal", positions=[], aspects=[])
        c = db.get_chart(self.conn, chart_uuid)
        db_id = c["id"]
        iid = db.add_interpretation(
            self.conn, chart_id=db_id, section="natal", sub_section="Sun in 5th",
            content="Creative vitality.", model="rules",
        )
        self.assertIsInstance(iid, int)
        rows = db.get_interpretations_by_chart(self.conn, db_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["content"], "Creative vitality.")


class TestApiKeys(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_add_and_verify_api_key(self):
        key = "my-secret-api-key-12345"
        kid = db.add_api_key(self.conn, key=key, name="Test Key")
        self.assertIsInstance(kid, int)
        found = db.get_api_key_by_hash(self.conn, key)
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "Test Key")

    def test_revoke_api_key(self):
        key = "revoke-me"
        kid = db.add_api_key(self.conn, key=key, name="Revokable")
        self.assertTrue(db.revoke_api_key(self.conn, kid))
        found = db.get_api_key_by_hash(self.conn, key)
        self.assertIsNone(found)

    def test_wrong_key_not_verified(self):
        db.add_api_key(self.conn, key="real-key", name="Real")
        found = db.get_api_key_by_hash(self.conn, "wrong-key")
        self.assertIsNone(found)


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_parameterized_query_blocks_injection_in_person_name(self):
        malicious = "'; DROP TABLE people; --"
        pid = db.add_person(
            self.conn,
            name=malicious,
            birth_date="2000-01-01",
            birth_time="12:00:00",
            timezone="UTC",
            latitude=0.0,
            longitude=0.0,
        )
        p = db.get_person(self.conn, pid)
        self.assertIsNotNone(p)
        self.assertEqual(p["name"], malicious)
        cur = self.conn.execute("SELECT count(*) FROM people")
        self.assertGreaterEqual(cur.fetchone()[0], 1)

    def test_parameterized_query_blocks_injection_in_chart_fields(self):
        malicious = '{"body": "<script>alert(1)</script>"}'
        cid = db.add_chart(
            self.conn,
            chart_type="natal",
            positions=malicious,
            aspects=[],
        )
        c = db.get_chart(self.conn, cid)
        self.assertIsNotNone(c)
        self.assertEqual(c["positions"], malicious)


class TestForeignKeyConstraints(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_fk_constraint_blocks_orphan_chart_person(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.add_chart(self.conn, chart_type="natal", person_id=9999, positions=[], aspects=[])


if __name__ == "__main__":
    unittest.main(verbosity=2)
