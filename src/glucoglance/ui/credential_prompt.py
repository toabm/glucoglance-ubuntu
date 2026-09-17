"""Small one-off GTK dialogs: entering LibreLinkUp credentials, and reporting
a plain result (connected OK / failed, and why) back to the user.

Used on first run (no email/password known yet), again if the stored
password is later rejected by the API, and to surface the outcome of a
login attempt. Each dialog runs its own tiny nested GTK loop via
`Gtk.Dialog.run()`, so these work whether the app was launched from a
terminal or by the desktop autostart mechanism - there's no console to fall
back to in the latter case.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402 (import must follow gi.require_version)


def prompt_for_credentials(initial_email: str = "") -> tuple[str, str] | None:
    """Show a modal dialog asking for a LibreLinkUp email and password.

    Returns (email, password), or None if the user cancelled.
    """
    dialog = Gtk.Dialog(title="Connect to LibreLinkUp")
    dialog.add_buttons(
        Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
        Gtk.STOCK_OK, Gtk.ResponseType.OK,
    )
    dialog.set_default_size(320, 0)

    content = dialog.get_content_area()
    content.set_spacing(8)
    content.set_border_width(12)

    email_entry = Gtk.Entry()
    email_entry.set_placeholder_text("LibreLinkUp email")
    email_entry.set_text(initial_email)
    content.add(email_entry)

    password_entry = Gtk.Entry()
    password_entry.set_placeholder_text("Password")
    password_entry.set_visibility(False)
    password_entry.set_activates_default(True)
    content.add(password_entry)

    dialog.set_default_response(Gtk.ResponseType.OK)
    dialog.show_all()

    response = dialog.run()
    email = email_entry.get_text().strip()
    password = password_entry.get_text()
    dialog.destroy()

    if response != Gtk.ResponseType.OK or not email or not password:
        return None
    return email, password


def show_message(text: str, *, is_error: bool = False) -> None:
    """Show a simple OK-only dialog reporting a result to the user - used so
    connecting to LibreLinkUp gives visible feedback instead of only the
    tray icon quietly changing to an error glyph."""
    dialog = Gtk.MessageDialog(
        message_type=Gtk.MessageType.ERROR if is_error else Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text="Couldn't connect to LibreLinkUp" if is_error else "LibreLinkUp",
    )
    dialog.format_secondary_text(text)
    dialog.run()
    dialog.destroy()
