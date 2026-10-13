"""The notice shown when GlucoGlance is started while it's already running.

Shown by the second copy, just before it exits (see `instance_lock.py`).
It's often started from the Applications menu or the Dock, where there's
no terminal to print to, so it has to be a dialog - and one that points
the user at the copy that's already in the top bar, rather than reading
like an error.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk  # noqa: E402 (import must follow gi.require_version)

from glucoglance.ui.app_icon import app_icon_path

_ICON_SIZE = 64


def show_already_running() -> None:
    """Tell the user GlucoGlance is already running and where to find it.

    Uses the app icon in the corner, like the About dialog does with the
    tray mark: MessageType.OTHER has no stock icon, and set_image()
    supplies ours (deprecated in GTK 3 but still works; if the icon can't
    be loaded, the dialog just has no image).
    """
    dialog = Gtk.MessageDialog(
        message_type=Gtk.MessageType.OTHER,
        buttons=Gtk.ButtonsType.OK,
        text="GlucoGlance is already running",
    )
    dialog.set_title("GlucoGlance")
    dialog.set_position(Gtk.WindowPosition.CENTER)
    # There's no parent window to stay on top of, so make sure it isn't
    # hidden behind whatever the user launched it from.
    dialog.set_keep_above(True)
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(app_icon_path()), _ICON_SIZE, _ICON_SIZE, True
        )
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        image.show()
        dialog.set_image(image)
    except GLib.Error:
        pass
    dialog.format_secondary_text(
        "Its icon is already in the top bar, on the right.\n\n"
        "Right-click it for the menu, or choose Restart there to reload "
        "the app."
    )
    dialog.run()
    dialog.destroy()
