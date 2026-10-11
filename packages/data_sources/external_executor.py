from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any

from packages.data_sources.external_metrics import (
    ExternalMetricRegistry,
)
from packages.data_sources.external_router import (
    ExternalQuestionRoute,
    ExternalRouteStatus,
)
from packages.data_sources.snapshot_store import (
    StoredFewsSnapshot,
)
from packages.data_sources.weather_snapshot_store import (
    StoredWeatherSnapshot,
)


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


class ExternalMetricExecutor:

    def __init__(
        self,
        registry: ExternalMetricRegistry,
    ) -> None:

        if not isinstance(
            registry,
            ExternalMetricRegistry,
        ):
            raise TypeError(
                "registry must be an ExternalMetricRegistry."
            )

        self.registry = registry

    def execute(
        self,
        route: ExternalQuestionRoute,
        *,
        market_snapshot: StoredFewsSnapshot | None,
        weather_snapshot: StoredWeatherSnapshot | None,
        max_items: int = 5,
    ) -> ExternalExecutionResult:

        if (
            route.status
            != ExternalRouteStatus.ROUTED
            or route.metric_id is None
            or route.source_id is None
            or route.operation is None
        ):
            raise ValueError(
                "External executor requires a routed external question."
            )

        if (
            type(max_items) is not int
            or max_items < 1
            or max_items > 20
        ):
            raise ValueError(
                "max_items must be an integer from 1 to 20."
            )

        metric = self.registry.get(
            route.metric_id
        )

        if (
            metric.source_id
            != route.source_id
        ):
            raise ValueError(
                "Route source does not match the external metric."
            )

        if (
            route.metric_id
            == "market_price_ngn_per_kg"
        ):
            return self._market_price(
                route,
                market_snapshot,
                max_items=max_items,
            )

        return self._weather(
            route,
            weather_snapshot,
        )

    def _market_price(
        self,
        route: ExternalQuestionRoute,
        stored: StoredFewsSnapshot | None,
        *,
        max_items: int,
    ) -> ExternalExecutionResult:

        if stored is None:
            return ExternalExecutionResult(
                status=ExternalExecutionStatus.UNAVAILABLE,
                metric_id=route.metric_id,
                source_id=route.source_id,
                operation=route.operation,
                rows=(),
                reason=(
                    "No validated local market-price snapshot "
                    "is currently available."
                ),
            )

        records = stored.result.records

        if route.operation == "value":
            if len(records) != 1:
                return ExternalExecutionResult(
                    status=ExternalExecutionStatus.NEEDS_CLARIFICATION,
                    metric_id=route.metric_id,
                    source_id=route.source_id,
                    operation=route.operation,
                    rows=(),
                    reason=(
                        "The saved market-price snapshot contains "
                        "multiple markets. Ask for a specific market "
                        "or request a highest/lowest market ranking."
                    ),
                )

            record = records[0]

            return ExternalExecutionResult(
                status=ExternalExecutionStatus.ANSWERED,
                metric_id=route.metric_id,
                source_id=route.source_id,
                operation=route.operation,
                rows=(
                    {
                        "market": record.market,
                        "admin_1": record.admin_1,
                        "period_date":
                            record.period_date.isoformat(),
                        "product": record.product,
                        "price_type": record.price_type,
                        "value": str(record.value),
                        "unit":
                            f"{record.currency}/{record.unit}",
                    },
                ),
            )

        descending = not any(
            phrase in route.normalized_question
            for phrase in (
                "lowest",
                "cheapest",
                "least expensive",
                "bottom",
            )
        )

        ranked = sorted(
            records,
            key=lambda record: (
                record.value,
                record.market.casefold(),
            ),
            reverse=descending,
        )

        rows = tuple(
            {
                "rank": index,
                "market": record.market,
                "admin_1": record.admin_1,
                "period_date":
                    record.period_date.isoformat(),
                "product": record.product,
                "value": str(record.value),
                "unit":
                    f"{record.currency}/{record.unit}",
            }
            for index, record
            in enumerate(
                ranked[:max_items],
                start=1,
            )
        )

        return ExternalExecutionResult(
            status=ExternalExecutionStatus.ANSWERED,
            metric_id=route.metric_id,
            source_id=route.source_id,
            operation=route.operation,
            rows=rows,
        )

    def _weather(
        self,
        route: ExternalQuestionRoute,
        stored: StoredWeatherSnapshot | None,
    ) -> ExternalExecutionResult:

        if stored is None:
            return ExternalExecutionResult(
                status=ExternalExecutionStatus.UNAVAILABLE,
                metric_id=route.metric_id,
                source_id=route.source_id,
                operation=route.operation,
                rows=(),
                reason=(
                    "No validated local weather forecast snapshot "
                    "is currently available."
                ),
            )

        records = stored.result.records

        field_by_metric = {
            "forecast_temperature_2m_c":
                "temperature_2m_c",
            "forecast_relative_humidity_2m_pct":
                "relative_humidity_2m_pct",
            "forecast_precipitation_mm":
                "precipitation_mm",
        }

        field_name = field_by_metric[
            route.metric_id
        ]

        values = tuple(
            (
                record.valid_at,
                getattr(
                    record,
                    field_name,
                ),
            )
            for record in records
            if getattr(
                record,
                field_name,
            ) is not None
        )

        if not values:
            return ExternalExecutionResult(
                status=ExternalExecutionStatus.UNAVAILABLE,
                metric_id=route.metric_id,
                source_id=route.source_id,
                operation=route.operation,
                rows=(),
                reason=(
                    "The saved forecast contains no usable "
                    "values for this measure."
                ),
            )

        if route.operation == "value":
            if route.metric_id == "forecast_precipitation_mm":
                rainy_hours = sum(
                    value > Decimal("0")
                    for _, value in values
                )

                return ExternalExecutionResult(
                    status=ExternalExecutionStatus.ANSWERED,
                    metric_id=route.metric_id,
                    source_id=route.source_id,
                    operation=route.operation,
                    rows=(
                        {
                            "forecast_valid_from":
                                stored.result.requested_from.isoformat(),
                            "forecast_valid_to":
                                stored.result.requested_to.isoformat(),
                            "rain_expected":
                                rainy_hours > 0,
                            "rainy_hours":
                                rainy_hours,
                            "hours_with_values":
                                len(values),
                        },
                    ),
                )

            return ExternalExecutionResult(
                status=ExternalExecutionStatus.NEEDS_CLARIFICATION,
                metric_id=route.metric_id,
                source_id=route.source_id,
                operation=route.operation,
                rows=(),
                reason=(
                    "The saved forecast contains multiple hourly "
                    "values. Ask for a specific forecast hour or "
                    "request the forecast range."
                ),
            )

        if route.operation == "sum":
            total = sum(
                (
                    value
                    for _, value
                    in values
                ),
                Decimal("0"),
            )

            return ExternalExecutionResult(
                status=ExternalExecutionStatus.ANSWERED,
                metric_id=route.metric_id,
                source_id=route.source_id,
                operation=route.operation,
                rows=(
                    {
                        "forecast_valid_from":
                            stored.result.requested_from.isoformat(),
                        "forecast_valid_to":
                            stored.result.requested_to.isoformat(),
                        "total": str(total),
                        "unit": "mm",
                        "hours_with_values":
                            len(values),
                    },
                ),
            )

        minimum_time, minimum = min(
            values,
            key=lambda item: item[1],
        )

        maximum_time, maximum = max(
            values,
            key=lambda item: item[1],
        )

        unit = (
            "°C"
            if route.metric_id
            == "forecast_temperature_2m_c"
            else "%"
        )

        return ExternalExecutionResult(
            status=ExternalExecutionStatus.ANSWERED,
            metric_id=route.metric_id,
            source_id=route.source_id,
            operation=route.operation,
            rows=(
                {
                    "minimum": str(minimum),
                    "minimum_valid_at":
                        minimum_time.isoformat(),
                    "maximum": str(maximum),
                    "maximum_valid_at":
                        maximum_time.isoformat(),
                    "unit": unit,
                },
            ),
        )
