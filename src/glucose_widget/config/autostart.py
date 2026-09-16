"""Manages the XDG autostart entry that launches this app at login.

Installing/removing `~/.config/autostart/glucose-widget.desktop` is exactly
what enables/disables autostart under GNOME (and other XDG-compliant
desktops) - no other system integration is needed.
"""

import sys
from pathlib import Path

from glucose_widget.ui.app_icon import app_icon_path

_AUTOSTART_DIR = Path.home() / ".config" / "autostart"
_DESKTOP_FILE_NAME = "glucose-widget.desktop"


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
    installed into a plain venv rather than via pipx).
    """
    exec_path = Path(sys.executable).with_name("glucose-widget")
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Glucose Widget\n"
        f"Exec={exec_path}\n"
        f"Icon={app_icon_path()}\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Comment=Shows current blood glucose reading in the top bar\n"
    )
