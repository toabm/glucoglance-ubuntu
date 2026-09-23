"""The glucose trend arrow, as reported by the LibreLinkUp API.

The API encodes the trend as a small integer (1-5). We translate that into a
named enum so the rest of the codebase never has to remember what "3" means,
and attach the display glyph used by the tray label directly to each value.
"""

from enum import Enum


class TrendArrow(Enum):
    """Direction glucose is currently moving, from the wearer's sensor."""

    UNKNOWN = 0
    RAPIDLY_FALLING = 1
    FALLING = 2
    STABLE = 3
    RISING = 4
    RAPIDLY_RISING = 5

    @property
    def glyph(self) -> str:
        """A single-character arrow suitable for a compact tray label."""
        return {
            TrendArrow.UNKNOWN: "?",
            TrendArrow.RAPIDLY_FALLING: "⇊",  # ⇊
            TrendArrow.FALLING: "↓",  # ↓
            TrendArrow.STABLE: "→",  # →
            TrendArrow.RISING: "↑",  # ↑
            TrendArrow.RAPIDLY_RISING: "⇈",  # ⇈
        }[self]

    @classmethod
    def from_api_value(cls, raw: object) -> "TrendArrow":
        """Map the API's raw trend integer to a TrendArrow, defaulting to UNKNOWN
        for anything missing or out of the 1-5 range (the API is unofficial and
        could send us something we don't recognize)."""
        try:
            return cls(int(raw))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return cls.UNKNOWN
