"""Tests for domain.range's low/normal/high classification."""

from glucose_widget.domain.range import GlucoseRange, classify_mgdl


def test_below_threshold_is_low():
    assert classify_mgdl(79) is GlucoseRange.LOW


def test_at_low_boundary_is_normal():
    assert classify_mgdl(80) is GlucoseRange.NORMAL


def test_within_range_is_normal():
    assert classify_mgdl(140) is GlucoseRange.NORMAL


def test_at_high_boundary_is_normal():
    assert classify_mgdl(180) is GlucoseRange.NORMAL


def test_above_threshold_is_high():
    assert classify_mgdl(181) is GlucoseRange.HIGH


def test_custom_thresholds_are_respected():
    assert classify_mgdl(75, low_threshold=70, high_threshold=160) is GlucoseRange.NORMAL
    assert classify_mgdl(65, low_threshold=70, high_threshold=160) is GlucoseRange.LOW
    assert classify_mgdl(165, low_threshold=70, high_threshold=160) is GlucoseRange.HIGH
