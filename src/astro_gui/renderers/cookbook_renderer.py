"""cookbook_renderer.py — Selectable cookbook list for the astrology GUI.

The Cookbook tab shows each chart placement (body in sign, body in
house, aspect) as a selectable row; selecting a row shows the grounded
corpus prose in a detail pane below. Rows are compact (title + subtitle)
so the list can carry a large number of positions without fighting the
display — the prose lives in the detail pane, not the row.

Entry builders are pure functions (unit-testable headless):
  natal_cookbook_entries(snapshot, cookbook) -> list[CookbookEntry]

The list itself is a Gtk.ListBox (single selection). Sections are
rendered as non-selectable header rows. Missing corpus keys are shown as
rows with an explicit "no corpus entry" note — never invented prose.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, Pango

from astro_text.symbols import symbol_for_body, symbol_for_sign, symbol_for_aspect


class CookbookEntry(GObject.Object):
    """One selectable row in the cookbook list."""

    __gtype_name__ = "AstroCookbookEntry"

    title = GObject.Property(type=str, default="")
    subtitle = GObject.Property(type=str, default="")
    text = GObject.Property(type=str, default="")
    section = GObject.Property(type=str, default="")
    missing = GObject.Property(type=bool, default=False)

    def __init__(self, title="", subtitle="", text="", section="",
                 missing=False, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.subtitle = subtitle
        self.text = text
        self.section = section
        self.missing = missing


def _glyph_body(name: str) -> str:
    glyph = symbol_for_body(name) or ""
    return f"{glyph} {name}".strip()


def _glyph_sign(name: str) -> str:
    if not name:
        return ""
    try:
        glyph = symbol_for_sign(name)
    except KeyError:
        glyph = ""
    return f"{glyph} {name}".strip()


def _glyph_aspect(name: str) -> str:
    if not name:
        return ""
    try:
        glyph = symbol_for_aspect(name)
    except KeyError:
        glyph = ""
    return f"{glyph} {name}".strip()


def natal_cookbook_entries(snapshot, cookbook: dict) -> list[CookbookEntry]:
    """Build the ordered entry list for a natal snapshot + cookbook.

    Sections: Bodies (sign + house per body), Aspects, Missing.
    Each entry carries the grounded corpus text; missing entries carry
    an explicit note instead of invented prose.
    """
    entries: list[CookbookEntry] = []

    by_sign = {e["body"]: e for e in cookbook.get("natal_signs", [])}
    by_house = {e["body"]: e for e in cookbook.get("natal_houses", [])}

    for b in snapshot.bodies:
        name = b.get("name", "?")
        sign = b.get("sign", "")
        sign_name = _glyph_sign(sign)
        house = b.get("house")
        retro = " (R)" if b.get("retrograde") else ""
        deg = b.get("sign_degree", "")

        sign_entry = by_sign.get(name)
        house_entry = by_house.get(name)

        title = f"{_glyph_body(name)} in {sign_name}"
        subtitle = f"House {house} · {deg}°{retro}"
        prose_parts = []
        if sign_entry:
            prose_parts.append(sign_entry["text"])
        if house_entry:
            prose_parts.append(f"House {house}: {house_entry['text']}")
        if not prose_parts:
            entries.append(CookbookEntry(
                title=title, subtitle=subtitle,
                text="No corpus entry for this placement — do not guess.",
                section="Bodies", missing=True,
            ))
        else:
            entries.append(CookbookEntry(
                title=title, subtitle=subtitle,
                text="\n\n".join(prose_parts), section="Bodies",
            ))

    for a in cookbook.get("natal_aspects", []):
        title = f"{_glyph_body(a['body_a'])} {_glyph_aspect(a['aspect'])} {_glyph_body(a['body_b'])}"
        subtitle = f"Orb {a['orb']}°"
        entries.append(CookbookEntry(
            title=title, subtitle=subtitle, text=a["text"], section="Aspects",
        ))

    for key in cookbook.get("missing", []):
        entries.append(CookbookEntry(
            title=key, subtitle="",
            text="No corpus entry for this placement — do not guess.",
            section="Missing", missing=True,
        ))

    return entries


def _timing_label(days) -> str:
    """'exact today' / 'exact in 2d' / 'exact 3d ago' from days_to_exact."""
    try:
        d = int(days)
    except (TypeError, ValueError):
        return ""
    if d == 0:
        return "exact today"
    if d > 0:
        return f"exact in {d}d"
    return f"exact {abs(d)}d ago"


def transit_cookbook_entries(snapshot, cookbook: dict) -> list[CookbookEntry]:
    """Build the ordered entry list for a transit snapshot + cookbook.

    Sections: Bodies (transiting body in sign / over natal house),
    Active Transits, Missing.
    """
    entries: list[CookbookEntry] = []

    by_sign = {e["body"]: e for e in cookbook.get("transit_signs", [])}
    by_house = {e["body"]: e for e in cookbook.get("transit_houses", [])}

    for b in snapshot.bodies:
        name = b.get("name", "?")
        sign = b.get("sign", "")
        sign_name = _glyph_sign(sign)
        house = b.get("natal_house")
        retro = " (R)" if b.get("retrograde") else ""
        deg = b.get("sign_degree", "")

        sign_entry = by_sign.get(name)
        house_entry = by_house.get(name)

        title = f"{_glyph_body(name)} in {sign_name}"
        subtitle = f"over natal house {house} · {deg}°{retro}" if house else f"{deg}°{retro}"
        prose_parts = []
        if sign_entry:
            prose_parts.append(sign_entry["text"])
        if house_entry:
            prose_parts.append(f"Over natal house {house}: {house_entry['text']}")
        if not prose_parts:
            entries.append(CookbookEntry(
                title=title, subtitle=subtitle,
                text="No corpus entry for this placement — do not guess.",
                section="Bodies", missing=True,
            ))
        else:
            entries.append(CookbookEntry(
                title=title, subtitle=subtitle,
                text="\n\n".join(prose_parts), section="Bodies",
            ))

    for a in cookbook.get("transit_aspects", []):
        title = f"{_glyph_body(a['transit_body'])} {_glyph_aspect(a['aspect'])} {_glyph_body(a['natal_body'])}"
        timing = _timing_label(a.get("days_to_exact"))
        subtitle = f"Orb {a['orb']}° · {timing}".strip(" ·")
        entries.append(CookbookEntry(
            title=title, subtitle=subtitle, text=a["text"], section="Active Transits",
        ))

    for key in cookbook.get("missing", []):
        entries.append(CookbookEntry(
            title=key, subtitle="",
            text="No corpus entry for this placement — do not guess.",
            section="Missing", missing=True,
        ))

    return entries


def synastry_cookbook_entries(snapshot, cookbook: dict) -> list[CookbookEntry]:
    """Build the ordered entry list for a synastry snapshot + cookbook.

    Sections: Bodies in B's house, Cross Aspects, Missing.
    """
    entries: list[CookbookEntry] = []

    person_b = getattr(snapshot, "person_b", "Partner")
    by_house = {e["body"]: e for e in cookbook.get("synastry_houses", [])}

    for b in snapshot.bodies:
        name = b.get("name", "?")
        sign = b.get("sign", "")
        sign_name = _glyph_sign(sign)
        house = b.get("house_b")
        deg = b.get("sign_degree", "")

        house_entry = by_house.get(name)

        title = f"{_glyph_body(name)} in {person_b}'s house {house}"
        subtitle = f"{sign_name} · {deg}°"
        if house_entry:
            entries.append(CookbookEntry(
                title=title, subtitle=subtitle,
                text=house_entry["text"], section=f"Bodies in {person_b}'s house",
            ))
        else:
            entries.append(CookbookEntry(
                title=title, subtitle=subtitle,
                text="No corpus entry for this placement — do not guess.",
                section=f"Bodies in {person_b}'s house", missing=True,
            ))

    for a in cookbook.get("synastry_aspects", []):
        title = f"{_glyph_body(a['body_a'])} {_glyph_aspect(a['aspect'])} {_glyph_body(a['body_b'])}"
        subtitle = f"Orb {a['orb']}°"
        entries.append(CookbookEntry(
            title=title, subtitle=subtitle, text=a["text"], section="Cross Aspects",
        ))

    for key in cookbook.get("missing", []):
        entries.append(CookbookEntry(
            title=key, subtitle="",
            text="No corpus entry for this placement — do not guess.",
            section="Missing", missing=True,
        ))

    return entries


def _section_row(title: str) -> Gtk.ListBoxRow:
    """A non-selectable section header row."""
    label = Gtk.Label(label=title)
    label.set_xalign(0.0)
    label.set_margin_top(8)
    label.set_margin_bottom(2)
    label.set_margin_start(6)
    label.set_margin_end(6)
    label.add_css_class("heading")
    row = Gtk.ListBoxRow()
    row.set_selectable(False)
    row.set_activatable(False)
    row.set_child(label)
    return row


def _entry_row(entry: CookbookEntry) -> Gtk.ListBoxRow:
    """A selectable row: title (bold) + subtitle (muted)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.set_spacing(1)
    box.set_margin_top(4)
    box.set_margin_bottom(4)
    box.set_margin_start(8)
    box.set_margin_end(8)

    title = Gtk.Label(label=entry.title)
    title.set_xalign(0.0)
    title.set_ellipsize(Pango.EllipsizeMode.END)
    title.add_css_class("title")
    box.append(title)

    if entry.subtitle:
        sub = Gtk.Label(label=entry.subtitle)
        sub.set_xalign(0.0)
        sub.set_ellipsize(Pango.EllipsizeMode.END)
        sub.add_css_class("dim-label")
        box.append(sub)

    row = Gtk.ListBoxRow()
    row.set_child(box)
    row._entry = entry
    return row


