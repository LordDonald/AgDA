"""Explicit selectors for saved external data; no natural-language inference."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ExternalSelection:
    market: str | None = None
    admin_1: str | None = None
    cpcv2: str | None = None
    period_date: date | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    descending: bool = True

    def __post_init__(self) -> None:
        for name in ("market", "admin_1", "cpcv2"):
            value = getattr(self, name)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{name} must be nonblank text.")
                object.__setattr__(self, name, value.strip())
        if self.period_date is not None and type(self.period_date) is not date:
            raise ValueError("period_date must be a date.")
        for name in ("valid_from", "valid_to"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, datetime)
                or value.utcoffset() != timedelta(0)
                or value.minute or value.second or value.microsecond
            ):
                raise ValueError(f"{name} must align to an aware UTC hour.")
        if (self.valid_from is not None and self.valid_to is not None
                and self.valid_from > self.valid_to):
            raise ValueError("valid_from must not be after valid_to.")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together.")
        for name, bound in (("latitude", 90), ("longitude", 180)):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite()
                or not -bound <= value <= bound
            ):
                raise ValueError(f"{name} must be a finite Decimal within [-{bound}, {bound}].")
        if type(self.descending) is not bool:
            raise ValueError("descending must be a boolean.")
        if self.has_market_selectors and self.has_weather_selectors:
            raise ValueError("Market and weather selectors cannot be combined.")

    @property
    def has_market_selectors(self) -> bool:
        return any(value is not None for value in (
            self.market, self.admin_1, self.cpcv2, self.period_date,
        ))

    @property
    def has_weather_selectors(self) -> bool:
        return any(value is not None for value in (
            self.valid_from, self.valid_to, self.latitude, self.longitude,
        ))
