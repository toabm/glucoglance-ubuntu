"""Tests for glucose unit conversion (domain.units)."""

from glucose_widget.domain.units import mgdl_to_mmol, mmol_to_mgdl


def test_mgdl_to_mmol_known_reference_value():
    # 100 mg/dL is a commonly cited ~5.5 mmol/L reference point.
    assert mgdl_to_mmol(100) == 5.5


def test_mmol_to_mgdl_known_reference_value():
    assert mmol_to_mgdl(5.5) == 99  # rounding of the inverse conversion


def test_round_trip_is_stable_within_rounding():
    original_mgdl = 118
    converted = mmol_to_mgdl(mgdl_to_mmol(original_mgdl))
    assert abs(converted - original_mgdl) <= 1
