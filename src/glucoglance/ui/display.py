"""The Display protocol: what any on-screen presentation of glucose readings
must implement.

`main.py` adapts poller events into calls on a `Display` - implementations
never see `poller.PollerEvent` types directly. That keeps this interface
the only thing a new UI (e.g. a future floating always-on-top window) needs
to implement; it requires no changes to the client, domain, or poller code.
"""

from enum import Enum
from typing import Protocol

from glucoglance.domain.reading import GlucoseReading
from glucoglance.domain.units import GlucoseUnit


class NoDataReason(Enum):
    """Why the latest poll produced no reading - lets a display tell the
    user the cause without knowing the client's exception types; `main.py`
    does that mapping."""

    NETWORK = "network"  # couldn't reach LibreLinkUp
    STALE_DATA = "stale_data"  # reached it, but no recent reading from the sensor
    AUTH = "auth"  # login rejected or session expired
    OTHER = "other"  # anything unexpected


class Display(Protocol):
    """A surface that can show the current glucose reading (or an error state)."""

    def show_reading(self, reading: GlucoseReading, unit: GlucoseUnit) -> None:
        """Show a newly-fetched reading, in the given display unit."""
        ...

    def show_error(self, reason: NoDataReason, message: str) -> None:
        """Show that the latest poll produced no reading, and why. `message`
        is the underlying error's text, for detail/logging."""
        ...

    def run(self) -> None:
        """Block, running this display's own event loop until `shutdown()` is called."""
        ...

    def shutdown(self) -> None:
        """Stop `run()`'s event loop and let the process exit."""
        ...
