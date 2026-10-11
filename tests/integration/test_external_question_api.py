from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.app.core.settings import AppSettings
from packages.data_sources.market_prices import MarketPriceRecord
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
from packages.data_sources.snapshot_store import FewsSnapshotStore
from packages.data_sources.weather_forecasts import WeatherForecastRecord
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
    build_open_meteo_snapshot,
)


runtime_module = importlib.import_module(
    "apps.api.app.core.runtime"
)
main_module = importlib.import_module(
    "apps.api.app.main"
)
questions_module = importlib.import_module(
    "apps.api.app.routes.questions"
)
health_module = importlib.import_module(
    "apps.api.app.routes.health"
)
sources_module = importlib.import_module(
    "apps.api.app.routes.sources"
)


class ExternalQuestionAPITests(unittest.TestCase):

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        root = Path(self.directory.name)

        self.fews_path = root / "fews.sqlite3"
        self.weather_path = root / "weather.sqlite3"

        self.now = datetime(
            2026,
            10,
            10,
            12,
            tzinfo=timezone.utc,
        )

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            self.settings = AppSettings.from_env()

        contract_clock = self.enterContext(
            patch(
                "packages.data_sources.contracts.datetime",
                wraps=datetime,
            )
        )
        contract_clock.now.return_value = self.now

        self.enterContext(
            patch(
                "packages.data_sources.providers."
                "fews_http_client._get_json",
                side_effect=AssertionError(
                    "Question API must never query FEWS."
                ),
            )
        )

        self.enterContext(
            patch(
                "packages.data_sources.providers."
                "open_meteo_forecast._get_json",
                side_effect=AssertionError(
                    "Question API must never query Open-Meteo."
                ),
            )
        )

    def save_fews(self):
        query = FewsMarketPriceQuery(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            cpcv2="R01122AC",
        )

        values = (
            ("Aba", "Abia", "998.10"),
            ("Biu", "Borno", "511.65"),
            ("Gombe", "Gombe", "710.00"),
        )

        records = tuple(
            MarketPriceRecord(
                source_id="fews_net_market_prices_ng",
                period_date=date(2025, 1, 31),
                country_code="NG",
                admin_1=state,
                admin_2=None,
                fnid=None,
                market=market,
                market_id=index,
                cpcv2="R01122AC",
                cpcv2_description="White maize",
                product="Maize Grain (White)",
                price_type="Retail",
                product_source="Local",
                unit="kg",
                currency="NGN",
                value=Decimal(value),
                dataseries=index,
                source_organization="FEWS NET",
                source_document=None,
                collection_status="Published",
                source_modified_at=None,
                longitude=None,
                latitude=None,
            )
            for index, (market, state, value)
            in enumerate(values, start=1)
        )

        snapshot = build_fews_snapshot(
            query,
            records,
            self.now,
        )

        result = FewsFetchResult(
            records=records,
            snapshot=snapshot,
            retrieved_at=self.now,
            pages_fetched=1,
            requests_made=1,
        )

        FewsSnapshotStore(
            self.fews_path
        ).save(
            query,
            result,
        )

    def save_weather(self):
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
            self.now,
        )

        result = OpenMeteoFetchResult(
            records=records,
            snapshot=snapshot,
            requested_from=records[0].valid_at,
            requested_to=records[-1].valid_at,
            retrieved_at=self.now,
            requests_made=1,
            missing_value_count=0,
        )

        WeatherSnapshotStore(
            self.weather_path
        ).save(
            query,
            result,
        )

    def configured(
        self,
        *,
        fews=True,
        weather=True,
    ):
        return replace(
            self.settings,
            fews_snapshot_path=(
                str(self.fews_path)
                if fews
                else None
            ),
            weather_snapshot_path=(
                str(self.weather_path)
                if weather
                else None
            ),
        )

    @contextmanager
    def api(
        self,
        configured_settings,
    ):
        runtime = runtime_module.AgDARuntime()

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    runtime_module,
                    "settings",
                    configured_settings,
                )
            )

            for module in (
                main_module,
                questions_module,
                health_module,
                sources_module,
            ):
                stack.enter_context(
                    patch.object(
                        module,
                        "runtime",
                        runtime,
                    )
                )

            client = stack.enter_context(
                TestClient(main_module.app)
            )

            yield runtime, client

    def ask(
        self,
        client,
        question,
    ):
        return client.post(
            "/v1/questions",
            json={
                "question": question,
                "include_visualization": False,
            },
        )

    def test_market_price_ranking_uses_fews(self):
        self.save_fews()
        self.save_weather()

        with self.api(
            self.configured()
        ) as (_, client):

            response = self.ask(
                client,
                "Which market has the highest maize price?",
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertEqual(
                body["status"],
                "answered",
            )

            self.assertIsNone(
                body["question_specification"]
            )

            self.assertEqual(
                body["result"]["source_id"],
                "fews_net_market_prices_ng",
            )

            self.assertEqual(
                body["result"]["rows"][0]["market"],
                "Aba",
            )

            self.assertIn(
                "historical observed",
                body["answer_text"],
            )

    def test_rain_question_uses_weather(self):
        self.save_weather()

        with self.api(
            self.configured(
                fews=False,
            )
        ) as (_, client):

            response = self.ask(
                client,
                "Will it rain?",
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertEqual(
                body["status"],
                "answered",
            )

            self.assertEqual(
                body["result"]["source_id"],
                "open_meteo_forecast",
            )

            self.assertTrue(
                body["result"]["rows"][0][
                    "rain_expected"
                ]
            )

            self.assertIn(
                "forecast",
                body["answer_text"].casefold(),
            )

    def test_temperature_without_hour_needs_clarification(
        self,
    ):
        self.save_weather()

        with self.api(
            self.configured(
                fews=False,
            )
        ) as (_, client):

            response = self.ask(
                client,
                "What is the forecast temperature?",
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertEqual(
                body["status"],
                "needs_clarification",
            )

            self.assertIn(
                "specific forecast hour",
                body["answer_text"],
            )

    def test_cross_source_question_is_blocked(
        self,
    ):
        self.save_fews()
        self.save_weather()

        with self.api(
            self.configured()
        ) as (_, client):

            response = self.ask(
                client,
                "Compare maize price with rainfall.",
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertEqual(
                body["status"],
                "reframe_required",
            )

            self.assertIsNone(
                body["result"]
            )

            self.assertIn(
                "one external measure",
                body["answer_text"],
            )

    def test_missing_external_snapshot_is_not_fabricated(
        self,
    ):
        with self.api(
            self.configured(
                fews=False,
                weather=False,
            )
        ) as (_, client):

            response = self.ask(
                client,
                "Will it rain?",
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertEqual(
                body["status"],
                "unsupported",
            )

            self.assertIn(
                "No validated local weather",
                body["answer_text"],
            )

    def test_wave5_question_falls_through_unchanged(
        self,
    ):
        self.save_fews()
        self.save_weather()

        with self.api(
            self.configured()
        ) as (_, client):

            response = self.ask(
                client,
                "Which states have the lowest maize yields?",
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertEqual(
                body["status"],
                "answered",
            )

            self.assertIsNotNone(
                body["question_specification"]
            )

            self.assertEqual(
                body["question_specification"][
                    "metric_id"
                ],
                "median_completed_yield",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
