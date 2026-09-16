"""The Display protocol: what any on-screen presentation of glucose readings
must implement.

`main.py` adapts poller events into calls on a `Display` - implementations
never see `poller.PollerEvent` types directly. That keeps this interface
the only thing a new UI (e.g. a future floating always-on-top window) needs
to implement; it requires no changes to the client, domain, or poller code.
"""

from typing import Protocol

from glucose_widget.domain.reading import GlucoseReading
from glucose_widget.domain.units import GlucoseUnit


class Display(Protocol):
    """A surface that can show the current glucose reading (or an error state)."""

    def show_reading(self, reading: GlucoseReading, unit: GlucoseUnit) -> None:
        """Show a newly-fetched reading, in the given display unit."""
        ...

    def show_error(self, message: str) -> None:
        """Show that the latest poll failed (network issue, stale data, etc.)."""
        ...

    def run(self) -> None:
        """Block, running this display's own event loop until `shutdown()` is called."""
        ...

    def shutdown(self) -> None:
        """Stop `run()`'s event loop and let the process exit."""
        ...
