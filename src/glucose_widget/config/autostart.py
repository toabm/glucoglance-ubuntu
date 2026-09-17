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

# Cosmetic only: GNOME's AppIndicator extension inserts new tray icons
# ahead of existing ones rather than appending, so this delay lets other
# autostart tray apps register first, aiming to land us at the left edge
# of the right-side icon group. Not user-configurable; tune by hand.
#
# Applied via X-GNOME-Autostart-Delay (native gnome-session-binary key),
# not a shell-wrapped Exec=. A `sh -c "sleep N && exec \"...\""` version
# passed desktop-file-validate but was rejected at real login by both
# systemd-xdg-autostart-generator and gnome-session-binary (confirmed via
# journalctl) - their Exec= parsers are stricter than the validator.
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
    installed into a plain venv rather than via pipx). See
    `_STARTUP_DELAY_SECONDS` above for why the delay is a separate key
    rather than part of this Exec= value.
    """
    exec_path = Path(sys.executable).with_name("glucose-widget")
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Glucose Widget\n"
        f"Exec={exec_path}\n"
        f"Icon={app_icon_path()}\n"
        "X-GNOME-Autostart-enabled=true\n"
        f"X-GNOME-Autostart-Delay={_STARTUP_DELAY_SECONDS}\n"
        "Comment=Shows current blood glucose reading in the top bar\n"
    )
