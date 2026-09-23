"""Glucose unit handling.

The LibreLinkUp API always reports glucose values in mg/dL, regardless of the
unit the sensor wearer's app is configured to display. This module defines
the two units we support showing to the user and the pure conversion
functions between them, so the conversion math lives in exactly one place.
"""

from enum import Enum

# The standard clinical conversion factor between mg/dL and mmol/L for glucose.
_MGDL_PER_MMOL = 18.0182


class GlucoseUnit(Enum):
    """A unit the widget can display glucose values in."""

    MGDL = "mgdl"
    MMOL = "mmol"


def mgdl_to_mmol(value_mgdl: float) -> float:
    """Convert a glucose value from mg/dL to mmol/L, rounded to 1 decimal place."""
    return round(value_mgdl / _MGDL_PER_MMOL, 1)


def mmol_to_mgdl(value_mmol: float) -> float:
    """Convert a glucose value from mmol/L to mg/dL, rounded to the nearest integer."""
    return round(value_mmol * _MGDL_PER_MMOL)
