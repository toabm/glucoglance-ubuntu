"""The "About" dialog, shown when clicking the tray menu's "GlucoGlance"
entry - that entry doubles as both the menu's title and the About trigger,
rather than having a separate disabled header plus a separate About item.
"""

from importlib.metadata import PackageNotFoundError, version

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402 (import must follow gi.require_version)

_MAINTAINER_EMAIL = "toabm@yahoo.es"
_REPO_URL = "https://github.com/toabm/glucoglance-ubuntu"
_SUMMARY = (
    "GlucoGlance shows your current glucose reading, from a FreeStyle "
    "Libre sensor via LibreLinkUp, right in your Ubuntu tray."
)


def show_about() -> None:
    """Show a simple dialog with the app's summary, version, repo, and
    maintainer contact."""
    dialog = Gtk.MessageDialog(
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text="GlucoGlance",
    )
    dialog.format_secondary_text(
        f"{_SUMMARY}\n\n"
        f"Version: {_installed_version()}\n"
        f"Repository: {_REPO_URL}\n"
        f"Contact: {_MAINTAINER_EMAIL}"
    )
    dialog.run()
    dialog.destroy()


def _installed_version() -> str:
    """Read the installed package version straight from its metadata
    (pyproject.toml's `version`), so this never drifts out of sync."""
    try:
        return version("glucoglance")
    except PackageNotFoundError:
        return "unknown"
