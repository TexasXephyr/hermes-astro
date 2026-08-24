"""main.py — AstroGuiApplication entry point."""

import os
import sys
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GObject

from astro_gui.window import MainWindow


# Package-relative path to the CSS file
_CSS_PATH = os.path.join(os.path.dirname(__file__), "styles", "style.css")


class AstroGuiApplication(Gtk.Application):
    """GTK4 Application shell with dark theme and modular window."""

    def __init__(self):
        super().__init__(
            application_id="com.nousresearch.AstroGui",
            flags=0,
        )

    def do_activate(self):
        # Create or present main window
        window = MainWindow(app=self)
        window.present()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._apply_theme()
        self._build_menubar()

    # ------------------------------------------------------------------
    # Menubar
    # ------------------------------------------------------------------
    def _build_menubar(self):
        """File menu: Save Document Set As... / Load Document Set..."""
        menu = Gio.Menu()
        file_menu = Gio.Menu()
        file_menu.append("Save Document Set As...", "win.save-document-set")
        file_menu.append("Load Document Set...", "win.load-document-set")
        menu.append_submenu("File", file_menu)
        self.set_menubar(menu)

    # ------------------------------------------------------------------
    # Theme / CSS
    # ------------------------------------------------------------------
    def _apply_theme(self):
        # Always request dark theme at the GTK settings level first
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-application-prefer-dark-theme", True)

        if os.path.isfile(_CSS_PATH):
            self._load_css(_CSS_PATH)

    def _load_css(self, path: str):
        css_provider = Gtk.CssProvider()
        try:
            css_provider.load_from_path(path)
        except Exception:
            return

        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


# ----------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------
def main():
    app = AstroGuiApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
