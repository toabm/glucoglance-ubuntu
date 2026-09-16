"""Classifies a glucose value into a coarse clinical range (low/normal/high).

Thresholds are always in mg/dL, matching GlucoseReading's canonical storage
unit. The values here are just the defaults - `config.settings.Settings`
carries the user's actual configured thresholds, so they can be tuned via
config.toml without a code change. For now this only drives the tray
icon's color; phase 2's threshold alarms will likely want their own,
separately configurable thresholds rather than assuming these exact
cutoffs.
"""

from enum import Enum

DEFAULT_LOW_THRESHOLD_MGDL = 80
DEFAULT_HIGH_THRESHOLD_MGDL = 180


class GlucoseRange(Enum):
    """A coarse classification of a glucose value."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


def classify_mgdl(
    value_mgdl: float,
    *,
    low_threshold: float = DEFAULT_LOW_THRESHOLD_MGDL,
    high_threshold: float = DEFAULT_HIGH_THRESHOLD_MGDL,
) -> GlucoseRange:
    """Classify a glucose value (given in mg/dL) as low, normal, or high,
    against the given thresholds (defaulting to this module's defaults)."""
    if value_mgdl < low_threshold:
        return GlucoseRange.LOW
    if value_mgdl > high_threshold:
        return GlucoseRange.HIGH
    return GlucoseRange.NORMAL
