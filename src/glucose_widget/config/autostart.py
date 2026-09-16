"""Manages the XDG autostart entry that launches this app at login.

Installing/removing `~/.config/autostart/glucose-widget.desktop` is exactly
what enables/disables autostart. That path is the standard XDG autostart
location on Ubuntu (and GNOME/most other Linux desktops generally), but
this project is only built and tested against Ubuntu.
"""

import sys
from pathlib import Path

from glucose_widget.ui.app_icon import app_icon_path

_AUTOSTART_DIR = Path.home() / ".config" / "autostart"
_DESKTOP_FILE_NAME = "glucose-widget.desktop"

# Purely cosmetic: exists to influence where this icon lands in the top
# bar, not sensor/API timing. Ubuntu's GNOME Shell AppIndicator extension
# inserts each new tray icon at a fixed position rather than appending, so
# indicators that register *later* tend to end up ahead of ones that
# registered earlier. Waiting here before launching - only on this
# autostart path, never when running from a terminal or the
# Applications-menu icon - gives other autostart tray apps a head start,
# with the goal of landing this icon at the left edge of the right-side
# icon group (immediately after the clock, ahead of things like
# wifi/bluetooth/volume). The exact result depends on how many other
# tray apps you have and how long they take to start, so this number may
# need tuning by hand - there's no config option for it (always applied;
# since it's a fixed value, regenerating this file on every startup is
# harmless - there's nothing a config option could preserve that this
# doesn't already produce).
_STARTUP_DELAY_SECONDS = 6


def autostart_desktop_path() -> Path:
    """Where the autostart entry lives, whether or not it's installed."""
    return _AUTOSTART_DIR / _DESKTOP_FILE_NAME


def set_autostart_enabled(enabled: bool) -> None:
    """Install or remove the autostart entry to match `enabled`."""
    if enabled:
        _AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
        autostart_desktop_path().write_text(_desktop_entry_content())
    else:
        autostart_desktop_path().unlink(missing_ok=True)


def _desktop_entry_content() -> str:
    """Build the .desktop file content.

    Exec points at the actual installed script next to the currently
    running interpreter, not just the bare command name "glucose-widget" -
    that name isn't guaranteed to be on PATH in a login session (e.g. when
    installed into a plain venv rather than via pipx). It's wrapped in a
    shell so `_STARTUP_DELAY_SECONDS` can run first.

    The Exec= key has its own quoting rules (it's not passed through a
    real shell) - only double quotes are recognized, and any literal
    double quote or backslash inside a quoted argument must itself be
    backslash-escaped. `exec` replaces the wrapping shell with the real
    process once the sleep is done, rather than leaving a shell parent
    hanging around.
    """
    exec_path = Path(sys.executable).with_name("glucose-widget")
    shell_command = f'sleep {_STARTUP_DELAY_SECONDS} && exec "{exec_path}"'
    escaped_shell_command = shell_command.replace("\\", "\\\\").replace('"', '\\"')
    exec_line = f'/bin/sh -c "{escaped_shell_command}"'
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Glucose Widget\n"
        f"Exec={exec_line}\n"
        f"Icon={app_icon_path()}\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Comment=Shows current blood glucose reading in the top bar\n"
    )
