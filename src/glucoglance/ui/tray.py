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

When a reading crosses out of range the icon also tries to catch the eye,
without sound or popups: it blinks (alternating a filled background with
the plain colored text) until the user acknowledges it - with the "Stop
blinking" menu item, which only appears while blinking, or by
middle-clicking the icon - or the reading comes back in range. Once
acknowledged it goes back to the plain colored text; the range color
alone is enough from then on. See `domain.range_tracker` for the
crossing/hysteresis logic.

Merely opening the menu deliberately does *not* stop the blinking, so
the "Stop blinking" item is still there to click. Hovering can't be
used either way: the Shell handles hover internally and never tells the
app.
"""

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
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

from glucoglance.config.autostart import set_autostart_enabled
from glucoglance.config.credentials import delete_password
from glucoglance.config.settings import Settings, save_settings
from glucoglance.domain.range import GlucoseRange
from glucoglance.domain.range_tracker import RangeState, RangeTracker
from glucoglance.domain.reading import GlucoseReading
from glucoglance.domain.units import GlucoseUnit
from glucoglance.ui.about_dialog import show_about
from glucoglance.ui.icon_renderer import (
    DEFAULT_TEXT_COLOR_RGBA,
    Rgba,
    parse_hex_color,
    render_text_icon,
)

_APP_ID = "glucoglance"
_PULSE_INTERVAL_MS = 500


@dataclass(frozen=True)
class _IconSpec:
    """Everything needed to render one tray icon frame."""

    text: str
    color: Rgba
    filled: bool = False


class TrayDisplay:
    """Displays glucose readings in the Ubuntu top bar via AppIndicator3/Ayatana."""

    def __init__(self, settings: Settings):
        self._settings = settings

        # Range thresholds and colors come from settings (config.toml) so
        # they're user-tunable without a code change; see classify_mgdl's
        # docstring for why the thresholds are always in mg/dL. The tracker
        # is only ever touched from the poller thread (in show_reading).
        self._range_tracker = RangeTracker(
            low_threshold=settings.low_threshold_mgdl,
            high_threshold=settings.high_threshold_mgdl,
            hysteresis_mgdl=settings.range_hysteresis_mgdl,
        )
        self._range_colors = {
            GlucoseRange.LOW: parse_hex_color(settings.color_low),
            GlucoseRange.NORMAL: parse_hex_color(settings.color_normal),
            GlucoseRange.HIGH: parse_hex_color(settings.color_high),
        }

        # Keep the actual autostart file in sync with the setting on every
        # startup - covers both a fresh install (setting defaults to True,
        # so this installs it immediately) and a manual config.toml edit.
        set_autostart_enabled(settings.autostart_enabled)

        self._icon_dir = Path(tempfile.mkdtemp(prefix="glucoglance-icons-"))
        # Confirmed live: GNOME Shell caches a tray icon bitmap by filename
        # and never re-reads it once that name has been seen, even after
        # the file's content changes - so a fixed/alternating set of names
        # just replays stale cached bitmaps. Every update instead gets a
        # brand-new, never-before-seen filename to guarantee a fresh read;
        # _write_icon() deletes older files right after. This applies to
        # the pulse too: confirmed live, switching back to an already-seen
        # name isn't redrawn at all, so every pulse frame is a new file.
        self._update_counter = 0
        self._recent_icon_names: list[str] = []
        # Pulse state, only touched on the GTK main loop: whether a crossing
        # is still waiting to be acknowledged, the running GLib timer, the
        # two frames to alternate between (plain, filled) and which one is
        # showing.
        self._pulse_pending = False
        self._pulse_timer_id: int | None = None
        self._pulse_frames: tuple[_IconSpec, _IconSpec] | None = None
        self._pulse_frame_index = 0
        # Set once shutdown() is called, even if it happens before run()
        # starts the main loop (see shutdown()'s docstring for why that can
        # happen) - lets run() skip entering the loop at all in that case.
        self._quit_requested = False

        self._indicator = AppIndicator3.Indicator.new(
            _APP_ID,
            self._write_icon(_IconSpec("--", DEFAULT_TEXT_COLOR_RGBA)),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_icon_theme_path(str(self._icon_dir))
        self._indicator.set_menu(self._build_menu())
        # Middle-clicking the icon "activates" this item directly, without
        # opening the menu - the one click the Shell forwards to the app
        # instead of handling itself.
        self._indicator.set_secondary_activate_target(self._stop_blinking_item)

    def _build_menu(self) -> Gtk.Menu:
        """Build the indicator's right-click menu: "GlucoGlance" (doubles as
        an About trigger), "Stop blinking" (only shown while blinking), a
        "start at login" checkbox, Restart (to pick up a config.toml edit
        without a terminal), Log out, and Quit."""
        menu = Gtk.Menu()

        about_item = Gtk.MenuItem(label="GlucoGlance")
        about_item.connect("activate", lambda *_args: show_about())
        menu.append(about_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Also the middle-click target (see __init__), which the label
        # mentions since there's no other way to discover that shortcut.
        # Shown/hidden together with its separator by _sync_stop_blinking_item().
        self._stop_blinking_item = Gtk.MenuItem(label="Stop blinking (middle-click)")
        self._stop_blinking_item.connect("activate", lambda *_args: self._acknowledge_highlight())
        menu.append(self._stop_blinking_item)
        self._stop_blinking_separator = Gtk.SeparatorMenuItem()
        menu.append(self._stop_blinking_separator)

        autostart_item = Gtk.CheckMenuItem(label="Start at login")
        autostart_item.set_active(self._settings.autostart_enabled)
        autostart_item.connect("toggled", self._on_autostart_toggled)
        menu.append(autostart_item)

        menu.append(Gtk.SeparatorMenuItem())

        restart_item = Gtk.MenuItem(label="Restart")
        restart_item.connect("activate", lambda *_args: self._restart())
        menu.append(restart_item)

        logout_item = Gtk.MenuItem(label="Log out")
        logout_item.connect("activate", lambda *_args: self._log_out())
        menu.append(logout_item)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_args: self.shutdown())
        menu.append(quit_item)

        menu.show_all()
        self._sync_stop_blinking_item()
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
        os.execv(sys.executable, [sys.executable, "-m", "glucoglance.main"])

    def _log_out(self) -> None:
        """Forget the stored LibreLinkUp credentials, then restart - the
        fresh process finds none stored and shows the login dialog again,
        reusing the same first-run flow rather than needing separate code
        for "log out and re-prompt"."""
        if self._settings.account_email:
            delete_password(self._settings.account_email)
            self._settings.account_email = None
            save_settings(self._settings)
        self._restart()

    def show_reading(self, reading: GlucoseReading, unit: GlucoseUnit) -> None:
        """Update the tray icon with a newly-fetched reading, colored by
        clinical range (red low / green normal / yellow high), plus the
        out-of-range highlight described in this module's docstring.

        Called from the poller's background thread, so the actual widget
        mutation is scheduled onto the GTK main loop via `GLib.idle_add`
        rather than done directly here.
        """
        state = self._range_tracker.update(reading)
        GLib.idle_add(self._apply_reading, self._format_reading(reading, unit), state)

    def show_error(self, message: str) -> None:
        """Show that the latest poll failed. Same threading caveat as
        show_reading. Deliberately plain: no fill, no pulse -
        an error means we don't know the current value, so nothing about
        the icon should suggest one."""
        GLib.idle_add(self._apply_error)

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

    def _apply_reading(self, text: str, state: RangeState) -> bool:
        """GLib.idle_add callback: show a reading's icon in its range color,
        blinking if it's out of range and the crossing hasn't been
        acknowledged yet. Returning False tells GLib not to call this
        again."""
        if self._quit_requested:
            return False
        self._stop_pulse_timer()

        color = self._range_colors[state.glucose_range]
        if not state.is_out_of_range:
            self._pulse_pending = False
        elif state.just_crossed and self._settings.highlight_pulse:
            self._pulse_pending = True

        plain = _IconSpec(text, color)
        if self._pulse_pending:
            # A new reading mid-blink re-renders both frames with the new value.
            self._start_pulse(plain, _IconSpec(text, color, filled=True))
        else:
            self._show_icon(plain)
        self._sync_stop_blinking_item()
        return False

    def _apply_error(self) -> bool:
        """GLib.idle_add callback: show the plain "--" error icon. An
        unacknowledged crossing stays pending, so blinking resumes if the
        next successful reading is still out of range."""
        if self._quit_requested:
            return False
        self._stop_pulse_timer()
        self._show_icon(_IconSpec("--", DEFAULT_TEXT_COLOR_RGBA))
        self._sync_stop_blinking_item()
        return False

    def _acknowledge_highlight(self) -> None:
        """Stop blinking until the next crossing, settling on the plain
        colored text. Called from the "Stop blinking" item (directly or via
        middle-click), on the main loop."""
        self._pulse_pending = False
        if self._pulse_timer_id is not None:
            self._stop_pulse_timer()
            if self._pulse_frame_index != 0 and self._pulse_frames is not None:
                self._show_icon(self._pulse_frames[0])
        self._sync_stop_blinking_item()

    def _sync_stop_blinking_item(self) -> None:
        """Show "Stop blinking" (and its separator) only while the icon is
        actually blinking - not e.g. while a poll error shows "--", even if
        blinking will resume after it."""
        blinking = self._pulse_timer_id is not None
        self._stop_blinking_item.set_visible(blinking)
        self._stop_blinking_separator.set_visible(blinking)

    def _show_icon(self, spec: _IconSpec) -> None:
        """Render `spec` under a fresh filename and make it the indicator's icon."""
        self._indicator.set_icon_full(self._write_icon(spec), spec.text)

    def _start_pulse(self, plain: _IconSpec, filled: _IconSpec) -> None:
        """Show `filled` and start alternating it with `plain` every
        _PULSE_INTERVAL_MS, until `_stop_pulse_timer()` is called. Frame
        index 0 is always the plain one, which is what acknowledging
        settles on."""
        self._pulse_frames = (plain, filled)
        self._pulse_frame_index = 1
        self._show_icon(filled)
        self._pulse_timer_id = GLib.timeout_add(_PULSE_INTERVAL_MS, self._on_pulse_tick)

    def _on_pulse_tick(self) -> bool:
        """GLib timer callback: show the other pulse frame. Returns whether
        GLib should keep calling it."""
        assert self._pulse_frames is not None
        if self._quit_requested:
            self._pulse_timer_id = None
            return False
        self._pulse_frame_index = 1 - self._pulse_frame_index
        self._show_icon(self._pulse_frames[self._pulse_frame_index])
        return True

    def _stop_pulse_timer(self) -> None:
        """Cancel the pulse timer, if one is running. Leaves
        `_pulse_pending` alone, so a later reading can resume blinking."""
        if self._pulse_timer_id is not None:
            GLib.source_remove(self._pulse_timer_id)
            self._pulse_timer_id = None

    def _write_icon(self, spec: _IconSpec) -> str:
        """Render `spec` to a PNG under a brand-new filename in our icon
        theme directory, delete older files, and return the new icon name
        (filename without extension) to pass to AppIndicator.

        Recreates the directory if it's missing (defensive: it's only ever
        removed by `shutdown()`, but guarding here means a stray extra
        write after shutdown can't crash with a confusing IOError).
        """
        self._icon_dir.mkdir(parents=True, exist_ok=True)

        self._update_counter += 1
        icon_name = f"reading-{self._update_counter}"
        surface = render_text_icon(spec.text, spec.color, filled=spec.filled)
        surface.write_to_png(str(self._icon_dir / f"{icon_name}.png"))

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
