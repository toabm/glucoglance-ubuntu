"""Tests for GlucosePoller: event dispatch, failure backoff, and clean shutdown.

Uses a fake client instead of the real LibreLinkUpClient so these tests run
fast and offline.
"""

import time
from datetime import datetime

from glucose_widget.domain.reading import GlucoseReading
from glucose_widget.domain.trend import TrendArrow
from glucose_widget.poller.poller import EventBus, GlucosePoller, PollError, ReadingUpdated

_SHORT_INTERVAL = 0.02


def make_reading(value: int = 100) -> GlucoseReading:
    return GlucoseReading(
        value_mgdl=value,
        trend=TrendArrow.STABLE,
        timestamp=datetime.now(),
        is_high=False,
        is_low=False,
    )


class FakeClient:
    """Returns a scripted sequence of readings/exceptions, one per call,
    repeating the last entry once the script is exhausted."""

    def __init__(self, script: list):
        self._script = script
        self.calls = 0

    def get_latest_reading(self) -> GlucoseReading:
        index = min(self.calls, len(self._script) - 1)
        self.calls += 1
        result = self._script[index]
        if isinstance(result, Exception):
            raise result
        return result


def collect_events(bus: EventBus) -> list:
    events = []
    bus.subscribe(events.append)
    return events


def wait_until(predicate, timeout: float = 2.0) -> None:
    """Poll `predicate` until it's true or `timeout` seconds have elapsed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not met within timeout")


def test_publishes_reading_updated_on_success():
    client = FakeClient([make_reading(value=118)])
    bus = EventBus()
    events = collect_events(bus)
    poller = GlucosePoller(client, interval_seconds=_SHORT_INTERVAL, bus=bus)

    poller.start()
    wait_until(lambda: len(events) >= 1)
    poller.stop()

    assert isinstance(events[0], ReadingUpdated)
    assert events[0].reading.value_mgdl == 118


def test_publishes_poll_error_with_increasing_failure_count():
    client = FakeClient([RuntimeError("boom"), RuntimeError("boom again")])
    bus = EventBus()
    events = collect_events(bus)
    poller = GlucosePoller(client, interval_seconds=_SHORT_INTERVAL, bus=bus)

    poller.start()
    wait_until(lambda: len(events) >= 2)
    poller.stop()

    assert all(isinstance(e, PollError) for e in events[:2])
    assert events[0].consecutive_failures == 1
    assert events[1].consecutive_failures == 2


def test_failure_count_resets_after_a_success():
    client = FakeClient([RuntimeError("boom"), make_reading()])
    bus = EventBus()
    events = collect_events(bus)
    poller = GlucosePoller(client, interval_seconds=_SHORT_INTERVAL, bus=bus)

    poller.start()
    wait_until(lambda: len(events) >= 2)
    poller.stop()

    assert isinstance(events[0], PollError)
    assert isinstance(events[1], ReadingUpdated)


def test_stop_joins_promptly_even_mid_backoff():
    # A long base interval means the poller would otherwise be asleep for a
    # long time; stop() should still return quickly because it interrupts
    # the wait rather than sleeping through it.
    client = FakeClient([make_reading()])
    poller = GlucosePoller(client, interval_seconds=60)

    poller.start()
    wait_until(lambda: client.calls >= 1)
    started = time.monotonic()
    poller.stop(timeout=2.0)
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
