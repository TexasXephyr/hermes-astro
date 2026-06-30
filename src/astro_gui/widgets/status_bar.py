"""status_bar.py — StatusBar widget for the astrology GUI."""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GObject, GLib
import datetime


class StatusBar(Gtk.Box):
    """Displays active planet info, house system, and current time."""

    __gtype_name__ = "AstroStatusBar"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(12)
        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_hexpand(True)

        # Left info label (planet / house / system)
        self._info_label = Gtk.Label()
        self._info_label.set_hexpand(True)
        self._info_label.set_xalign(0.0)
        self._info_label.set_text("Ready — select a person")
        self.append(self._info_label)

        # Right time label
        self._time_label = Gtk.Label()
        self._time_label.set_xalign(1.0)
        self._time_label.set_text("--:--:--")
        self.append(self._time_label)

        # Update timer
        self._tick()
        self._timer_id = GLib.timeout_add_seconds(1, self._tick)

    def _tick(self):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self._time_label.set_text(now)
        return True

    def set_info(self, text: str):
        """Update the left-side status text."""
        self._info_label.set_text(text)

    def do_dispose(self):
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        super().do_dispose()
