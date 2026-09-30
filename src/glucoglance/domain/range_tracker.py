"""Tracks out-of-range stretches across successive readings, for the tray
icon's attention cues (filled background, pulse on crossing).

`range.classify_mgdl` looks at one value in isolation. This module adds
the two things that need memory of earlier readings:

- **Hysteresis**: once a reading has left the range, it only counts as back
  in range once it's `hysteresis_mgdl` inside the threshold. Without this,
  a value hovering right at a threshold (e.g. 179, 181, 180, 182) would
  flip the highlight on and off with every poll.
- **Crossings**: telling a fresh crossing (worth a pulse) apart from
  "still out, same as last time".

Gaps are measured between the readings' own timestamps, never the wall
clock, so this stays pure and deterministic. A gap between readings
longer than `max_gap` (e.g. the app was asleep or polls kept failing)
starts over, so an out-of-range reading after it counts as a fresh
crossing again rather than silently continuing a stretch nobody saw.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from glucoglance.domain.range import (
    DEFAULT_HIGH_THRESHOLD_MGDL,
    DEFAULT_LOW_THRESHOLD_MGDL,
    GlucoseRange,
    classify_mgdl,
)
from glucoglance.domain.reading import GlucoseReading

DEFAULT_HYSTERESIS_MGDL = 5
DEFAULT_MAX_GAP = timedelta(minutes=15)


@dataclass(frozen=True)
class RangeState:
    """Where the latest reading sits, with the context of the ones before it."""

    glucose_range: GlucoseRange
    # True only for the first reading of a new out-of-range stretch.
    just_crossed: bool

    @property
    def is_out_of_range(self) -> bool:
        return self.glucose_range is not GlucoseRange.NORMAL


class RangeTracker:
    """Feeds on readings one at a time and reports a `RangeState` for each."""

    def __init__(
        self,
        *,
        low_threshold: float = DEFAULT_LOW_THRESHOLD_MGDL,
        high_threshold: float = DEFAULT_HIGH_THRESHOLD_MGDL,
        hysteresis_mgdl: float = DEFAULT_HYSTERESIS_MGDL,
        max_gap: timedelta = DEFAULT_MAX_GAP,
    ):
        self._low_threshold = low_threshold
        self._high_threshold = high_threshold
        self._hysteresis = hysteresis_mgdl
        self._max_gap = max_gap
        self._range = GlucoseRange.NORMAL
        self._last_timestamp: datetime | None = None

    def update(self, reading: GlucoseReading) -> RangeState:
        """Classify `reading` in the context of earlier ones and return the
        resulting state."""
        if self._last_timestamp is not None and (
            reading.timestamp - self._last_timestamp > self._max_gap
        ):
            self._range = GlucoseRange.NORMAL
        self._last_timestamp = reading.timestamp

        new_range = self._classify(reading.value_mgdl)
        # A new stretch starts on any change into LOW or HIGH, including a
        # direct LOW <-> HIGH jump (unlikely, but a different problem).
        just_crossed = new_range is not GlucoseRange.NORMAL and new_range is not self._range
        self._range = new_range
        return RangeState(glucose_range=new_range, just_crossed=just_crossed)

    def _classify(self, value_mgdl: float) -> GlucoseRange:
        """Plain threshold classification, except that staying in an
        already-entered LOW/HIGH range uses a threshold moved `hysteresis`
        further into the normal band."""
        low, high = self._low_threshold, self._high_threshold
        if self._range is GlucoseRange.LOW:
            low += self._hysteresis
        elif self._range is GlucoseRange.HIGH:
            high -= self._hysteresis
        return classify_mgdl(value_mgdl, low_threshold=low, high_threshold=high)
