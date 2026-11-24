"""Tests for domain.range_tracker: crossings, hysteresis, and gap handling."""

from datetime import datetime, timedelta

from glucoglance.domain.range import GlucoseRange
from glucoglance.domain.range_tracker import RangeTracker
from glucoglance.domain.reading import GlucoseReading
from glucoglance.domain.trend import TrendArrow

_START = datetime(2026, 9, 29, 12, 0)


def _feed(tracker: RangeTracker, values: list[int], step_minutes: int = 1, first_minute: int = 0):
    """Feed `values` as readings `step_minutes` apart, the first one
    `first_minute` after _START; return every state."""
    return [
        tracker.update(
            GlucoseReading(
                value_mgdl=value,
                trend=TrendArrow.STABLE,
                timestamp=_START + timedelta(minutes=first_minute + i * step_minutes),
                is_high=False,
                is_low=False,
            )
        )
        for i, value in enumerate(values)
    ]


def test_in_range_readings_are_never_highlighted():
    states = _feed(RangeTracker(), [100, 120, 140])
    assert all(not s.is_out_of_range and not s.just_crossed for s in states)


def test_crossing_is_flagged_only_on_the_first_out_of_range_reading():
    states = _feed(RangeTracker(), [170, 185, 190, 195])
    assert [s.just_crossed for s in states] == [False, True, False, False]
    assert states[3].glucose_range is GlucoseRange.HIGH


def test_hysteresis_keeps_high_until_clearly_back_in_range():
    # Default threshold 180, hysteresis 5: needs <= 175 to leave HIGH.
    states = _feed(RangeTracker(), [185, 179, 176, 175])
    assert [s.glucose_range for s in states] == [
        GlucoseRange.HIGH,
        GlucoseRange.HIGH,
        GlucoseRange.HIGH,
        GlucoseRange.NORMAL,
    ]


def test_hysteresis_keeps_low_until_clearly_back_in_range():
    # Default threshold 80, hysteresis 5: needs >= 85 to leave LOW.
    states = _feed(RangeTracker(), [75, 82, 84, 85])
    assert [s.is_out_of_range for s in states] == [True, True, True, False]


def test_hysteresis_does_not_delay_entering_a_range():
    states = _feed(RangeTracker(), [180, 181])
    assert states[1].glucose_range is GlucoseRange.HIGH


def test_recrossing_after_recovery_starts_a_new_stretch():
    states = _feed(RangeTracker(), [190, 150, 190], step_minutes=5)
    assert states[2].just_crossed


def test_direct_jump_between_low_and_high_is_a_new_crossing():
    states = _feed(RangeTracker(), [70, 200])
    assert states[1].just_crossed
    assert states[1].glucose_range is GlucoseRange.HIGH


def test_long_gap_between_readings_restarts_the_stretch():
    tracker = RangeTracker(max_gap=timedelta(minutes=15))
    states = _feed(tracker, [190, 195, 200], step_minutes=20)
    assert all(s.just_crossed for s in states)


def test_custom_thresholds_and_hysteresis_are_respected():
    tracker = RangeTracker(low_threshold=70, high_threshold=160, hysteresis_mgdl=10)
    states = _feed(tracker, [165, 152, 150])
    assert [s.is_out_of_range for s in states] == [True, True, False]


def test_acknowledge_in_hysteresis_band_returns_to_normal():
    # 178 is below the 180 threshold but still HIGH because of hysteresis.
    tracker = RangeTracker()
    states = _feed(tracker, [190, 178])
    assert states[1].glucose_range is GlucoseRange.HIGH
    assert tracker.acknowledge() is GlucoseRange.NORMAL


def test_acknowledge_in_low_hysteresis_band_returns_to_normal():
    tracker = RangeTracker()
    _feed(tracker, [75, 82])
    assert tracker.acknowledge() is GlucoseRange.NORMAL


def test_acknowledge_while_still_out_of_range_keeps_the_range():
    tracker = RangeTracker()
    _feed(tracker, [190, 195])
    assert tracker.acknowledge() is GlucoseRange.HIGH
    # Still the same stretch: the next high reading is not a new crossing.
    [state] = _feed(tracker, [196], first_minute=2)
    assert not state.just_crossed


def test_after_acknowledge_in_band_values_use_plain_thresholds():
    # After the reset, 179 is in range and 182 is a fresh crossing.
    tracker = RangeTracker()
    _feed(tracker, [190, 178])
    tracker.acknowledge()
    later = _feed(tracker, [179, 182], first_minute=2)
    assert later[0].glucose_range is GlucoseRange.NORMAL
    assert later[1].glucose_range is GlucoseRange.HIGH
    assert later[1].just_crossed


def test_acknowledge_before_any_reading_is_harmless():
    assert RangeTracker().acknowledge() is GlucoseRange.NORMAL