def build_cookbook_list(entries: list[CookbookEntry]) -> Gtk.Widget:
    """Build the selectable cookbook list + detail pane.

    Returns a vertical Box: the detail pane on top showing the selected
    row's prose (sized to its content — variable depth, never clipped),
    and the scrollable ListBox below taking the remaining space. The
    detail pane is reachable as `box.detail_label` for tests.
    """
    listbox = Gtk.ListBox()
    listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)

    current_section = None
    for entry in entries:
        if entry.section != current_section:
            listbox.append(_section_row(entry.section))
            current_section = entry.section
        listbox.append(_entry_row(entry))

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_hexpand(True)
    scroll.set_child(listbox)

    detail = Gtk.Label()
    detail.set_xalign(0.0)
    detail.set_valign(Gtk.Align.START)
    detail.set_wrap(True)
    detail.set_margin_top(8)
    detail.set_margin_bottom(8)
    detail.set_margin_start(8)
    detail.set_margin_end(8)
    detail.set_selectable(True)
    detail.set_text("Select a placement to see its corpus interpretation.")

    # Detail pane above the list, sized to its content. The label sits
    # directly in the vertical box (NO ScrolledWindow wrapper): the box
    # measures it at the real width, the text wraps, and its natural
    # height grows with the prose — so the full text for a planet or
    # aspect is always visible (variable depth). The list below takes
    # whatever space remains and scrolls.
    def _on_row_selected(_listbox, row):
        if row is None:
            return
        entry = getattr(row, "_entry", None)
        if entry is None:
            return
        if entry.missing:
            detail.set_markup(
                f"<b>{entry.title}</b>\n\n<span color='#d4a72c'>{entry.text}</span>"
            )
        else:
            detail.set_markup(f"<b>{entry.title}</b>\n\n{entry.text}")

    listbox.connect("row-selected", _on_row_selected)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(detail)
    box.append(scroll)
    box.detail_label = detail
    box.listbox = listbox
    return box
