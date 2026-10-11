"""One bounded Open-Meteo forecast request; no persistence or runtime side effects."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from http.client import HTTPException
import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from packages.data_sources.contracts import SourceDefinition, SourceSnapshot, SourceType
from packages.data_sources.weather_forecasts import WeatherForecastRecord


OPEN_METEO_FORECAST_SOURCE_ID = "open_meteo_forecast"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_MODEL = "ecmwf_ifs025"
_VARIABLES = ("temperature_2m", "relative_humidity_2m", "precipitation")
_UNITS = {"time": "unixtime", "temperature_2m": "\u00b0C",
          "relative_humidity_2m": "%", "precipitation": "mm"}


class WeatherClientError(RuntimeError):
    """The forecast could not be retrieved and validated completely."""


class WeatherLimitError(WeatherClientError):
    """A configured response or record bound would be exceeded."""


class WeatherHTTPError(WeatherClientError):
    """The single HTTP attempt failed; redirects and retries are disabled."""


class WeatherResponseError(WeatherClientError):
    """The returned forecast does not satisfy the requested contract."""


def _positive_integer(name: str, value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer.")


@dataclass(frozen=True, slots=True)
class WeatherClientLimits:
    max_records: int = 168
    timeout_seconds: float = 20.0
    max_response_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        _positive_integer("max_records", self.max_records)
        _positive_integer("max_response_bytes", self.max_response_bytes)
        if (isinstance(self.timeout_seconds, bool)
                or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be positive and finite.")


@dataclass(frozen=True, slots=True)
class OpenMeteoForecastQuery:
    latitude: Decimal
    longitude: Decimal
    forecast_days: int = 3

    def __post_init__(self) -> None:
        for name, bound in (("latitude", 90), ("longitude", 180)):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or not -bound <= value <= bound:
                raise ValueError(f"{name} must be a finite Decimal within [-{bound}, {bound}].")
        _positive_integer("forecast_days", self.forecast_days)
        if self.forecast_days > 7:
            raise ValueError("The local pilot permits at most seven forecast days.")

    def url(self, start_date: date) -> str:
        if type(start_date) is not date:
            raise ValueError("start_date must be a date.")
        return OPEN_METEO_FORECAST_URL + "?" + urlencode({
            "latitude": str(self.latitude), "longitude": str(self.longitude),
            "models": OPEN_METEO_MODEL, "hourly": ",".join(_VARIABLES),
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=self.forecast_days - 1)).isoformat(),
            "timezone": "GMT", "timeformat": "unixtime", "temperature_unit": "celsius",
            "precipitation_unit": "mm", "cell_selection": "nearest", "elevation": "nan",
        })


@dataclass(frozen=True, slots=True)
class OpenMeteoFetchResult:
    records: tuple[WeatherForecastRecord, ...]
    snapshot: SourceSnapshot
    requested_from: datetime
    requested_to: datetime
    retrieved_at: datetime
    requests_made: int
    missing_value_count: int


def build_open_meteo_source_definition() -> SourceDefinition:
    return SourceDefinition(
        source_id=OPEN_METEO_FORECAST_SOURCE_ID,
        display_name="Open-Meteo hourly weather forecast",
        source_type=SourceType.WEATHER_FORECAST,
        provider="Open-Meteo / ECMWF", geographic_scope="One explicitly requested coordinate; Nigeria pilot",
        methodology_note=(
            "ECMWF IFS 0.25 degree model forecast, provided by Open-Meteo as hourly values. "
            "Nearest grid cell without elevation downscaling; hourly output may be interpolated. "
            "Temperature and humidity are valid at the stated hour; precipitation sums the preceding hour. "
            "This product stitches recent runs and does not supply a single issue time. "
            "SourceSnapshot observed_from/observed_to describe forecast-valid hours, not observed weather. "
            "Freshness measures AgDA retrieval age, not forecast accuracy or model issue age."
        ),
        attribution="Weather data by Open-Meteo.com; ECMWF IFS model data",
        license_name="CC BY 4.0", source_url=OPEN_METEO_FORECAST_URL,
        stale_after_hours=6, expected_refresh_hours=None,
    )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _invalid_json_constant(value: str) -> None:
    raise ValueError("Non-finite JSON constant.")


def _get_json(url: str, *, timeout_seconds: float, max_response_bytes: int) -> dict[str, Any]:
    request = Request(url, headers={
        "Accept": "application/json", "Accept-Encoding": "identity",
        "User-Agent": "AgDA-Weather-Pilot/0.1",
    })
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise WeatherHTTPError(f"Open-Meteo returned HTTP {response.status}.")
            body = response.read(max_response_bytes + 1)
    except HTTPError as error:
        error.close()
        raise WeatherHTTPError(f"Open-Meteo returned HTTP {error.code}.") from error
    except (URLError, OSError, HTTPException) as error:
        raise WeatherHTTPError("Open-Meteo request failed or timed out.") from error
    if len(body) > max_response_bytes:
        raise WeatherLimitError("Weather response exceeds max_response_bytes.")
    try:
        payload = json.loads(body, parse_float=Decimal, parse_constant=_invalid_json_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise WeatherResponseError("Weather response is not valid JSON.") from error
    if not isinstance(payload, dict):
        raise WeatherResponseError("Weather response must be a single JSON object.")
    return payload


def _number(name: str, value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise WeatherResponseError(f"Weather {name} must be numeric.")
    result = Decimal(str(value))
    if not result.is_finite():
        raise WeatherResponseError(f"Weather {name} must be finite.")
    return result


def _grid_distance_km(query: OpenMeteoForecastQuery, latitude: Decimal, longitude: Decimal) -> float:
    lat1, lat2 = math.radians(float(query.latitude)), math.radians(float(latitude))
    dlon = math.radians(float(longitude - query.longitude))
    haversine = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, haversine))))


def normalize_open_meteo_forecast(
    payload: dict[str, Any], query: OpenMeteoForecastQuery, start_date: date,
) -> tuple[WeatherForecastRecord, ...]:
    if type(start_date) is not date:
        raise ValueError("start_date must be a date.")
    if not isinstance(payload, dict) or payload.get("error"):
        raise WeatherResponseError("Open-Meteo did not return a successful forecast object.")
    if (type(payload.get("utc_offset_seconds")) is not int or payload["utc_offset_seconds"] != 0
            or payload.get("timezone") not in ("GMT", "UTC", "Etc/GMT", "Etc/UTC")):
        raise WeatherResponseError("Weather response must use UTC.")
    latitude = _number("latitude", payload.get("latitude"))
    longitude = _number("longitude", payload.get("longitude"))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise WeatherResponseError("Weather grid coordinates are outside geographic bounds.")
    if _grid_distance_km(query, latitude, longitude) > 50:
        raise WeatherResponseError("Weather grid cell is too far from the requested point.")
    units, hourly = payload.get("hourly_units"), payload.get("hourly")
    if not isinstance(units, dict) or any(units.get(key) != value for key, value in _UNITS.items()):
        raise WeatherResponseError("Weather units do not match the requested units.")
    hours = query.forecast_days * 24
    if not isinstance(hourly, dict) or any(
        not isinstance(hourly.get(key), list) or len(hourly[key]) != hours
        for key in ("time", *_VARIABLES)
    ):
        raise WeatherResponseError("Weather arrays must cover every requested hour exactly.")
    first = datetime.combine(start_date, time.min, timezone.utc)
    records = []
    for index, timestamp in enumerate(hourly["time"]):
        valid_at = first + timedelta(hours=index)
        if type(timestamp) is not int or timestamp != int(valid_at.timestamp()):
            raise WeatherResponseError("Weather timestamps must match the ordered requested UTC hours.")
        values = [None if hourly[key][index] is None else _number(key, hourly[key][index])
                  for key in _VARIABLES]
        try:
            records.append(WeatherForecastRecord(
                source_id=OPEN_METEO_FORECAST_SOURCE_ID, model=OPEN_METEO_MODEL,
                requested_latitude=query.latitude, requested_longitude=query.longitude,
                grid_latitude=latitude, grid_longitude=longitude, valid_at=valid_at,
                temperature_2m_c=values[0], relative_humidity_2m_pct=values[1], precipitation_mm=values[2],
                # generationtime_ms is a duration; no model issue timestamp is supplied.
                source_issued_at=None,
            ))
        except ValueError as error:
            raise WeatherResponseError("Weather values are outside the canonical contract.") from error
    if not any(any(value is not None for value in (
        record.temperature_2m_c, record.relative_humidity_2m_pct, record.precipitation_mm,
    )) for record in records):
        raise WeatherResponseError("Weather response contains no usable forecast values.")
    return tuple(records)


def _json_scalar(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError("Unsupported weather snapshot value.")


def _clock_utc(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime.")
    return value.astimezone(timezone.utc)


class OpenMeteoForecastClient:
    def __init__(self, *, limits: WeatherClientLimits | None = None,
                 get_json: Callable[..., dict[str, Any]] | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.limits = limits if limits is not None else WeatherClientLimits()
        self._get_json = get_json if get_json is not None else _get_json
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def fetch(self, query: OpenMeteoForecastQuery) -> OpenMeteoFetchResult:
        if query.forecast_days * 24 > self.limits.max_records:
            raise WeatherLimitError("Requested weather hours exceed max_records.")
        started_at = _clock_utc(self._clock)
        url = query.url(started_at.date())
        try:
            payload = self._get_json(url, timeout_seconds=self.limits.timeout_seconds,
                                     max_response_bytes=self.limits.max_response_bytes)
        except (URLError, OSError, HTTPException) as error:
            raise WeatherHTTPError("Open-Meteo request failed or timed out.") from error
        if isinstance(payload, dict) and isinstance(payload.get("hourly"), dict):
            times = payload["hourly"].get("time")
            if isinstance(times, list) and len(times) > self.limits.max_records:
                raise WeatherLimitError("Returned weather hours exceed max_records.")
        records = normalize_open_meteo_forecast(payload, query, started_at.date())
        retrieved_at = _clock_utc(self._clock)
        if retrieved_at < started_at:
            raise ValueError("Retrieval clock moved backwards during the request.")
        digest = sha256(json.dumps(
            {"query_url": url, "records": [asdict(record) for record in records]},
            sort_keys=True, separators=(",", ":"), default=_json_scalar, allow_nan=False,
        ).encode("utf-8")).hexdigest()
        snapshot = SourceSnapshot(
            source_id=OPEN_METEO_FORECAST_SOURCE_ID, dataset_version=f"open-meteo-hourly-v1:{digest}",
            observed_from=records[0].valid_at, observed_to=records[-1].valid_at,
            refreshed_at=retrieved_at, retrieved_at=retrieved_at, record_count=len(records),
        )
        missing = sum(value is None for record in records for value in (
            record.temperature_2m_c, record.relative_humidity_2m_pct, record.precipitation_mm,
        ))
        return OpenMeteoFetchResult(
            records=records, snapshot=snapshot, requested_from=records[0].valid_at,
            requested_to=records[-1].valid_at, retrieved_at=retrieved_at,
            requests_made=1, missing_value_count=missing,
        )
