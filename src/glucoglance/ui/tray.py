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
the plain colored text) for up to 20 minutes, then stays filled, until
the user acknowledges it - with the menu item that only appears while
highlighted ("Stop blinking", or "Clear highlight" once it's steady), or
by middle-clicking the icon - or the reading comes back in range. Once
acknowledged it goes back to the plain colored text; the range color
alone is enough from then on. See `domain.range_tracker` for the
crossing/hysteresis logic.

When a poll produces no reading, no number is shown at all: the icon
becomes the app's own eye/gauge/drop mark with a red eye
(`assets/tray-icon-error.svg`), and a greyed line at the top of the menu
says why ("No data: can't reach LibreLinkUp", etc.). Before the first
reading arrives, the icon is the same mark in its normal colors.

Merely opening the menu deliberately does *not* stop the highlight, so
its menu item is still there to click. Hovering can't be
used either way: the Shell handles hover internally and never tells the
app.
"""

import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import cairo
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
from glucoglance.ui.app_icon import tray_icon_path
from glucoglance.ui.display import NoDataReason
from glucoglance.ui.icon_renderer import (
    DEFAULT_TEXT_COLOR_RGBA,
    Rgba,
    parse_hex_color,
    render_image_icon,
    render_text_icon,
)

_APP_ID = "glucoglance"
_PULSE_INTERVAL_MS = 500
# How long a crossing blinks before settling on the steady filled icon.
_BLINK_DURATION_S = 20 * 60
_STOP_BLINKING_LABEL = "Stop blinking (middle-click)"
_CLEAR_HIGHLIGHT_LABEL = "Clear highlight (middle-click)"
# Drawn instead of the app's mark if its icon file can't be loaded.
_NO_DATA_FALLBACK_TEXT = "--"
# Sizes the icon shown before the first reading arrives; see _no_data_icon_spec.
_TYPICAL_READING_TEXT = "000 →"
_WAITING_DESCRIPTION = "GlucoGlance: waiting for the first reading"
# The menu's reason line during an error (also the icon's accessible text).
_NO_DATA_DESCRIPTIONS = {
    NoDataReason.NETWORK: "No data: can't reach LibreLinkUp",
    NoDataReason.STALE_DATA: "No data: no recent sensor reading",
    NoDataReason.AUTH: "No data: login needed",
    NoDataReason.OTHER: "No data: unexpected error",
}


@dataclass(frozen=True)
class _IconSpec:
    """Everything needed to render one tray icon frame. With `image_path`
    set, that image is drawn instead of `text` (which stays the fallback
    if it can't be loaded)."""

    text: str
    color: Rgba
    filled: bool = False
    min_width: int = 0
    image_path: Path | None = None
    # Accessible description; defaults to `text`.
    description: str | None = None


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
        # _write_icon() deletes older files right after.
        #
        # That also rules out blinking by alternating two icon names:
        # switching back to an already-seen name isn't redrawn at all
        # (confirmed live). Instead, each highlighted reading gets one
        # fresh pair - plain as the normal icon, filled as the *attention*
        # icon - and blinking toggles the indicator's status between ACTIVE
        # and ATTENTION, which the Shell does redraw every time (confirmed
        # live), so blinking itself creates no new names. An earlier
        # version wrote a new file per 500 ms frame instead, and
        # gnome-shell held on to ~12 MB per 30 minutes of blinking, never
        # freed; with the status toggle its memory stayed flat.
        self._update_counter = 0
        self._recent_icon_names: list[str] = []
        # Width of the last icon written; "no data" icons are padded to it
        # (see _no_data_icon_spec).
        self._last_icon_width = render_text_icon(_TYPICAL_READING_TEXT).get_width()
        # Highlight state, only touched on the GTK main loop: whether a
        # crossing is still waiting to be acknowledged, when its blinking
        # phase ends (a time.monotonic() value), the running blink timer,
        # and whether the indicator's status is currently ATTENTION.
        self._highlight_pending = False
        self._blink_deadline = 0.0
        self._pulse_timer_id: int | None = None
        self._attention_shown = False
        # Set once shutdown() is called, even if it happens before run()
        # starts the main loop (see shutdown()'s docstring for why that can
        # happen) - lets run() skip entering the loop at all in that case.
        self._quit_requested = False

        self._indicator = AppIndicator3.Indicator.new(
            _APP_ID,
            self._write_icon(self._no_data_icon_spec(None)),
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_icon_theme_path(str(self._icon_dir))
        self._indicator.set_menu(self._build_menu())
        # Middle-clicking the icon "activates" this item directly, without
        # opening the menu - the one click the Shell forwards to the app
        # instead of handling itself.
        self._indicator.set_secondary_activate_target(self._acknowledge_item)

    def _build_menu(self) -> Gtk.Menu:
        """Build the indicator's right-click menu: "GlucoGlance" (doubles as
        an About trigger), "Stop blinking"/"Clear highlight" (only shown
        while highlighted), a
        "start at login" checkbox, Restart (to pick up a config.toml edit
        without a terminal), Log out, and Quit."""
        menu = Gtk.Menu()

        about_item = Gtk.MenuItem(label="GlucoGlance")
        about_item.connect("activate", lambda *_args: show_about())
        menu.append(about_item)

        # Why there's no reading; only shown during an error, greyed out
        # since it's information, not an action (see _sync_no_data_item).
        self._no_data_item = Gtk.MenuItem(label="")
        self._no_data_item.set_sensitive(False)
        menu.append(self._no_data_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Also the middle-click target (see __init__), which the label
        # mentions since there's no other way to discover that shortcut.
        # Shown/hidden (and relabeled) together with its separator by
        # _sync_acknowledge_item().
        self._acknowledge_item = Gtk.MenuItem(label=_STOP_BLINKING_LABEL)
        self._acknowledge_item.connect("activate", lambda *_args: self._acknowledge_highlight())
        menu.append(self._acknowledge_item)
        self._acknowledge_separator = Gtk.SeparatorMenuItem()
        menu.append(self._acknowledge_separator)

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
        self._sync_acknowledge_item(visible=False, blinking=False)
        self._sync_no_data_item(None)
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

    def show_error(self, reason: NoDataReason, message: str) -> None:
        """Show that the latest poll produced no reading: the red-eye icon,
        plus `reason` in the menu. Same threading caveat as show_reading.
        Deliberately no number and no blinking - we don't know the current
        value, so nothing about the icon should suggest one."""
        GLib.idle_add(self._apply_error, reason)

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
        highlighted if it's out of range and the crossing hasn't been
        acknowledged yet. Returning False tells GLib not to call this
        again."""
        if self._quit_requested:
            return False

        color = self._range_colors[state.glucose_range]
        if not state.is_out_of_range:
            self._highlight_pending = False
        elif state.just_crossed and self._settings.highlight_pulse:
            # A new crossing (re)starts the blinking phase.
            self._highlight_pending = True
            self._blink_deadline = time.monotonic() + _BLINK_DURATION_S

        self._indicator.set_icon_full(self._write_icon(_IconSpec(text, color)), text)
        if self._highlight_pending:
            # A new pair of names per reading; the running blink (if any)
            # just carries on with the new value.
            filled = _IconSpec(text, color, filled=True)
            self._indicator.set_attention_icon_full(self._write_icon(filled), text)
        self._sync_highlight()
        self._sync_no_data_item(None)
        return False

    def _apply_error(self, reason: NoDataReason) -> bool:
        """GLib.idle_add callback: show the red-eye "no data" icon and the
        reason in the menu. An unacknowledged crossing stays pending, so the
        highlight resumes (blinking or steady, depending on how long it's
        been) if the next successful reading is still out of range."""
        if self._quit_requested:
            return False
        self._stop_pulse_timer()
        # Icon first, then the status: the other order would briefly show
        # the old reading's plain icon.
        self._show_icon(self._no_data_icon_spec(reason))
        self._set_attention(False)
        self._sync_acknowledge_item(visible=False, blinking=False)
        self._sync_no_data_item(reason)
        return False

    def _acknowledge_highlight(self) -> None:
        """Clear the highlight until the next crossing, settling on the
        plain colored text. Called from the menu item (directly or via
        middle-click), on the main loop."""
        self._highlight_pending = False
        self._sync_highlight()

    def _sync_highlight(self) -> None:
        """Bring the blink timer, the indicator's status and the menu item
        in line with the highlight state: blinking until the deadline, then
        the steady filled (attention) icon, until acknowledged."""
        blinking = self._highlight_pending and time.monotonic() < self._blink_deadline
        if blinking:
            if self._pulse_timer_id is None:
                self._set_attention(True)
                self._pulse_timer_id = GLib.timeout_add(_PULSE_INTERVAL_MS, self._on_pulse_tick)
        else:
            self._stop_pulse_timer()
            self._set_attention(self._highlight_pending)
        self._sync_acknowledge_item(visible=self._highlight_pending, blinking=blinking)

    def _sync_acknowledge_item(self, *, visible: bool, blinking: bool) -> None:
        """Show the acknowledge item (and its separator) only while the
        icon is actually highlighted - not e.g. while a poll error shows "no
        data", even if the highlight will resume after it - labeled for
        what clicking it will stop."""
        self._acknowledge_item.set_label(_STOP_BLINKING_LABEL if blinking else _CLEAR_HIGHLIGHT_LABEL)
        self._acknowledge_item.set_visible(visible)
        self._acknowledge_separator.set_visible(visible)

    def _sync_no_data_item(self, reason: NoDataReason | None) -> None:
        """Show the menu's reason line for `reason`, or hide it (None)."""
        if reason is not None:
            self._no_data_item.set_label(_NO_DATA_DESCRIPTIONS[reason])
        self._no_data_item.set_visible(reason is not None)

    def _no_data_icon_spec(self, reason: NoDataReason | None) -> _IconSpec:
        """The app's own mark, for when there's no reading to show: the
        red-eye variant for an error (`reason`), or the normal one before
        the first reading (None). Padded to the width of the icon it
        replaces.

        Why the padding matters - seen live with the earlier "--" icon
        (GNOME Shell 46 + ubuntu-appindicators): switching from a reading
        (e.g. 61x32) to a bare, narrow "--" (24x32) could leave the
        previous image drawn underneath - a stale "74" with "--" over it,
        i.e. showing a reading we no longer have - and the reverse switch
        left "--" under the next reading. With "--" padded to the same
        width, repeated error/recovery cycles (including mid-blink) came out
        clean. The likely cause is the extension changing how it sizes the
        icon's slot below a 1.5:1 aspect ratio; either way, never letting
        the width jump avoids it (and stops neighboring tray icons shifting
        sideways on errors). The mark is just as narrow, so the same padding
        applies to it.
        """
        return _IconSpec(
            _NO_DATA_FALLBACK_TEXT,
            DEFAULT_TEXT_COLOR_RGBA,
            min_width=self._last_icon_width,
            image_path=tray_icon_path(error=reason is not None),
            description=_WAITING_DESCRIPTION if reason is None else _NO_DATA_DESCRIPTIONS[reason],
        )

    def _show_icon(self, spec: _IconSpec) -> None:
        """Render `spec` under a fresh filename and make it the indicator's icon."""
        self._indicator.set_icon_full(self._write_icon(spec), spec.description or spec.text)

    def _set_attention(self, on: bool) -> None:
        """Switch the indicator between its attention icon (the filled
        frame) and its normal icon, via its status."""
        if on != self._attention_shown:
            self._attention_shown = on
            status = AppIndicator3.IndicatorStatus.ATTENTION if on else AppIndicator3.IndicatorStatus.ACTIVE
            self._indicator.set_status(status)

    def _on_pulse_tick(self) -> bool:
        """GLib timer callback: flip between the plain and filled icons, or
        settle on the filled one once the blinking phase is over. Returns
        whether GLib should keep calling it."""
        if self._quit_requested:
            self._pulse_timer_id = None
            return False
        if time.monotonic() >= self._blink_deadline:
            self._pulse_timer_id = None
            self._sync_highlight()
            return False
        self._set_attention(not self._attention_shown)
        return True

    def _stop_pulse_timer(self) -> None:
        """Cancel the pulse timer, if one is running. Leaves
        `_highlight_pending` alone, so a later reading can resume it."""
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
        surface = self._render(spec)
        surface.write_to_png(str(self._icon_dir / f"{icon_name}.png"))
        self._last_icon_width = surface.get_width()

        # Keep the current (plain, filled) pair and the one before it (in
        # case the Shell hasn't finished reading those yet) and delete
        # anything older.
        self._recent_icon_names.append(icon_name)
        while len(self._recent_icon_names) > 4:
            (self._icon_dir / f"{self._recent_icon_names.pop(0)}.png").unlink(missing_ok=True)

        return icon_name

    @staticmethod
    def _render(spec: _IconSpec) -> cairo.ImageSurface:
        """Draw `spec`: its image if it has one, falling back to its text
        if that file can't be loaded."""
        if spec.image_path is not None:
            try:
                return render_image_icon(spec.image_path, min_width=spec.min_width)
            except GLib.Error:
                pass
        return render_text_icon(spec.text, spec.color, filled=spec.filled, min_width=spec.min_width)

    @staticmethod
    def _format_reading(reading: GlucoseReading, unit: GlucoseUnit) -> str:
        """Render a reading as compact icon text, e.g. '118 →' or '6.6 ↑'."""
        value = reading.value_in(unit)
        value_text = f"{value:.0f}" if unit is GlucoseUnit.MGDL else f"{value:.1f}"
        return f"{value_text} {reading.trend.glyph}"
