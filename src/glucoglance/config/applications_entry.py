"""Manages the per-user Applications-menu entry for launching the app by hand.

Installing/removing `~/.local/share/applications/glucoglance.desktop` is
exactly what shows/hides GlucoGlance in GNOME's Activities overview and
app search (from where it can also be pinned to the Dock). GNOME watches
that directory, so the change shows up without logging out.

This is separate from the autostart entry (`autostart.py`): normally the
app starts by itself at login, and this launcher is only for starting it
again by hand, e.g. after choosing "Quit".

The file name matches the one the .deb installs system-wide under
`/usr/share/applications`, on purpose: both then have the same desktop ID,
so a per-user entry overrides the system one instead of adding a second
launcher. For the same reason, the tray hides its menu toggle when a
system-wide entry exists (`system_entry_installed()`) - removing the
per-user file there would not remove the launcher, just reveal the
system one.
"""

import os
from pathlib import Path

from glucoglance.config.autostart import app_exec_path
from glucoglance.ui.app_icon import app_icon_path

_APPLICATIONS_DIR = Path.home() / ".local" / "share" / "applications"
_DESKTOP_FILE_NAME = "glucoglance.desktop"
# Used when XDG_DATA_DIRS is unset or empty, per the XDG Base Directory spec.
_DEFAULT_XDG_DATA_DIRS = "/usr/local/share:/usr/share"


def applications_entry_path() -> Path:
    """Where the per-user entry lives, whether or not it's installed."""
    return _APPLICATIONS_DIR / _DESKTOP_FILE_NAME


def is_applications_entry_installed() -> bool:
    """Whether the per-user entry currently exists."""
    return applications_entry_path().exists()


def set_applications_entry_installed(installed: bool) -> None:
    """Install or remove the per-user entry to match `installed`."""
    if installed:
        _APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
        applications_entry_path().write_text(_desktop_entry_content())
    else:
        applications_entry_path().unlink(missing_ok=True)


def refresh_applications_entry() -> None:
    """Rewrite the per-user entry if it exists, so its Exec= and Icon=
    paths follow the currently running install (e.g. after a reinstall
    into a different venv). Does nothing if it isn't installed."""
    if is_applications_entry_installed():
        set_applications_entry_installed(True)


def system_entry_installed() -> bool:
    """Whether a system-wide entry with the same desktop ID exists in any
    of the XDG data directories (e.g. from the .deb)."""
    data_dirs = os.environ.get("XDG_DATA_DIRS") or _DEFAULT_XDG_DATA_DIRS
    return any(
        (Path(data_dir) / "applications" / _DESKTOP_FILE_NAME).exists()
        for data_dir in data_dirs.split(":")
        if data_dir
    )


def _desktop_entry_content() -> str:
    """Build the .desktop file content. See `app_exec_path()` for why
    Exec= is an absolute path rather than the bare command name."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=GlucoGlance\n"
        "Comment=Shows current blood glucose reading in the top bar\n"
        f"Exec={app_exec_path()}\n"
        f"Icon={app_icon_path()}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "Keywords=glucose;libre;librelinkup;cgm;tray;\n"
    )
