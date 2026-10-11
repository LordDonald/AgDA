from dataclasses import dataclass
from enum import StrEnum


class ExternalMetricKind(StrEnum):
    MARKET_PRICE = "market_price"
    WEATHER_FORECAST = "weather_forecast"


@dataclass(frozen=True, slots=True)
class ExternalMetricDefinition:
    metric_id: str
    source_id: str
    kind: ExternalMetricKind
    display_name: str
    unit: str
    supported_operations: tuple[str, ...]
    question_terms: tuple[str, ...]
    time_semantics: str
    caution: str

    def __post_init__(self) -> None:
        for name in (
            "metric_id",
            "source_id",
            "display_name",
            "unit",
            "time_semantics",
            "caution",
        ):
            value = getattr(self, name)

            if (
                not isinstance(value, str)
                or not value.strip()
            ):
                raise ValueError(
                    f"{name} must be nonblank text."
                )

        if not self.supported_operations:
            raise ValueError(
                "supported_operations must not be empty."
            )

        if not self.question_terms:
            raise ValueError(
                "question_terms must not be empty."
            )


class ExternalMetricRegistry:

    def __init__(
        self,
        definitions: tuple[
            ExternalMetricDefinition,
            ...
        ],
    ) -> None:

        self._definitions = {}

        for definition in definitions:
            if not isinstance(
                definition,
                ExternalMetricDefinition,
            ):
                raise TypeError(
                    "Expected ExternalMetricDefinition."
                )

            if (
                definition.metric_id
                in self._definitions
            ):
                raise ValueError(
                    "Duplicate external metric_id: "
                    f"{definition.metric_id}"
                )

            self._definitions[
                definition.metric_id
            ] = definition

    def contains(
        self,
        metric_id: str,
    ) -> bool:

        return (
            metric_id
            in self._definitions
        )

    def get(
        self,
        metric_id: str,
    ) -> ExternalMetricDefinition:

        try:
            return self._definitions[
                metric_id
            ]
        except KeyError as error:
            raise KeyError(
                f"Unknown external metric_id: "
                f"{metric_id}"
            ) from error

    def list(
        self,
    ) -> tuple[
        ExternalMetricDefinition,
        ...
    ]:

        return tuple(
            self._definitions.values()
        )

    def count(
        self,
    ) -> int:

        return len(
            self._definitions
        )


def build_external_metric_registry(
) -> ExternalMetricRegistry:

    return ExternalMetricRegistry(
        (
            ExternalMetricDefinition(
                metric_id=
                    "market_price_ngn_per_kg",
                source_id=
                    "fews_net_market_prices_ng",
                kind=
                    ExternalMetricKind.MARKET_PRICE,
                display_name=
                    "Observed retail market price",
                unit=
                    "NGN/kg",
                supported_operations=(
                    "value",
                    "rank",
                ),
                question_terms=(
                    "price",
                    "market price",
                    "maize price",
                    "cost per kg",
                    "naira per kg",
                ),
                time_semantics=(
                    "Historical observed market-price "
                    "period from the saved FEWS snapshot."
                ),
                caution=(
                    "Do not describe this historical "
                    "observation as a current live price."
                ),
            ),
            ExternalMetricDefinition(
                metric_id=
                    "forecast_temperature_2m_c",
                source_id=
                    "open_meteo_forecast",
                kind=
                    ExternalMetricKind.WEATHER_FORECAST,
                display_name=
                    "Forecast air temperature",
                unit=
                    "°C",
                supported_operations=(
                    "value",
                    "range",
                ),
                question_terms=(
                    "temperature",
                    "hot",
                    "cold",
                    "degrees",
                ),
                time_semantics=(
                    "Hourly forecast-valid time from "
                    "the saved Open-Meteo snapshot."
                ),
                caution=(
                    "Forecast values are predictions, "
                    "not observed weather."
                ),
            ),
            ExternalMetricDefinition(
                metric_id=
                    "forecast_relative_humidity_2m_pct",
                source_id=
                    "open_meteo_forecast",
                kind=
                    ExternalMetricKind.WEATHER_FORECAST,
                display_name=
                    "Forecast relative humidity",
                unit=
                    "%",
                supported_operations=(
                    "value",
                    "range",
                ),
                question_terms=(
                    "humidity",
                    "humid",
                    "relative humidity",
                ),
                time_semantics=(
                    "Hourly forecast-valid time from "
                    "the saved Open-Meteo snapshot."
                ),
                caution=(
                    "Forecast values are predictions, "
                    "not observed humidity."
                ),
            ),
            ExternalMetricDefinition(
                metric_id=
                    "forecast_precipitation_mm",
                source_id=
                    "open_meteo_forecast",
                kind=
                    ExternalMetricKind.WEATHER_FORECAST,
                display_name=
                    "Forecast precipitation",
                unit=
                    "mm",
                supported_operations=(
                    "value",
                    "sum",
                ),
                question_terms=(
                    "rain",
                    "rainfall",
                    "precipitation",
                    "will it rain",
                ),
                time_semantics=(
                    "Each hourly precipitation value "
                    "represents the preceding hour."
                ),
                caution=(
                    "Forecast precipitation is predicted "
                    "weather, not measured rainfall."
                ),
            ),
        )
    )
