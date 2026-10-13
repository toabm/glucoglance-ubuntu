"""The "About" dialog, shown when clicking the tray menu's "GlucoGlance"
entry - that entry doubles as both the menu's title and the About trigger,
rather than having a separate disabled header plus a separate About item.
"""

from importlib.metadata import PackageNotFoundError, version

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk  # noqa: E402 (import must follow gi.require_version)

from glucoglance.ui.app_icon import tray_icon_path
from glucoglance.ui.disclaimer import DISCLAIMER

_MAINTAINER_EMAIL = "toabm@yahoo.es"
_REPO_URL = "https://github.com/toabm/glucoglance-ubuntu"
# Width of the app's mark in the dialog's top-left corner (it's wider than tall).
_ICON_WIDTH = 64
_SUMMARY = (
    "GlucoGlance shows your current glucose reading, from a FreeStyle "
    "Libre sensor via LibreLinkUp, right in your Ubuntu tray."
)


def show_about() -> None:
    """Show a simple dialog with the app's summary, version, repo,
    maintainer contact, license, and the medical/affiliation disclaimer.

    Shows the app's own small eye/gauge/drop mark in the corner instead of
    GTK's generic "i" info icon: MessageType.OTHER has no stock icon, and
    set_image() supplies ours. (set_image is deprecated in GTK 3 but still
    works; if the icon can't be loaded, the dialog just has no image.)
    """
    dialog = Gtk.MessageDialog(
        message_type=Gtk.MessageType.OTHER,
        buttons=Gtk.ButtonsType.OK,
        text="GlucoGlance",
    )
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(tray_icon_path()), _ICON_WIDTH, -1, True)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        image.show()
        dialog.set_image(image)
    except GLib.Error:
        pass
    dialog.format_secondary_text(
        f"{_SUMMARY}\n\n"
        f"Version: {_installed_version()}\n"
        f"Repository: {_REPO_URL}\n"
        f"Contact: {_MAINTAINER_EMAIL}\n"
        f"License: MIT\n\n"
        f"{DISCLAIMER}"
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
