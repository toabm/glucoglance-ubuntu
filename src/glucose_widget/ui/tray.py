"""Tray indicator implementation of the Display protocol.

Shows the glucose value and trend arrow as the indicator's *icon*, rendered
on the fly as a small bitmap (see `icon_renderer`). We render the number
into the icon itself, rather than using AppIndicator's built-in text-label
feature, because that label feature doesn't render at all under this
project's target Shell/extension combination (GNOME Shell 46 +
ubuntu-appindicators) - confirmed by direct D-Bus inspection during
development: our app correctly publishes the label text, but the Shell
extension never draws it. Icon rendering, unlike the label, was confirmed
to work reliably, so the number becomes the icon instead.

Ubuntu versions differ in whether they ship the original `AppIndicator3`
GObject-introspection typelib or its community-maintained fork,
`AyatanaAppIndicator3` (the one present on Ubuntu 24.04, this project's
target). We try Ayatana first and fall back to the classic name so this
runs on either.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except ValueError:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3  # type: ignore[no-redef]

from gi.repository import GLib, Gtk

from glucose_widget.config.autostart import set_autostart_enabled
from glucose_widget.config.settings import Settings, save_settings
from glucose_widget.domain.range import GlucoseRange, classify_mgdl
from glucose_widget.domain.reading import GlucoseReading
from glucose_widget.domain.units import GlucoseUnit
from glucose_widget.ui.icon_renderer import DEFAULT_TEXT_COLOR_RGBA, parse_hex_color, render_text_icon

_APP_ID = "glucose-widget"


class TrayDisplay:
    """Displays glucose readings in the Ubuntu top bar via AppIndicator3/Ayatana."""

    def __init__(self, settings: Settings):
        self._settings = settings

        # Range thresholds and colors come from settings (config.toml) so
        # they're user-tunable without a code change; see classify_mgdl's
        # docstring for why the thresholds are always in mg/dL.
        self._low_threshold = settings.low_threshold_mgdl
        self._high_threshold = settings.high_threshold_mgdl
        self._range_colors = {
            GlucoseRange.LOW: parse_hex_color(settings.color_low),
            GlucoseRange.NORMAL: parse_hex_color(settings.color_normal),
            GlucoseRange.HIGH: parse_hex_color(settings.color_high),
        }

        # Keep the actual autostart file in sync with the setting on every
        # startup - covers both a fresh install (setting defaults to True,
        # so this installs it immediately) and a manual config.toml edit.
        set_autostart_enabled(settings.autostart_enabled)

        self._icon_dir = Path(tempfile.mkdtemp(prefix="glucose-widget-icons-"))
        # Confirmed live: GNOME Shell caches a tray icon bitmap by filename
        # and never re-reads it once that name has been seen, even after
        # the file's content changes - so a fixed/alternating set of names
        # just replays stale cached bitmaps. Every update instead gets a
        # brand-new, never-before-seen filename to guarantee a fresh read;
        # _write_icon() deletes the previous file right after.
        self._update_counter = 0
        self._recent_icon_names: list[str] = []
        # Set once shutdown() is called, even if it happens before run()
        # starts the main loop (see shutdown()'s docstring for why that can
        # happen) - lets run() skip entering the loop at all in that case.
        self._quit_requested = False

        self._indicator = AppIndicator3.Indicator.new(
            _APP_ID,
            self._write_icon("--", DEFAULT_TEXT_COLOR_RGBA),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_icon_theme_path(str(self._icon_dir))
        self._indicator.set_menu(self._build_menu())

    def _build_menu(self) -> Gtk.Menu:
        """Build the indicator's right-click menu: a "start at login"
        checkbox, Restart (to pick up a config.toml edit without a
        terminal), and Quit."""
        menu = Gtk.Menu()

        autostart_item = Gtk.CheckMenuItem(label="Start at login")
        autostart_item.set_active(self._settings.autostart_enabled)
        autostart_item.connect("toggled", self._on_autostart_toggled)
        menu.append(autostart_item)

        menu.append(Gtk.SeparatorMenuItem())

        restart_item = Gtk.MenuItem(label="Restart")
        restart_item.connect("activate", lambda *_args: self._restart())
        menu.append(restart_item)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_args: self.shutdown())
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _on_autostart_toggled(self, item: Gtk.CheckMenuItem) -> None:
        """Persist the checkbox's new state and install/remove the actual
        autostart entry to match."""
        enabled = item.get_active()
        self._settings.autostart_enabled = enabled
        save_settings(self._settings)
        set_autostart_enabled(enabled)

    def _restart(self) -> None:
        """Re-exec the whole process in place. `os.execv` replaces the
        entire process image - including the poller's background thread -
        so there's nothing else to shut down first."""
        shutil.rmtree(self._icon_dir, ignore_errors=True)
        os.execv(sys.executable, [sys.executable, "-m", "glucose_widget.main"])

    def show_reading(self, reading: GlucoseReading, unit: GlucoseUnit) -> None:
        """Update the tray icon with a newly-fetched reading, colored by
        clinical range (red low / green normal / yellow high).

        Called from the poller's background thread, so the actual widget
        mutation is scheduled onto the GTK main loop via `GLib.idle_add`
        rather than done directly here.
        """
        text = self._format_reading(reading, unit)
        glucose_range = classify_mgdl(
            reading.value_mgdl,
            low_threshold=self._low_threshold,
            high_threshold=self._high_threshold,
        )
        GLib.idle_add(self._apply_icon, text, self._range_colors[glucose_range])

    def show_error(self, message: str) -> None:
        """Show that the latest poll failed. Same threading caveat as show_reading."""
        GLib.idle_add(self._apply_icon, "--", DEFAULT_TEXT_COLOR_RGBA)

    def run(self) -> None:
        """Block on the GTK main loop until `shutdown()` is called.

        A no-op if `shutdown()` already happened - see its docstring.
        """
        if self._quit_requested:
            return
        Gtk.main()

    def shutdown(self) -> None:
        """Stop the GTK main loop and clean up our temporary icon files.

        The Shell renders our tray menu independently of our own process,
        so "Quit" can be clicked - and this called - before `run()` has
        even started the main loop (e.g. while a startup credential dialog
        is still up). `Gtk.main_quit()` would raise if no loop is running,
        so it's only called when one actually is; `_quit_requested` makes
        sure `run()` still skips starting one afterwards.
        """
        self._quit_requested = True
        if Gtk.main_level() > 0:
            Gtk.main_quit()
        shutil.rmtree(self._icon_dir, ignore_errors=True)

    def _apply_icon(self, text: str, color: tuple[float, float, float, float]) -> bool:
        """GLib.idle_add callback: render `text` in `color` and set it as
        the indicator's icon. Returning False tells GLib not to call this
        again."""
        if self._quit_requested:
            return False
        icon_name = self._write_icon(text, color)
        self._indicator.set_icon_full(icon_name, text)
        return False

    def _write_icon(self, text: str, color: tuple[float, float, float, float]) -> str:
        """Render `text` in `color` to a PNG under a brand-new filename in
        our icon theme directory, delete the previous update's file, and
        return the new icon name (filename without extension) to pass to
        AppIndicator.

        Recreates the directory if it's missing (defensive: it's only ever
        removed by `shutdown()`, but guarding here means a stray extra
        write after shutdown can't crash with a confusing IOError).
        """
        self._icon_dir.mkdir(parents=True, exist_ok=True)

        self._update_counter += 1
        icon_name = f"reading-{self._update_counter}"
        render_text_icon(text, color).write_to_png(str(self._icon_dir / f"{icon_name}.png"))

        # Keep the current file and one prior (in case the Shell hasn't
        # finished reading the previous one yet) and delete anything older.
        self._recent_icon_names.append(icon_name)
        while len(self._recent_icon_names) > 2:
            (self._icon_dir / f"{self._recent_icon_names.pop(0)}.png").unlink(missing_ok=True)

        return icon_name

    @staticmethod
    def _format_reading(reading: GlucoseReading, unit: GlucoseUnit) -> str:
        """Render a reading as compact icon text, e.g. '118 →' or '6.6 ↑'."""
        value = reading.value_in(unit)
        value_text = f"{value:.0f}" if unit is GlucoseUnit.MGDL else f"{value:.1f}"
        return f"{value_text} {reading.trend.glyph}"
