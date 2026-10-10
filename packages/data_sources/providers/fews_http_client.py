"""Bounded, read-only FEWS monthly market-price retrieval for the Nigeria pilot.

No persistence, registry mutation, retries, or automatic redirects. A limit or
failure aborts the whole fetch; only a completed traversal can produce a snapshot.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, DecimalException
from hashlib import sha256
from http.client import HTTPException
import json
import math
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from packages.data_sources.contracts import SourceSnapshot
from packages.data_sources.market_prices import MarketPriceRecord
from packages.data_sources.providers.fews_market_prices import (
    FEWS_MARKET_SOURCE_ID,
    normalize_fews_page,
)


FEWS_MARKET_URL = "https://fdw.fews.net/api/marketpricefacts.json"
FEWS_MONTHLY_SCHEDULE = "Monthly"
FEWS_MARKET_FIELDS = (
    "period_date", "country_code", "admin_1", "admin_2", "fnid", "market",
    "market_id", "cpcv2", "cpcv2_description", "product", "price_type",
    "product_source", "unit", "currency", "value", "dataseries",
    "source_organization", "source_document", "collection_status", "modified",
    "longitude", "latitude",
)
_SCOPE_FIELDS = (
    "country_code", "schedule", "start_date", "end_date", "cpcv2",
    "product", "price_type",
)


class FewsClientError(RuntimeError):
    """The fetch did not complete; no snapshot is available."""


class FewsLimitError(FewsClientError):
    """A configured request, page, record, or response-size budget was reached."""


class FewsHTTPError(FewsClientError):
    """The bounded HTTP request failed (including redirects)."""


class FewsResponseError(FewsClientError):
    """The provider response, pagination link, or record is invalid."""


def _positive_integer(name: str, value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


@dataclass(frozen=True, slots=True)
class FewsClientLimits:
    page_size: int = 100
    max_pages: int = 10
    max_requests: int = 10
    max_records: int = 5000
    timeout_seconds: float = 30.0
    max_response_bytes: int = 5 * 1024 * 1024

    def __post_init__(self) -> None:
        for name in (
            "page_size", "max_pages", "max_requests", "max_records",
            "max_response_bytes",
        ):
            _positive_integer(name, getattr(self, name))
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and greater than zero.")


@dataclass(frozen=True, slots=True)
class FewsMarketPriceQuery:
    """A single CPCv2 leaf/prefix, or an explicitly chosen text fallback.

    Nigeria is fixed because the existing adapter uses the Nigeria source ID.
    When both filters are supplied, CPCv2 takes precedence. Dates are inclusive.
    """

    start_date: date
    end_date: date | None = None
    cpcv2: str | None = None
    product: str | None = None
    price_type: str = "Retail"

    def __post_init__(self) -> None:
        if type(self.start_date) is not date:
            raise ValueError("start_date must be a date.")
        if self.end_date is not None:
            if type(self.end_date) is not date or self.end_date < self.start_date:
                raise ValueError("end_date must be a date on or after start_date.")
        for name in ("cpcv2", "product", "price_type"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
                or value != value.strip() or any(ord(c) < 32 for c in value)
            ):
                raise ValueError(f"{name} must be nonblank text without surrounding whitespace.")
        if self.cpcv2 is None and self.product is None:
            raise ValueError("Supply a CPCv2 code/prefix or an explicit product fallback.")
        if self.cpcv2 is not None and not self.cpcv2.isalnum():
            raise ValueError("cpcv2 must be a single alphanumeric code or prefix.")
        if self.price_type is None:
            raise ValueError("price_type must be nonblank text.")

    def url(self, page_size: int) -> str:
        _positive_integer("page_size", page_size)
        params = {
            "country_code": "NG",
            "schedule": FEWS_MONTHLY_SCHEDULE,
            "start_date": self.start_date.isoformat(),
            "price_type": self.price_type,
            "page_size": str(page_size),
            "fields": ",".join(FEWS_MARKET_FIELDS),
        }
        if self.end_date is not None:
            params["end_date"] = self.end_date.isoformat()
        if self.cpcv2 is not None:
            params["cpcv2"] = self.cpcv2
        else:
            params["product"] = self.product
        return FEWS_MARKET_URL + "?" + urlencode(params)


@dataclass(frozen=True, slots=True)
class FewsFetchResult:
    records: tuple[MarketPriceRecord, ...]
    snapshot: SourceSnapshot | None
    retrieved_at: datetime
    pages_fetched: int
    requests_made: int


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # One client request must not turn into hidden requests outside the cap.
        return None


def _invalid_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def _get_json(
    url: str, *, timeout_seconds: float, max_response_bytes: int,
) -> dict[str, Any]:
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "AgDA-FEWS/0.1",
    })
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise FewsHTTPError(f"FEWS returned HTTP {response.status}.")
            body = response.read(max_response_bytes + 1)
    except HTTPError as error:
        error.close()
        raise FewsHTTPError(f"FEWS returned HTTP {error.code}.") from error
    except (URLError, OSError, HTTPException) as error:
        raise FewsHTTPError("FEWS request failed or timed out.") from error
    if len(body) > max_response_bytes:
        raise FewsLimitError("FEWS response exceeds max_response_bytes.")
    try:
        payload = json.loads(
            body, parse_float=Decimal, parse_constant=_invalid_json_constant,
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise FewsResponseError("FEWS response is not valid JSON.") from error
    if not isinstance(payload, dict):
        raise FewsResponseError("FEWS response must be a JSON object.")
    return payload


def _validate_url(url: str, scope: dict[str, list[str]]) -> None:
    if not isinstance(url, str) or not url or any(c.isspace() or ord(c) < 32 for c in url):
        raise FewsResponseError("Invalid FEWS pagination URL.")
    try:
        parts = urlsplit(url)
        valid = (
            parts.scheme == "https" and parts.hostname == "fdw.fews.net"
            and parts.port in (None, 443)
            and parts.username is None and parts.password is None
            and not parts.fragment
            and parts.path in ("/api/marketpricefacts.json", "/api/marketpricefacts/")
        )
        params = parse_qs(parts.query, keep_blank_values=True)
    except ValueError as error:
        raise FewsResponseError("Invalid FEWS pagination URL.") from error
    if not valid:
        raise FewsResponseError("FEWS pagination URL left the allowed HTTPS endpoint.")
    if any(params.get(key) != scope.get(key) for key in _SCOPE_FIELDS):
        raise FewsResponseError("FEWS pagination URL changed the monthly query scope.")


def _validate_raw_record(record: dict[str, Any]) -> None:
    # The reusable 26B.2 normalizer accepts scalar conversions. At the HTTP
    # boundary, reject containers and lossy IDs before those conversions occur.
    numeric_fields = {"market_id", "dataseries", "value", "longitude", "latitude"}
    for name in FEWS_MARKET_FIELDS:
        value = record.get(name)
        if value is None:
            continue
        if name not in numeric_fields:
            if not isinstance(value, str):
                raise FewsResponseError(f"FEWS {name} must be text or null.")
        elif isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise FewsResponseError(f"FEWS {name} must be a numeric scalar or null.")
        elif name in ("market_id", "dataseries") and value != "":
            try:
                number = Decimal(str(value))
                if not number.is_finite() or number != number.to_integral_value():
                    raise ValueError("ID is not an integer")
            except (ValueError, DecimalException) as error:
                raise FewsResponseError(f"FEWS {name} must be an integer.") from error


def _validate_record(record: MarketPriceRecord, query: FewsMarketPriceQuery) -> None:
    if (
        record.country_code != "NG" or record.price_type != query.price_type
        or record.period_date < query.start_date
        or (query.end_date is not None and record.period_date > query.end_date)
        or (query.cpcv2 is not None and not record.cpcv2.startswith(query.cpcv2))
    ):
        raise FewsResponseError("FEWS returned a record outside the requested scope.")
    for name in ("value", "longitude", "latitude"):
        value = getattr(record, name)
        if value is not None and not value.is_finite():
            raise FewsResponseError(f"FEWS returned non-finite {name}.")


def _json_scalar(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported snapshot value: {type(value).__name__}")


class FewsMarketPriceClient:
    def __init__(
        self, *, limits: FewsClientLimits | None = None,
        get_json: Callable[..., dict[str, Any]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.limits = limits if limits is not None else FewsClientLimits()
        self._get_json = get_json if get_json is not None else _get_json
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def fetch(self, query: FewsMarketPriceQuery) -> FewsFetchResult:
        limits = self.limits
        initial_url = query.url(limits.page_size)
        scope = parse_qs(urlsplit(initial_url).query, keep_blank_values=True)
        url: str | None = initial_url
        visited: set[str] = set()
        records: list[MarketPriceRecord] = []
        requests_made = pages_fetched = 0

        while url is not None:
            _validate_url(url, scope)
            if url in visited:
                raise FewsResponseError("FEWS pagination repeated a URL.")
            if pages_fetched >= limits.max_pages:
                raise FewsLimitError("FEWS fetch would exceed max_pages.")
            if requests_made >= limits.max_requests:
                raise FewsLimitError("FEWS fetch would exceed max_requests.")
            if len(records) >= limits.max_records:
                raise FewsLimitError("FEWS fetch reached max_records with another page pending.")
            visited.add(url)
            requests_made += 1
            try:
                payload = self._get_json(
                    url, timeout_seconds=limits.timeout_seconds,
                    max_response_bytes=limits.max_response_bytes,
                )
            except (URLError, OSError, HTTPException) as error:
                raise FewsHTTPError("FEWS request failed or timed out.") from error
            pages_fetched += 1
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise FewsResponseError("FEWS response results must be a list in a JSON object.")
            if "next" not in payload:
                raise FewsResponseError("FEWS response is missing the next pagination field.")
            next_url = payload["next"]
            if next_url is not None:
                _validate_url(next_url, scope)
            raw_records = payload["results"]
            if len(records) + len(raw_records) > limits.max_records:
                raise FewsLimitError("FEWS response would exceed max_records.")
            if any(not isinstance(record, dict) for record in raw_records):
                raise FewsResponseError("FEWS results must contain only record objects.")
            for raw_record in raw_records:
                _validate_raw_record(raw_record)
            try:
                page_records = normalize_fews_page(payload)
                for record in page_records:
                    _validate_record(record, query)
            except (ValueError, TypeError, DecimalException, OverflowError) as error:
                raise FewsResponseError("FEWS record normalization failed.") from error
            records.extend(page_records)
            # Deliberately do not infer completion from count or a short/empty page.
            # This exact string goes to the transport; no calculated offset or rewrite.
            url = next_url

        retrieved_at = self._clock()
        if (
            not isinstance(retrieved_at, datetime) or retrieved_at.tzinfo is None
            or retrieved_at.utcoffset() is None
        ):
            raise ValueError("clock must return a timezone-aware datetime.")
        retrieved_at = retrieved_at.astimezone(timezone.utc)
        snapshot = None
        if records:
            version_payload = {
                "scope": {key: scope[key] for key in _SCOPE_FIELDS if key in scope},
                "records": [asdict(record) for record in records],
            }
            digest = sha256(json.dumps(
                version_payload, sort_keys=True, separators=(",", ":"),
                default=_json_scalar, allow_nan=False,
            ).encode("utf-8")).hexdigest()
            snapshot = SourceSnapshot(
                source_id=FEWS_MARKET_SOURCE_ID,
                dataset_version=f"fews-monthly-v1:{digest}",
                observed_from=datetime.combine(
                    min(record.period_date for record in records), time.min, timezone.utc,
                ),
                observed_to=datetime.combine(
                    max(record.period_date for record in records), time.min, timezone.utc,
                ),
                # Phase 26A freshness measures AgDA's successful local refresh.
                refreshed_at=retrieved_at,
                retrieved_at=retrieved_at,
                record_count=len(records),
            )
        return FewsFetchResult(
            records=tuple(records), snapshot=snapshot, retrieved_at=retrieved_at,
            pages_fetched=pages_fetched, requests_made=requests_made,
        )
