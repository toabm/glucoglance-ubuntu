"""Background polling loop for glucose readings.

`GlucosePoller` runs a daemon thread that repeatedly asks a client (anything with a `get_latest_reading()` method,
typically a `LibreLinkUpClient`) for the latest reading and publishes the result as an event on its `EventBus`.

Design notes:
  - Threading (not asyncio) because the rest of the app is GTK/GLib callback-driven, and there is only ever one blocking
    network call in flight at a time - a plain thread is simpler than running an asyncio loop alongside GLib's for no real
    benefit.
  - Events are published from the background thread. GTK is not thread-safe, so any subscriber that touches GTK widgets
    (like the tray display) must marshal its own handling back onto the main loop (e.g. via `GLib.idle_add`) - the poller
    deliberately knows nothing about GTK, so it stays reusable for a future phase 2 alert subscriber that might not need
    the GTK main loop at all.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from glucoglance.domain.reading import GlucoseReading

DEFAULT_INTERVAL_SECONDS = 65
_MAX_BACKOFF_SECONDS = 600


class ReadingSource(Protocol):
    """Anything the poller can pull a reading from - satisfied by LibreLinkUpClient."""

    def get_latest_reading(self) -> GlucoseReading: ...


class PollerEvent:
    """Base class for events published on the poller's EventBus."""


@dataclass(frozen=True)
class ReadingUpdatedEvent(PollerEvent):
    """A new reading was fetched successfully."""

    reading: GlucoseReading


@dataclass(frozen=True)
class PollErrorEvent(PollerEvent):
    """A poll attempt failed. `consecutive_failures` lets subscribers decide
    for themselves when a run of errors is worth surfacing as "stale"."""

    error: Exception
    consecutive_failures: int


@dataclass
class EventBus:
    """A minimal publish/subscribe list.

    Events are a class-hierarchy tagged union, not a topic-based scheme:
    `publish()` takes any `PollerEvent`, and every subscriber receives every
    event regardless of its concrete type - there's no per-type filtering
    here. Each subscriber is responsible for checking which `PollerEvent`
    subclass (`ReadingUpdatedEvent`, `PollErrorEvent`, ...) it got and
    ignoring the ones it doesn't care about. This keeps the bus itself
    trivial to extend - a new event type is just a new `PollerEvent`
    subclass, with no changes needed here.
    """

    _subscribers: list[Callable[[PollerEvent], None]] = field(default_factory=list)

    def subscribe(self, handler: Callable[[PollerEvent], None]) -> None:
        self._subscribers.append(handler)

    def publish(self, event: PollerEvent) -> None:
        """Call every subscriber with `event`. Subscribers run in the calling
        thread - see the module docstring about GTK thread-safety."""
        for handler in list(self._subscribers):
            handler(event)


class GlucosePoller:
    """Polls a `ReadingSource` on an interval and publishes results to an EventBus."""

    def __init__(
            self,
            client: ReadingSource,
            *,
            interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
            bus: EventBus | None = None,
    ):
        self.bus = bus or EventBus()
        self._client = client
        self._base_interval = interval_seconds
        # _stop_event is how the main thread tells the poller thread to stop. It's a threading.Event,
        # which is a flag that is safe to share between threads. It's either set or not set, and a thread can wait
        # for it to become set.
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None


    def start(self) -> None:
        """Start polling in a background daemon thread. No-op if already running."""
        if self._thread is not None:
            return
        self._stop_event.clear() # Resets the flag to "not stopped" so the loop can run.
        self._thread = threading.Thread(target=self._run, daemon=True, name="glucose-poller")
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the polling loop to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        """The polling loop body. Runs until `stop()` is called."""
        consecutive_failures = 0
        while not self._stop_event.is_set():
            try:
                reading = self._client.get_latest_reading()
            except Exception as exc:  # noqa: BLE001 - any client failure is reported uniformly
                consecutive_failures += 1
                self.bus.publish(PollErrorEvent(error=exc, consecutive_failures=consecutive_failures))
                wait_seconds = self._backoff_seconds(consecutive_failures)
            else:
                consecutive_failures = 0
                self.bus.publish(ReadingUpdatedEvent(reading=reading))
                wait_seconds = self._base_interval

            # `Event.wait` (rather than `time.sleep`) so `stop()` can interrupt
            # the wait immediately instead of after the full interval.
            self._stop_event.wait(timeout=wait_seconds)

    def _backoff_seconds(self, consecutive_failures: int) -> float:
        """Exponential backoff after errors, capped so we still retry eventually."""
        backoff = self._base_interval * (2 ** (consecutive_failures - 1))
        return min(backoff, _MAX_BACKOFF_SECONDS)
