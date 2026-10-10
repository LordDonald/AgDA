"""Canonical hourly forecasts, distinct from weather observations and surveys."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


def _decimal(name: str, value: Decimal, minimum=None, maximum=None) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} is below its allowed range.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} is above its allowed range.")


def _utc(name: str, value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an aware UTC datetime.")


@dataclass(frozen=True, slots=True)
class WeatherForecastRecord:
    source_id: str
    model: str
    requested_latitude: Decimal
    requested_longitude: Decimal
    grid_latitude: Decimal
    grid_longitude: Decimal
    valid_at: datetime
    temperature_2m_c: Decimal | None
    relative_humidity_2m_pct: Decimal | None
    precipitation_mm: Decimal | None
    source_issued_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("source_id", "model"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank text.")
        for name in ("requested_latitude", "grid_latitude"):
            _decimal(name, getattr(self, name), -90, 90)
        for name in ("requested_longitude", "grid_longitude"):
            _decimal(name, getattr(self, name), -180, 180)
        _utc("valid_at", self.valid_at)
        if self.valid_at.minute or self.valid_at.second or self.valid_at.microsecond:
            raise ValueError("valid_at must align to a UTC hour.")
        if self.source_issued_at is not None:
            _utc("source_issued_at", self.source_issued_at)
        if self.temperature_2m_c is not None:
            _decimal("temperature_2m_c", self.temperature_2m_c, Decimal("-273.15"))
        if self.relative_humidity_2m_pct is not None:
            _decimal("relative_humidity_2m_pct", self.relative_humidity_2m_pct, 0, 100)
        if self.precipitation_mm is not None:
            _decimal("precipitation_mm", self.precipitation_mm, 0)

    @property
    def precipitation_period_start(self) -> datetime:
        """Precipitation is the sum over the hour ending at valid_at."""
        return self.valid_at - timedelta(hours=1)
