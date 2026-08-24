"""test_calendar_export.py — Library-side ICS/CSV export tests (pytest)."""

from astro_analyze.calendar import (
    export_to_ics,
    export_to_ics_string,
    export_to_csv_string,
    dedupe_contacts,
)

EVENTS = [
    {"date": "2026-09-05", "transiting_body": "Saturn", "natal_body": "Sun",
     "aspect": "conjunction", "orb": 0.4, "applying": True, "angle": 0.0},
    {"date": "2026-08-30", "transiting_body": "Mars", "natal_body": "Moon",
     "aspect": "square", "orb": 1.2, "applying": False, "angle": 90.0},
]


def test_ics_string_structure():
    ics = export_to_ics_string(EVENTS)
    lines = ics.splitlines()
    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-1] == "END:VCALENDAR"
    assert ics.count("BEGIN:VEVENT") == 2
    assert ics.count("END:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20260905" in ics
    assert "SUMMARY:Saturn conjunction natal Sun" in ics
    assert "DESCRIPTION:Orb: 0.4 degrees. Applying. Angle: 0.0\u00b0." in ics


def test_ics_string_matches_file_output():
    import tempfile, os
    ics_str = export_to_ics_string(EVENTS)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.ics")
        export_to_ics(EVENTS, path)
        with open(path, encoding="utf-8", newline="") as f:
            assert f.read() == ics_str


def test_ics_uid_unique():
    ics = export_to_ics_string(EVENTS)
    uids = [l for l in ics.splitlines() if l.startswith("UID:")]
    assert len(uids) == 2
    assert len(set(uids)) == 2


def test_ics_escaping():
    evil = [{"date": "2026-09-05", "transiting_body": "Saturn, Jr", "natal_body": "Sun",
             "aspect": "conjunction", "orb": 0.4, "applying": True, "angle": 0.0}]
    ics = export_to_ics_string(evil)
    assert "Saturn\\, Jr" in ics


def test_csv_string():
    csv = export_to_csv_string(EVENTS)
    assert csv.startswith("date,transiting_body,natal_body,aspect,orb,applying")
    assert "2026-09-05,Saturn,Sun,conjunction,0.4,1" in csv
    assert "2026-08-30,Mars,Moon,square,1.2,0" in csv


def test_dedupe_contacts():
    # Same contact across many in-orb days → one row at the most exact day
    raw = [
        {"date": "2026-09-01", "transiting_body": "Saturn", "natal_body": "Sun",
         "aspect": "conjunction", "orb": 2.1, "applying": True},
        {"date": "2026-09-05", "transiting_body": "Saturn", "natal_body": "Sun",
         "aspect": "conjunction", "orb": 0.4, "applying": True},
        {"date": "2026-09-10", "transiting_body": "Saturn", "natal_body": "Sun",
         "aspect": "conjunction", "orb": 1.8, "applying": False},
        {"date": "2026-09-03", "transiting_body": "Mars", "natal_body": "Moon",
         "aspect": "square", "orb": 1.2, "applying": False},
    ]
    out = dedupe_contacts(raw)
    assert len(out) == 2, f"expected 2 contacts, got {len(out)}"
    saturn = [e for e in out if e["transiting_body"] == "Saturn"][0]
    assert saturn["date"] == "2026-09-05", f"Saturn contact dated {saturn['date']}"
    assert saturn["orb"] == 0.4
    # Sorted by date
    assert [e["date"] for e in out] == sorted(e["date"] for e in out)
