"""calendar_renderer.py — Date-range transit event list for the astrology GUI.

Builds a sortable Gtk.ColumnView table of transit events over a date
range (the "Calendar" tab):

  Date | Body | Aspect | Natal | Orb | Applying | Priority

Events come from astro_analyze.transits.find_transit_events, scored with
astro_analyze.scoring.score_active_transits (the centralized priority
formula — same as the Transit Grid). The view follows the same GTK 4.22
conventions as table_renderer: a visible row of sort buttons ABOVE the
view (the native ColumnView header cannot host custom widgets on this
build), one button per column, click to sort, re-click to invert, with a
'▲ '/'▼ ' prefix on the active button.

Body / aspect / natal cells render with LiberZodiac path glyphs via the
shared _glyph_column helper from table_renderer.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Gio

from astro_gui.renderers.table_renderer import (
    _text_column,
    _glyph_column,
    _make_sorter,
    _header_button,
    _install_sort_buttons,
)


class CalendarRow(GObject.Object):
    """One row in the calendar event list."""

    __gtype_name__ = "AstroCalendarRow"

    date = GObject.Property(type=str, default="")
    body = GObject.Property(type=str, default="")
    aspect = GObject.Property(type=str, default="")
    natal = GObject.Property(type=str, default="")
    orb = GObject.Property(type=str, default="")
    applying = GObject.Property(type=str, default="")
    priority = GObject.Property(type=str, default="")
    # Raw names (no glyphs) for filtering / stable sorting
    body_name = GObject.Property(type=str, default="")
    natal_name = GObject.Property(type=str, default="")
    aspect_name = GObject.Property(type=str, default="")
    sort_date = GObject.Property(type=str, default="")
    sort_orb = GObject.Property(type=float, default=0.0)
    sort_priority = GObject.Property(type=int, default=0)

    def __init__(self, date="", body="", aspect="", natal="", orb="",
                 applying="", priority="", body_name="", natal_name="",
                 aspect_name="", sort_date="", sort_orb=0.0,
                 sort_priority=0, **kwargs):
        super().__init__(**kwargs)
        self.date = date
        self.body = body
        self.aspect = aspect
        self.natal = natal
        self.orb = orb
        self.applying = applying
        self.priority = priority
        self.body_name = body_name
        self.natal_name = natal_name
        self.aspect_name = aspect_name
        self.sort_date = sort_date
        self.sort_orb = sort_orb
        self.sort_priority = sort_priority


CALENDAR_COLUMNS = ["Date", "Body", "Aspect", "Natal", "Orb", "Applying", "Priority"]


def build_calendar_view(events: list[dict]) -> Gtk.Widget:
    """Build the calendar event list: Date | Body | Aspect | Natal | Orb | Applying | Priority.

    `events` is the priority-scored list from
    astro_analyze.scoring.score_active_transits (each dict has
    transiting_body, natal_body, aspect, orb, applying, date, priority).

    Returns a vertical Box: a row of sort buttons above the ColumnView.
    Default sort: date ascending. The sort buttons live in a visible row
    above the view because GTK 4.22's ColumnView header row cannot host
    custom widgets on this build (see table_renderer._install_sort_buttons).
    """
    rows = []
    for e in events:
        tb = e.get("transiting_body", "?")
        nb = e.get("natal_body", "?")
        aspect = e.get("aspect", "?")
        date = e.get("date", "")
        applying = "Applying" if e.get("applying") else "Separating"
        rows.append(CalendarRow(
            date=date,
            body=tb,
            aspect=aspect,
            natal=nb,
            orb=f"{e.get('orb', 0.0):.2f}°",
            applying=applying,
            priority=str(e.get("priority", 0)),
            body_name=tb,
            natal_name=nb,
            aspect_name=aspect,
            sort_date=date,
            sort_orb=float(e.get("orb", 0.0)),
            sort_priority=int(e.get("priority", 0)),
        ))

    model = Gio.ListStore.new(CalendarRow)
    for r in rows:
        model.append(r)

    sort_model = Gtk.SortListModel(model=model)
    selection = Gtk.SingleSelection(model=sort_model)
    view = Gtk.ColumnView(model=selection)

    sorter_specs = {
        "Date": _make_sorter(CalendarRow, "sort_date"),
        "Body": _make_sorter(CalendarRow, "body"),
        "Aspect": _make_sorter(CalendarRow, "aspect"),
        "Natal": _make_sorter(CalendarRow, "natal"),
        "Orb": _make_sorter(CalendarRow, "sort_orb"),
        "Applying": _make_sorter(CalendarRow, "applying"),
        "Priority": _make_sorter(CalendarRow, "sort_priority", descending=True),
    }
    view.append_column(_text_column("Date", "date", sortable=True, sorter=sorter_specs["Date"]))
    view.append_column(_glyph_column("Body", "body", sortable=True, sorter=sorter_specs["Body"]))
    view.append_column(_text_column("Aspect", "aspect", sortable=True, sorter=sorter_specs["Aspect"]))
    view.append_column(_glyph_column("Natal", "natal", sortable=True, sorter=sorter_specs["Natal"]))
    view.append_column(_text_column("Orb", "orb", sortable=True, sorter=sorter_specs["Orb"]))
    view.append_column(_text_column("Applying", "applying", sortable=True, sorter=sorter_specs["Applying"]))
    view.append_column(_text_column("Priority", "priority", sortable=True, sorter=sorter_specs["Priority"]))

    # Default sort: date ascending
    sort_model.set_sorter(sorter_specs["Date"])

    buttons = {title: _header_button(title) for title in sorter_specs}
    sort_row = _install_sort_buttons(view, sort_model, buttons, sorter_specs,
                                     default_title="Date")
    view._sort_model = sort_model
    view._sort_buttons = buttons

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(sort_row)
    box.append(view)
    view.set_vexpand(True)
    return box


def calendar_csv_rows(events: list[dict]) -> list[dict]:
    """Rows for the calendar CSV export, mirroring the view's columns."""
    rows = []
    for e in events:
        rows.append({
            "Date": e.get("date", ""),
            "Body": e.get("transiting_body", ""),
            "Aspect": e.get("aspect", ""),
            "Natal": e.get("natal_body", ""),
            "Orb": f"{e.get('orb', 0.0):.2f}",
            "Applying": "1" if e.get("applying") else "0",
            "Priority": str(e.get("priority", 0)),
        })
    return rows


CALENDAR_CSV_COLUMNS = ["Date", "Body", "Aspect", "Natal", "Orb", "Applying", "Priority"]
