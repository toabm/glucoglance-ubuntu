"""Tests for TrendArrow.from_api_value's handling of the API's raw integer."""

from glucoglance.domain.trend import TrendArrow


def test_known_values_map_correctly():
    assert TrendArrow.from_api_value(1) is TrendArrow.RAPIDLY_FALLING
    assert TrendArrow.from_api_value(3) is TrendArrow.STABLE
    assert TrendArrow.from_api_value(5) is TrendArrow.RAPIDLY_RISING


def test_out_of_range_value_falls_back_to_unknown():
    assert TrendArrow.from_api_value(99) is TrendArrow.UNKNOWN


def test_missing_or_non_numeric_value_falls_back_to_unknown():
    assert TrendArrow.from_api_value(None) is TrendArrow.UNKNOWN
    assert TrendArrow.from_api_value("not-a-number") is TrendArrow.UNKNOWN
