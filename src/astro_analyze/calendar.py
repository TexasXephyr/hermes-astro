"""
Calendar export module (Phase 8).
ICS (iCalendar) and CSV export for transit events.
Python stdlib only.
"""
import csv
import io
import os
from datetime import datetime


# ------------------------------------------------------------------
# Contact deduplication

def dedupe_contacts(events: list) -> list:
    """Collapse per-day in-orb events into one row per aspect contact.

    ``find_transit_events`` emits a row for every day an aspect is within
    orb, so a single Saturn-Sun conjunction spanning weeks produces many
    rows. For a calendar, one row per (transiting_body, natal_body,
    aspect) contact is what a human reads: dated at the day the aspect
    is most exact (smallest orb), with the original fields preserved.
    Returns the deduped list sorted by date then orb.
    """
    best: dict[tuple, dict] = {}
    for e in events:
        key = (e.get("transiting_body"), e.get("natal_body"), e.get("aspect"))
        cur = best.get(key)
        if cur is None or abs(float(e.get("orb", 999))) < abs(float(cur.get("orb", 999))):
            best[key] = e
    return sorted(best.values(), key=lambda e: (e.get("date", ""), e.get("orb", 999)))


# ------------------------------------------------------------------
# ICS export

def _ics_escape(text: str) -> str:
    """Escape special chars for ICS text values."""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_uid(event: dict, idx: int) -> str:
    """Generate a unique UID for a transit event."""
    tb = event.get("transiting_body", "unknown").lower().replace(" ", "-")
    nb = event.get("natal_body", "unknown").lower().replace(" ", "-")
    date = event.get("date", "unknown")
    return f"{tb}-{nb}-{date}-{idx}@astro-tool"


def _ics_date_str(date_str: str) -> str:
    """Convert YYYY-MM-DD to ICS DATE format YYYYMMDD."""
    return date_str.replace("-", "")


def _ics_lines(events: list) -> list:
    """Build the raw ICS line list for `events` (shared by file/string writers)."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Astrology Tool//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for idx, event in enumerate(events):
        tb = event.get("transiting_body", "Unknown")
        nb = event.get("natal_body", "Unknown")
        aspect = event.get("aspect", "aspect")
        date = event.get("date", "")
        orb = event.get("orb", 0.0)
        applying = event.get("applying", False)
        angle = event.get("angle", 0.0)

        summary = f"{tb} {aspect} natal {nb}"
        desc = (
            f"Orb: {orb} degrees. "
            f"{'Applying' if applying else 'Separating'}. "
            f"Angle: {angle}\u00b0."
        )
        uid = _ics_uid(event, idx)
        dtstart = _ics_date_str(date)

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"DTSTART;VALUE=DATE:{dtstart}")
        lines.append(f"SUMMARY:{_ics_escape(summary)}")
        lines.append(f"DESCRIPTION:{_ics_escape(desc)}")
        lines.append("TRANSP:TRANSPARENT")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return lines


def export_to_ics(events: list, filename: str) -> None:
    """
    Write transit events to .ics file compatible with Google Calendar, Apple Calendar, etc.

    Each event becomes a VEVENT with:
    - SUMMARY: "Saturn conjunct natal Sun"
    - DTSTART;VALUE=DATE: exact date of transit
    - DESCRIPTION: Full transit details
    - UID: unique identifier per event
    """
    lines = _ics_lines(events)

    # Ensure directory exists
    dirname = os.path.dirname(filename)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(filename, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lines))
        f.write("\r\n")


def export_to_ics_string(events: list) -> str:
    """Return the ICS calendar as a string (for GUI save-dialog writes)."""
    return "\r\n".join(_ics_lines(events)) + "\r\n"


# ------------------------------------------------------------------
# CSV export

def export_to_csv(events: list, filename: str) -> None:
    """
    Simple CSV with columns: date, transiting_body, natal_body, aspect, orb, applying
    """
    rows = []
    for event in events:
        rows.append({
            "date": event.get("date", ""),
            "transiting_body": event.get("transiting_body", ""),
            "natal_body": event.get("natal_body", ""),
            "aspect": event.get("aspect", ""),
            "orb": event.get("orb", 0.0),
            "applying": "1" if event.get("applying", False) else "0",
        })

    dirname = os.path.dirname(filename)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "transiting_body", "natal_body", "aspect", "orb", "applying"],
        )
        writer.writeheader()
        writer.writerows(rows)


def export_to_csv_string(events: list) -> str:
    """Return CSV content as a string (useful for API responses)."""
    if not events:
        return "date,transiting_body,natal_body,aspect,orb,applying\n"
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["date", "transiting_body", "natal_body", "aspect", "orb", "applying"],
    )
    writer.writeheader()
    for event in events:
        writer.writerow({
            "date": event.get("date", ""),
            "transiting_body": event.get("transiting_body", ""),
            "natal_body": event.get("natal_body", ""),
            "aspect": event.get("aspect", ""),
            "orb": event.get("orb", 0.0),
            "applying": "1" if event.get("applying", False) else "0",
        })
    return output.getvalue()
