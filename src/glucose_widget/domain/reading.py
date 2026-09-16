"""The GlucoseReading model: a single point-in-time glucose measurement."""

from dataclasses import dataclass
from datetime import datetime

from glucose_widget.domain.trend import TrendArrow
from glucose_widget.domain.units import GlucoseUnit, mgdl_to_mmol


@dataclass(frozen=True)
class GlucoseReading:
    """A single glucose measurement.

    The value is always stored in mg/dL (the unit the API returns), so that
    conversion logic lives only in `value_in()` / `domain.units` and is never
    duplicated between the client and the UI.
    """

    value_mgdl: int
    trend: TrendArrow
    timestamp: datetime
    is_high: bool
    is_low: bool

    def value_in(self, unit: GlucoseUnit) -> float:
        """Return this reading's value converted to the requested display unit."""
        if unit is GlucoseUnit.MGDL:
            return float(self.value_mgdl)
        return mgdl_to_mmol(self.value_mgdl)
