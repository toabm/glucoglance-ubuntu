"""Entry point: wires the LibreLinkUp client, the background poller, and the
tray display together, and handles first-run/credential-refresh prompts.

This module is intentionally the only place that knows about all the other
packages at once - client, poller, ui, and config are each independently
testable and don't import each other except through the small interfaces
(`ReadingSource`, `Display`, `PollerEvent`) defined for exactly that purpose.
"""

import logging
import signal
import sys

import gi

# Pinned here, before anything else touches `gi`, so that whichever module
# happens to import Gtk first doesn't lock in the OS default version (Ubuntu
# ships Gtk 4 as the default) instead of the Gtk 3 the tray/dialog code needs.
gi.require_version("Gtk", "3.0")

from gi.repository import GLib  # noqa: E402 (must follow gi.require_version)

from glucose_widget.client.errors import AuthError, NetworkError, StaleDataError
from glucose_widget.client.librelinkup import LibreLinkUpClient
from glucose_widget.config.credentials import get_password, set_password
from glucose_widget.config.settings import Settings, load_settings, save_settings
from glucose_widget.poller.poller import EventBus, GlucosePoller, PollError, ReadingUpdated
from glucose_widget.ui.credential_prompt import prompt_for_credentials, show_message
from glucose_widget.ui.tray import TrayDisplay

logger = logging.getLogger(__name__)


class Application:
    """Owns the long-lived pieces of the running app and wires them together."""

    def __init__(self):
        self.settings: Settings = load_settings()
        self.display = TrayDisplay(self.settings)
        self.client: LibreLinkUpClient | None = None
        self.poller: GlucosePoller | None = None

    def start(self) -> None:
        """Obtain credentials, start polling, and block on the tray's main loop."""
        self._ensure_client()
        self._start_poller()
        self._install_signal_handlers()
        self.display.run()
        if self.poller is not None:
            self.poller.stop()

    def _ensure_client(self) -> None:
        """Make sure we have a working LibreLinkUpClient: prompt for
        credentials if none are stored yet, and actually try a request
        before proceeding so a login *failure* is reported to the user
        immediately rather than only showing up later as a tray glyph.

        Success is only announced with a popup when credentials were just
        typed in this run (`prompted`) - a normal startup with already-saved
        credentials stays silent and just shows the reading in the tray.
        """
        email = self.settings.account_email
        password = get_password(email) if email else None
        prompted = False

        while True:
            if not email or not password:
                credentials = prompt_for_credentials(email or "")
                if credentials is None:
                    sys.exit("LibreLinkUp credentials are required to run this app.")
                email, password = credentials
                prompted = True

            client = LibreLinkUpClient(email, password, base_host=self.settings.base_host)
            if self._verify_client(client, announce_success=prompted):
                self._save_credentials(email, password)
                self.client = client
                return

            # Credentials were rejected outright - clear them so the loop
            # re-prompts instead of retrying the same ones.
            email, password = None, None

    def _verify_client(self, client: LibreLinkUpClient, *, announce_success: bool) -> bool:
        """Make one real request with `client`. Always reports a login
        failure (the user needs to act on that); only reports success when
        `announce_success` is set, so a routine startup with credentials
        that already worked doesn't pop up a dialog for no reason.

        Returns True if the client is usable going forward (even if this
        particular request hit a transient/no-data issue), False if the
        credentials themselves were rejected.
        """
        try:
            client.get_latest_reading()
        except AuthError as exc:
            show_message(
                f"Login failed: {exc}\n\nCheck your LibreLinkUp email and password.",
                is_error=True,
            )
            return False
        except (NetworkError, StaleDataError) as exc:
            if announce_success:
                show_message(
                    f"Logged in, but couldn't fetch a reading yet:\n{exc}\n\n"
                    "This will keep retrying in the background."
                )
            return True
        else:
            if announce_success:
                show_message("Connected to LibreLinkUp successfully.")
            return True

    def _start_poller(self) -> None:
        """Create a fresh poller for the current client and subscribe our
        event handler to it."""
        assert self.client is not None
        bus = EventBus()
        bus.subscribe(self._handle_event)
        self.poller = GlucosePoller(
            self.client,
            interval_seconds=self.settings.interval_seconds,
            bus=bus,
        )
        self.poller.start()

    def _handle_event(self, event) -> None:
        """Adapt a poller event into a Display call (runs on the poller's
        background thread)."""
        if isinstance(event, ReadingUpdated):
            logger.info(
                "Reading updated: %s mg/dL, trend=%s",
                event.reading.value_mgdl,
                event.reading.trend.name,
            )
            self.display.show_reading(event.reading, self.settings.unit)
            self._remember_resolved_host()
        elif isinstance(event, PollError):
            logger.warning(
                "Poll failed (%d consecutive): %s", event.consecutive_failures, event.error
            )
            self.display.show_error(str(event.error))
            if isinstance(event.error, AuthError):
                # Marshal onto the main loop since this rebuilds the poller.
                GLib.idle_add(self._reauthenticate)

    def _remember_resolved_host(self) -> None:
        """Persist the client's (possibly region-redirected) host so future
        runs skip the redirect round trip."""
        assert self.client is not None
        if self.client.base_host != self.settings.base_host:
            self.settings.base_host = self.client.base_host
            save_settings(self.settings)

    def _reauthenticate(self) -> bool:
        """Stop the current poller, ask for fresh credentials, and restart
        once they're confirmed to work. Runs on the main loop; returns
        False so GLib doesn't call it again."""
        assert self.poller is not None
        self.poller.stop()

        while True:
            credentials = prompt_for_credentials(self.settings.account_email or "")
            if credentials is None:
                self.display.shutdown()
                return False

            email, password = credentials
            client = LibreLinkUpClient(email, password)
            if self._verify_client(client, announce_success=True):
                self._save_credentials(email, password)
                self.client = client
                self._start_poller()
                return False

    def _save_credentials(self, email: str, password: str) -> None:
        """Store the email in settings and the password in the system keyring."""
        set_password(email, password)
        self.settings.account_email = email
        save_settings(self.settings)

    def _install_signal_handlers(self) -> None:
        """Let Ctrl-C / a service manager stop us as cleanly as the tray's
        own Quit menu item does."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self._on_terminate_signal)

    def _on_terminate_signal(self) -> bool:
        self.display.shutdown()
        return False


def main() -> None:
    """Console-script entry point (see pyproject.toml)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    Application().start()


if __name__ == "__main__":
    main()
