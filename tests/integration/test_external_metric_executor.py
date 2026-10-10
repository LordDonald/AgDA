from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from packages.data_sources.external_executor import (
    ExternalExecutionStatus,
    ExternalMetricExecutor,
)
from packages.data_sources.external_metrics import (
    build_external_metric_registry,
)
from packages.data_sources.external_router import (
    ExternalQuestionRouter,
)
from packages.data_sources.market_prices import (
    MarketPriceRecord,
)
from packages.data_sources.providers.fews_http_client import (
    FewsFetchResult,
    FewsMarketPriceQuery,
    build_fews_snapshot,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    OPEN_METEO_MODEL,
    OpenMeteoFetchResult,
    OpenMeteoForecastQuery,
)
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore,
)
from packages.data_sources.weather_forecasts import (
    WeatherForecastRecord,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
    build_open_meteo_snapshot,
)


class ExternalMetricExecutorTests(
    unittest.TestCase
):

    def setUp(self):
        registry = build_external_metric_registry()

        self.router = ExternalQuestionRouter(
            registry
        )

        self.executor = ExternalMetricExecutor(
            registry
        )

        self.retrieved_at = datetime(
            2026,
            10,
            10,
            12,
            tzinfo=timezone.utc,
        )

    def market_snapshot(self):
        query = FewsMarketPriceQuery(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            cpcv2="R01122AC",
        )

        records = (
            MarketPriceRecord(
                source_id="fews_net_market_prices_ng",
                period_date=date(2025, 1, 31),
                country_code="NG",
                admin_1="Abia",
                admin_2="Aba North",
                fnid="NG0000M001",
                market="Aba",
                market_id=1,
                cpcv2="R01122AC",
                cpcv2_description="White maize",
                product="Maize Grain (White)",
                price_type="Retail",
                product_source="Local",
                unit="kg",
                currency="NGN",
                value=Decimal("998.10"),
                dataseries=1,
                source_organization="FEWS NET",
                source_document=None,
                collection_status="Published",
                source_modified_at=None,
                longitude=Decimal("7.37063"),
                latitude=Decimal("5.10719"),
            ),
            MarketPriceRecord(
                source_id="fews_net_market_prices_ng",
                period_date=date(2025, 1, 31),
                country_code="NG",
                admin_1="Borno",
                admin_2="Biu",
                fnid="NG0000M002",
                market="Biu",
                market_id=2,
                cpcv2="R01122AC",
                cpcv2_description="White maize",
                product="Maize Grain (White)",
                price_type="Retail",
                product_source="Local",
                unit="kg",
                currency="NGN",
                value=Decimal("511.65"),
                dataseries=2,
                source_organization="FEWS NET",
                source_document=None,
                collection_status="Published",
                source_modified_at=None,
                longitude=Decimal("12.1928"),
                latitude=Decimal("10.6137"),
            ),
        )

        snapshot = build_fews_snapshot(
            query,
            records,
            self.retrieved_at,
        )

        result = FewsFetchResult(
            records=records,
            snapshot=snapshot,
            retrieved_at=self.retrieved_at,
            pages_fetched=1,
            requests_made=1,
        )

        with TemporaryDirectory() as temp:
            store = FewsSnapshotStore(
                Path(temp) / "fews.sqlite3"
            )

            return store.save(
                query,
                result,
            )

    def weather_snapshot(self):
        query = OpenMeteoForecastQuery(
            latitude=Decimal("5.10719"),
            longitude=Decimal("7.37063"),
            forecast_days=1,
        )

        start = datetime(
            2026,
            10,
            10,
            0,
            tzinfo=timezone.utc,
        )

        records = tuple(
            WeatherForecastRecord(
                source_id=
                    OPEN_METEO_FORECAST_SOURCE_ID,
                model=
                    OPEN_METEO_MODEL,
                requested_latitude=
                    query.latitude,
                requested_longitude=
                    query.longitude,
                grid_latitude=
                    Decimal("5.125"),
                grid_longitude=
                    Decimal("7.375"),
                valid_at=
                    start + timedelta(hours=hour),
                temperature_2m_c=
                    Decimal(str(20 + hour)),
                relative_humidity_2m_pct=
                    Decimal("80"),
                precipitation_mm=(
                    Decimal("1.5")
                    if hour in (5, 6)
                    else Decimal("0")
                ),
                source_issued_at=None,
            )
            for hour in range(24)
        )

        snapshot = build_open_meteo_snapshot(
            query,
            records,
            self.retrieved_at,
        )

        result = OpenMeteoFetchResult(
            records=records,
            snapshot=snapshot,
            requested_from=records[0].valid_at,
            requested_to=records[-1].valid_at,
            retrieved_at=self.retrieved_at,
            requests_made=1,
            missing_value_count=0,
        )

        with TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp) / "weather.sqlite3"
            )

            return store.save(
                query,
                result,
            )

    def test_highest_market_price_ranking(self):
        result = self.executor.execute(
            self.router.route(
                "Which market has the highest maize price?"
            ),
            market_snapshot=self.market_snapshot(),
            weather_snapshot=None,
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.ANSWERED,
        )

        self.assertEqual(
            result.rows[0]["market"],
            "Aba",
        )

        self.assertEqual(
            result.rows[0]["value"],
            "998.10",
        )

    def test_lowest_market_price_ranking(self):
        result = self.executor.execute(
            self.router.route(
                "Which market has the lowest maize price?"
            ),
            market_snapshot=self.market_snapshot(),
            weather_snapshot=None,
        )

        self.assertEqual(
            result.rows[0]["market"],
            "Biu",
        )

    def test_unspecified_market_price_needs_clarification(self):
        result = self.executor.execute(
            self.router.route(
                "What is the maize price?"
            ),
            market_snapshot=self.market_snapshot(),
            weather_snapshot=None,
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.NEEDS_CLARIFICATION,
        )

    def test_temperature_range(self):
        result = self.executor.execute(
            self.router.route(
                "What is the forecast temperature range?"
            ),
            market_snapshot=None,
            weather_snapshot=self.weather_snapshot(),
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.ANSWERED,
        )

        self.assertEqual(
            result.rows[0]["minimum"],
            "20",
        )

        self.assertEqual(
            result.rows[0]["maximum"],
            "43",
        )

        self.assertEqual(
            result.rows[0]["unit"],
            "°C",
        )

    def test_temperature_value_needs_hour_clarification(self):
        result = self.executor.execute(
            self.router.route(
                "What is the forecast temperature?"
            ),
            market_snapshot=None,
            weather_snapshot=self.weather_snapshot(),
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.NEEDS_CLARIFICATION,
        )

    def test_rain_question_reports_expected_rain(self):
        result = self.executor.execute(
            self.router.route(
                "Will it rain?"
            ),
            market_snapshot=None,
            weather_snapshot=self.weather_snapshot(),
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.ANSWERED,
        )

        self.assertTrue(
            result.rows[0]["rain_expected"]
        )

        self.assertEqual(
            result.rows[0]["rainy_hours"],
            2,
        )

    def test_total_rain_sums_hourly_forecast(self):
        result = self.executor.execute(
            self.router.route(
                "How much rain is forecast?"
            ),
            market_snapshot=None,
            weather_snapshot=self.weather_snapshot(),
        )

        self.assertEqual(
            result.rows[0]["total"],
            "3.0",
        )

        self.assertEqual(
            result.rows[0]["unit"],
            "mm",
        )

    def test_missing_market_snapshot_is_unavailable(self):
        result = self.executor.execute(
            self.router.route(
                "Which market has the highest maize price?"
            ),
            market_snapshot=None,
            weather_snapshot=None,
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.UNAVAILABLE,
        )

    def test_missing_weather_snapshot_is_unavailable(self):
        result = self.executor.execute(
            self.router.route(
                "Will it rain?"
            ),
            market_snapshot=None,
            weather_snapshot=None,
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.UNAVAILABLE,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
