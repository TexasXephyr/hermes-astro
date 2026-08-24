"""hover_panel.py — Right-side hover inspector for the wheel views.

A scrollable markup label that shows the status, aspects, and cookbook
rows for whatever the mouse is over on the wheel. The panel is
deliberately simple: one label, scrollable, min width ~300px.
"""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango


class HoverPanel(Gtk.ScrolledWindow):
    """Scrollable panel that displays hover-target markup."""

    __gtype_name__ = "AstroHoverPanel"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_min_content_width(300)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._label = Gtk.Label()
        self._label.set_xalign(0.0)
        self._label.set_valign(Gtk.Align.START)
        self._label.set_wrap(True)
        self._label.set_selectable(True)
        self._label.set_margin_top(8)
        self._label.set_margin_bottom(8)
        self._label.set_margin_start(8)
        self._label.set_margin_end(8)
        self.set_child(self._label)

        self.clear()

    def show_markup(self, markup: str):
        self._label.set_markup(markup)

    def clear(self):
        self._label.set_markup(
            "<span color='#888888'>Hover over the wheel to inspect a planet, "
            "aspect, sign, or house.</span>"
        )

    @property
    def label(self) -> Gtk.Label:
        return self._label
