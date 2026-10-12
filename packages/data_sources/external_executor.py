"""Deterministic calculations over validated in-memory external snapshots."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from packages.data_sources.external_metrics import ExternalMetricRegistry
from packages.data_sources.external_router import ExternalQuestionRoute, ExternalRouteStatus
from packages.data_sources.external_selection import ExternalSelection
from packages.data_sources.snapshot_store import StoredFewsSnapshot
from packages.data_sources.weather_snapshot_store import StoredWeatherSnapshot


class ExternalExecutionStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ExternalExecutionResult:
    status: ExternalExecutionStatus
    metric_id: str
    source_id: str
    operation: str
    rows: tuple[dict[str, Any], ...]
    reason: str | None = None


def _result(
    route: ExternalQuestionRoute,
    status: ExternalExecutionStatus,
    *,
    rows: tuple[dict[str, Any], ...] = (),
    reason: str | None = None,
) -> ExternalExecutionResult:
    return ExternalExecutionResult(
        status=status, metric_id=route.metric_id, source_id=route.source_id,
        operation=route.operation, rows=rows, reason=reason,
    )


def _normalized(value: str | None) -> str | None:
    return value.casefold() if value is not None else None


class ExternalMetricExecutor:
    def __init__(self, registry: ExternalMetricRegistry) -> None:
        if not isinstance(registry, ExternalMetricRegistry):
            raise TypeError("registry must be an ExternalMetricRegistry.")
        self.registry = registry

    def execute(
        self,
        route: ExternalQuestionRoute,
        *,
        market_snapshot: StoredFewsSnapshot | None,
        weather_snapshot: StoredWeatherSnapshot | None,
        max_items: int = 5,
        selection: ExternalSelection | None = None,
    ) -> ExternalExecutionResult:
        if (route.status != ExternalRouteStatus.ROUTED or route.metric_id is None
                or route.source_id is None or route.operation is None):
            raise ValueError("External executor requires a routed external question.")
        if type(max_items) is not int or not 1 <= max_items <= 20:
            raise ValueError("max_items must be an integer from 1 to 20.")
        if selection is not None and not isinstance(selection, ExternalSelection):
            raise TypeError("selection must be an ExternalSelection.")

        metric = self.registry.get(route.metric_id)
        if metric.source_id != route.source_id:
            raise ValueError("Route source does not match the external metric.")
        if route.operation not in metric.supported_operations:
            raise ValueError("Operation is not supported for this external metric.")

        if route.metric_id == "market_price_ngn_per_kg":
            if selection is not None and selection.has_weather_selectors:
                raise ValueError("Weather selectors cannot be used for a market metric.")
            return self._market_price(route, market_snapshot, max_items, selection)
        if selection is not None and (selection.has_market_selectors or not selection.descending):
            raise ValueError("Market selectors cannot be used for a weather metric.")
        return self._weather(route, weather_snapshot, selection or ExternalSelection())

    def _market_price(
        self,
        route: ExternalQuestionRoute,
        stored: StoredFewsSnapshot | None,
        max_items: int,
        selection: ExternalSelection | None,
    ) -> ExternalExecutionResult:
        if stored is None:
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "No validated local market-price snapshot is currently available."
            ))
        records = stored.result.records
        if selection is not None:
            for field in ("market", "admin_1", "cpcv2"):
                requested = getattr(selection, field)
                if requested is not None:
                    records = tuple(record for record in records
                                    if _normalized(getattr(record, field)) == requested.casefold())
            if selection.period_date is not None:
                records = tuple(record for record in records
                                if record.period_date == selection.period_date)
        if not records:
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "No saved market-price records match the explicit selection."
            ))

        if route.operation == "value" and len(records) != 1:
            return _result(route, ExternalExecutionStatus.NEEDS_CLARIFICATION, reason=(
                "Multiple market-price observations match. Select a specific market, "
                "administrative area, product code and observation period."
            ))

        # Cross-period, cross-product or cross-unit rankings are not comparable.
        dimensions = ("cpcv2", "product", "currency", "unit", "price_type", "product_source", "country_code")
        signatures = {
            (record.period_date, *(_normalized(getattr(record, field)) for field in dimensions))
            for record in records
        }
        if len(signatures) != 1:
            return _result(route, ExternalExecutionStatus.NEEDS_CLARIFICATION, reason=(
                "A market ranking requires one observation period, product, currency, "
                "unit, price type, product source and country. Narrow the selection."
            ))
        if any(
            record.source_id != route.source_id
            or record.cpcv2.casefold() != "r01122ac"
            or record.product.casefold() != "maize grain (white)"
            or record.currency.casefold() != "ngn"
            or record.unit.casefold() != "kg"
            or record.price_type.casefold() != "retail"
            or record.country_code.casefold() != "ng"
            for record in records
        ):
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "This metric supports Nigerian retail white maize prices in NGN/kg only. "
                "The saved selection does not match that metric contract."
            ))

        if route.operation == "rank":
            identities = {(record.market.casefold(), _normalized(record.admin_1)) for record in records}
            if len(identities) != len(records):
                return _result(route, ExternalExecutionStatus.NEEDS_CLARIFICATION, reason=(
                    "Multiple observations remain for the same market. A ranking requires "
                    "one comparable observation per market."
                ))
            descending = selection.descending if selection is not None else not any(
                phrase in route.normalized_question
                for phrase in ("lowest", "cheapest", "least expensive", "bottom")
            )
            records = sorted(records, key=lambda record: (
                -record.value if descending else record.value,
                record.market.casefold(), _normalized(record.admin_1) or "",
            ))[:max_items]

        rows = []
        for index, record in enumerate(records, start=1):
            row = {
                "market": record.market, "admin_1": record.admin_1,
                "period_date": record.period_date.isoformat(), "cpcv2": record.cpcv2,
                "product": record.product, "price_type": record.price_type,
                "product_source": record.product_source, "country_code": record.country_code,
                "value": str(record.value), "unit": f"{record.currency}/{record.unit}",
            }
            if route.operation == "rank":
                row["rank"] = index
            rows.append(row)
        return _result(route, ExternalExecutionStatus.ANSWERED, rows=tuple(rows))

    def _weather(
        self,
        route: ExternalQuestionRoute,
        stored: StoredWeatherSnapshot | None,
        selection: ExternalSelection,
    ) -> ExternalExecutionResult:
        if stored is None:
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "No validated local weather forecast snapshot is currently available."
            ))
        if selection.latitude is not None and (
            selection.latitude != stored.query.latitude or selection.longitude != stored.query.longitude
        ):
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "The selected coordinates do not match the saved forecast's requested coordinates."
            ))

        start = selection.valid_from or stored.result.requested_from
        end = selection.valid_to or stored.result.requested_to
        if (start > end or start < stored.result.requested_from or end > stored.result.requested_to):
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "The selected forecast hours extend beyond the saved forecast coverage. "
                "Choose hours within the saved forecast bounds."
            ))
        records = tuple(record for record in stored.result.records if start <= record.valid_at <= end)
        if not records:
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "No saved forecast records match the explicit selection."
            ))
        if len({record.valid_at for record in records}) != len(records) or any(
            record.source_id != route.source_id
            or record.requested_latitude != stored.query.latitude
            or record.requested_longitude != stored.query.longitude
            for record in records
        ):
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "The saved forecast selection contains incompatible or duplicate hourly records."
            ))

        field_name = {
            "forecast_temperature_2m_c": "temperature_2m_c",
            "forecast_relative_humidity_2m_pct": "relative_humidity_2m_pct",
            "forecast_precipitation_mm": "precipitation_mm",
        }[route.metric_id]
        values = tuple(sorted(
            (record.valid_at, getattr(record, field_name)) for record in records
            if getattr(record, field_name) is not None
        ))
        if not values:
            return _result(route, ExternalExecutionStatus.UNAVAILABLE, reason=(
                "The selected forecast hours contain no usable values for this measure."
            ))

        expected_hours = int((end - start).total_seconds() // 3600) + 1
        missing_hours = expected_hours - len(values)
        row = {
            "forecast_valid_from": start.isoformat(), "forecast_valid_to": end.isoformat(),
            "latitude": str(stored.query.latitude), "longitude": str(stored.query.longitude),
            "expected_hours": expected_hours, "hours_with_values": len(values),
            "missing_hours": missing_hours, "data_quality": "partial" if missing_hours else "complete",
        }

        if route.metric_id == "forecast_precipitation_mm":
            row["interval_start"] = (start - timedelta(hours=1)).isoformat()
            row["interval_end"] = end.isoformat()
            row["unit"] = "mm"
            if route.operation == "sum":
                row["total"] = str(sum((value for _, value in values), Decimal("0")))
            else:
                rainy_hours = sum(value > Decimal("0") for _, value in values)
                row["rainy_hours"] = rainy_hours
                row["rain_expected"] = True if rainy_hours else (None if missing_hours else False)
            return _result(route, ExternalExecutionStatus.ANSWERED, rows=(row,))

        row["unit"] = "°C" if route.metric_id == "forecast_temperature_2m_c" else "%"
        if route.operation == "value":
            if expected_hours != 1:
                return _result(route, ExternalExecutionStatus.NEEDS_CLARIFICATION, reason=(
                    "The selected forecast contains multiple hourly values. Set valid_from and "
                    "valid_to to the same specific forecast hour or request the forecast range."
                ))
            row.update(value=str(values[0][1]), valid_at=values[0][0].isoformat())
        else:
            minimum_time, minimum = min(values, key=lambda item: item[1])
            maximum_time, maximum = max(values, key=lambda item: item[1])
            row.update(minimum=str(minimum), minimum_valid_at=minimum_time.isoformat(),
                       maximum=str(maximum), maximum_valid_at=maximum_time.isoformat())
        return _result(route, ExternalExecutionStatus.ANSWERED, rows=(row,))
