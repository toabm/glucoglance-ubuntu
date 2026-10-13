"""Run GlucoGlance against a fake glucose value you control, for manually
testing the tray (colors, the out-of-range blink, acknowledging it, error
display) without waiting for your real glucose to cooperate.

Usage, from the repo root with the venv active:

    python scripts/run_with_fake_reading.py            # starts at 120 mg/dL
    python scripts/run_with_fake_reading.py --value 74 --interval 3

Then, from another terminal, change what the next poll returns by writing
to the value file (its path is printed at startup):

    echo 74 > "$XDG_RUNTIME_DIR/glucoglance-fake-reading"     # low
    echo "200 4" > "$XDG_RUNTIME_DIR/glucoglance-fake-reading"  # high, rising
    echo 120 > "$XDG_RUNTIME_DIR/glucoglance-fake-reading"    # back in range
    echo error > "$XDG_RUNTIME_DIR/glucoglance-fake-reading"  # network failure
    echo stale > "$XDG_RUNTIME_DIR/glucoglance-fake-reading"  # no recent reading
    echo auth > "$XDG_RUNTIME_DIR/glucoglance-fake-reading"   # login rejected

The optional second number is the trend, as the API encodes it (1-5,
1 = rapidly falling, 3 = stable, 5 = rapidly rising). Values are always
in mg/dL, like the API, whatever display unit config.toml selects.

This is a test harness, so it's careful not to change anything real: no
LibreLinkUp login or network access, no keyring access (so no credential
prompt - not even for a simulated "auth" failure - and the tray's "Log
out" does nothing), no writes to config.toml
(your saved settings are still read, e.g. thresholds, colors and unit),
and no changes to the autostart entry. The tray's "Restart" re-runs this
script rather than the real app. The icon can appear alongside a running
real GlucoGlance.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import glucoglance.main as app_main
import glucoglance.ui.tray as tray
from glucoglance.client.errors import AuthError, NetworkError, StaleDataError
from glucoglance.domain.range import DEFAULT_HIGH_THRESHOLD_MGDL, DEFAULT_LOW_THRESHOLD_MGDL
from glucoglance.domain.reading import GlucoseReading
from glucoglance.domain.trend import TrendArrow

logger = logging.getLogger("fake_reading")

DEFAULT_VALUE_FILE = (
    Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "glucoglance-fake-reading"
)


class FakeReadingClient:
    """Stands in for LibreLinkUpClient: every `get_latest_reading()` call
    re-reads the value file, so edits take effect on the next poll."""

    def __init__(self, value_file: Path, base_host: str | None):
        self._value_file = value_file
        # Application._remember_resolved_host() reads this after every
        # reading; echoing the configured host back means "nothing to save".
        self.base_host = base_host

    def get_latest_reading(self) -> GlucoseReading:
        """Build a reading from the value file's "<mg/dL> [trend]" contents,
        or raise the matching client error for "error" (network), "stale" or
        "auth" - the same error path as a real failed poll. Anything
        unparseable counts as a network error."""
        raw = self._value_file.read_text().split()
        keyword = raw[0].lower() if raw else "error"
        if keyword == "error":
            raise NetworkError("simulated network failure (value file says 'error')")
        if keyword == "stale":
            raise StaleDataError("simulated stale data (value file says 'stale')")
        if keyword == "auth":
            raise AuthError("simulated login failure (value file says 'auth')")
        try:
            value = int(raw[0])
            trend = TrendArrow.from_api_value(raw[1]) if len(raw) > 1 else TrendArrow.STABLE
        except ValueError as exc:
            raise NetworkError(f"unparseable value file contents: {raw!r}") from exc
        return GlucoseReading(
            value_mgdl=value,
            trend=trend,
            timestamp=datetime.now(),
            is_high=value > DEFAULT_HIGH_THRESHOLD_MGDL,
            is_low=value < DEFAULT_LOW_THRESHOLD_MGDL,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--value",
        type=int,
        help="starting value in mg/dL (default: keep the value file's current "
        "contents, or 120 if it doesn't exist yet)",
    )
    parser.add_argument(
        "--interval", type=int, default=5, help="seconds between polls (default: 5)"
    )
    parser.add_argument(
        "--value-file",
        type=Path,
        default=DEFAULT_VALUE_FILE,
        help=f"file holding the fake reading (default: {DEFAULT_VALUE_FILE})",
    )
    return parser.parse_args()


def _install_test_doubles(value_file: Path, interval_seconds: int) -> None:
    """Patch the app so it runs on the fake client and can't touch real
    settings, credentials, or the autostart entry (see module docstring)."""
    real_load_settings = app_main.load_settings

    def load_settings_for_test():
        settings = real_load_settings()
        settings.interval_seconds = interval_seconds
        return settings

    def ensure_fake_client(application: app_main.Application) -> None:
        application.client = FakeReadingClient(value_file, application.settings.base_host)

    def restart_this_script(_display: tray.TrayDisplay) -> None:
        os.execv(sys.executable, [sys.executable, *sys.argv])

    def log_out_disabled(_display: tray.TrayDisplay) -> None:
        logger.info("'Log out' is disabled under the fake-reading harness")

    def reauthenticate_disabled(_application: app_main.Application) -> bool:
        # The real app stops polling and prompts for credentials on an
        # AuthError; here we just keep polling the value file.
        logger.info("Simulated AuthError: skipping the credential prompt")
        return False

    app_main.load_settings = load_settings_for_test
    app_main.save_settings = lambda settings: None
    app_main.Application._ensure_client = ensure_fake_client
    app_main.Application._reauthenticate = reauthenticate_disabled
    tray.save_settings = lambda settings: None
    tray.set_autostart_enabled = lambda enabled: None
    tray.TrayDisplay._restart = restart_this_script
    tray.TrayDisplay._log_out = log_out_disabled


def main() -> None:
    args = _parse_args()
    if args.value is not None or not args.value_file.exists():
        args.value_file.write_text(f"{args.value if args.value is not None else 120}\n")
    print(f"Fake reading file: {args.value_file}")
    print(f'Change it with e.g.: echo 74 > "{args.value_file}"')

    _install_test_doubles(args.value_file, args.interval)
    app_main.main()


if __name__ == "__main__":
    main()
