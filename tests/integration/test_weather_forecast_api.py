from contextlib import ExitStack, contextmanager
from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.app.core.settings import AppSettings
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    OPEN_METEO_MODEL,
    OpenMeteoFetchResult,
    OpenMeteoForecastQuery,
)
from packages.data_sources.weather_forecasts import (
    WeatherForecastRecord,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
    build_open_meteo_snapshot,
    effective_open_meteo_query,
)


runtime_module = importlib.import_module(
    "apps.api.app.core.runtime"
)
main_module = importlib.import_module(
    "apps.api.app.main"
)
health_module = importlib.import_module(
    "apps.api.app.routes.health"
)
sources_module = importlib.import_module(
    "apps.api.app.routes.sources"
)
weather_module = importlib.import_module(
    "apps.api.app.routes.weather_forecast"
)


def sample_fetch(
    retrieved_at: datetime,
):
    query = OpenMeteoForecastQuery(
        latitude=Decimal("5.10719"),
        longitude=Decimal("7.37063"),
        forecast_days=3,
    )

    start = datetime(
        2026,
        10,
        10,
        0,
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
                start
                + timedelta(hours=hour),
            temperature_2m_c=
                Decimal(
                    str(
                        25
                        + hour / 10
                    )
                ),
            relative_humidity_2m_pct=
                Decimal("83"),
            precipitation_mm=(
                None
                if hour == 6
                else Decimal("0.2")
            ),
            source_issued_at=None,
        )
        for hour in range(72)
    )

    snapshot = build_open_meteo_snapshot(
        query,
        records,
        retrieved_at,
    )

    result = OpenMeteoFetchResult(
        records=records,
        snapshot=snapshot,
        requested_from=
            records[0].valid_at,
        requested_to=
            records[-1].valid_at,
        retrieved_at=
            retrieved_at,
        requests_made=1,
        missing_value_count=1,
    )

    return query, result


class WeatherForecastAPITests(
    unittest.TestCase
):

    def setUp(
        self,
    ):
        self.directory = TemporaryDirectory()
        self.addCleanup(
            self.directory.cleanup
        )

        self.path = (
            Path(
                self.directory.name
            )
            / "weather.sqlite3"
        )

        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            self.settings = (
                AppSettings.from_env()
            )

        self.now = datetime(
            2026,
            10,
            10,
            12,
            0,
            tzinfo=timezone.utc,
        )

        contract_clock = self.enterContext(
            patch(
                "packages.data_sources.contracts.datetime",
                wraps=datetime,
            )
        )

        contract_clock.now.return_value = (
            self.now
        )

        self.network = self.enterContext(
            patch(
                "packages.data_sources.providers."
                "open_meteo_forecast._get_json",
                side_effect=AssertionError(
                    "Weather API must never query Open-Meteo."
                ),
            )
        )

    def save(
        self,
        *,
        retrieved_at=None,
    ):
        query, result = sample_fetch(
            retrieved_at
            or self.now
        )

        stored = WeatherSnapshotStore(
            self.path
        ).save(
            query,
            result,
        )

        return query, result, stored

    def configured(
        self,
    ):
        return replace(
            self.settings,
            weather_snapshot_path=
                str(
                    self.path
                ),
        )

    @contextmanager
    def api(
        self,
        configured_settings=None,
    ):
        runtime = (
            runtime_module.AgDARuntime()
        )

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    runtime_module,
                    "settings",
                    configured_settings
                    or self.configured(),
                )
            )

            for module in (
                main_module,
                health_module,
                sources_module,
                weather_module,
            ):
                stack.enter_context(
                    patch.object(
                        module,
                        "runtime",
                        runtime,
                    )
                )

            client = stack.enter_context(
                TestClient(
                    main_module.app
                )
            )

            yield runtime, client

        self.network.assert_not_called()

    def assert_core_ready(
        self,
        client,
    ):
        response = client.get(
            "/v1/ready"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        body = response.json()

        self.assertTrue(
            body["ready"]
        )

        self.assertEqual(
            body["data_version"],
            "wave5_v1",
        )

        self.assertFalse(
            body["external_sources"][
                "affects_core_readiness"
            ]
        )

    def test_loaded_snapshot_returns_records_and_provenance(
        self,
    ):
        query, result, stored = self.save()

        with self.api() as (
            _,
            client,
        ):
            response = client.get(
                "/v1/weather-forecast"
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertEqual(
                body["snapshot_id"],
                stored.snapshot_id,
            )

            self.assertEqual(
                body[
                    "weather_snapshot_restore_status"
                ],
                "loaded",
            )

            self.assertEqual(
                body["filters"],
                {},
            )

            self.assertEqual(
                body["total"],
                72,
            )

            self.assertEqual(
                body["returned_count"],
                50,
            )

            self.assertEqual(
                body["next_offset"],
                50,
            )

            source = body["source"]

            self.assertEqual(
                source["query"],
                effective_open_meteo_query(
                    query
                ),
            )

            self.assertEqual(
                source["source_id"],
                OPEN_METEO_FORECAST_SOURCE_ID,
            )

            self.assertEqual(
                source["record_count"],
                72,
            )

            self.assertEqual(
                source["freshness"],
                "fresh",
            )

            self.assertEqual(
                source["dataset_version"],
                result.snapshot.dataset_version,
            )

            first = body["records"][0]

            self.assertEqual(
                set(first),
                {
                    field.name
                    for field
                    in fields(
                        WeatherForecastRecord
                    )
                },
            )

            self.assertEqual(
                first["valid_at"],
                "2026-10-10T00:00:00Z",
            )

            self.assertEqual(
                first[
                    "requested_latitude"
                ],
                "5.10719",
            )

            self.assertIsNone(
                body["records"][6][
                    "precipitation_mm"
                ]
            )

            self.assertNotIn(
                str(
                    self.path
                ),
                json.dumps(
                    body
                ),
            )

    def test_pagination_preserves_snapshot_pin(
        self,
    ):
        _, _, stored = self.save()

        with self.api() as (
            _,
            client,
        ):
            first = client.get(
                "/v1/weather-forecast",
                params={
                    "limit": 10,
                },
            ).json()

            second = client.get(
                "/v1/weather-forecast",
                params={
                    "limit": 10,
                    "offset": 10,
                    "snapshot_id":
                        first["snapshot_id"],
                },
            )

            self.assertEqual(
                second.status_code,
                200,
            )

            body = second.json()

            self.assertEqual(
                body["snapshot_id"],
                stored.snapshot_id,
            )

            self.assertEqual(
                body["offset"],
                10,
            )

            self.assertEqual(
                body["returned_count"],
                10,
            )

            self.assertEqual(
                body["next_offset"],
                20,
            )

    def test_validity_filters_are_inclusive(
        self,
    ):
        self.save()

        with self.api() as (
            _,
            client,
        ):
            response = client.get(
                "/v1/weather-forecast",
                params={
                    "valid_from":
                        "2026-10-10T05:00:00Z",
                    "valid_to":
                        "2026-10-10T07:00:00Z",
                },
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            body = response.json()

            self.assertEqual(
                body["total"],
                3,
            )

            self.assertEqual(
                [
                    record["valid_at"]
                    for record
                    in body["records"]
                ],
                [
                    "2026-10-10T05:00:00Z",
                    "2026-10-10T06:00:00Z",
                    "2026-10-10T07:00:00Z",
                ],
            )

    def test_naive_validity_filter_is_rejected(
        self,
    ):
        self.save()

        with self.api() as (
            _,
            client,
        ):
            response = client.get(
                "/v1/weather-forecast",
                params={
                    "valid_from":
                        "2026-10-10T05:00:00",
                },
            )

            self.assertEqual(
                response.status_code,
                422,
            )

    def test_reversed_validity_range_is_rejected(
        self,
    ):
        self.save()

        with self.api() as (
            _,
            client,
        ):
            response = client.get(
                "/v1/weather-forecast",
                params={
                    "valid_from":
                        "2026-10-10T08:00:00Z",
                    "valid_to":
                        "2026-10-10T07:00:00Z",
                },
            )

            self.assertEqual(
                response.status_code,
                422,
            )

    def test_unknown_snapshot_pin_is_conflict(
        self,
    ):
        self.save()

        with self.api() as (
            _,
            client,
        ):
            response = client.get(
                "/v1/weather-forecast",
                params={
                    "snapshot_id":
                        "0" * 64,
                },
            )

            self.assertEqual(
                response.status_code,
                409,
            )

    def test_missing_snapshot_is_unavailable_but_core_ready(
        self,
    ):
        with self.api() as (
            _,
            client,
        ):
            response = client.get(
                "/v1/weather-forecast"
            )

            self.assertEqual(
                response.status_code,
                503,
            )

            self.assert_core_ready(
                client
            )

            self.assertFalse(
                self.path.exists()
            )

    def test_stale_snapshot_remains_readable(
        self,
    ):
        self.save(
            retrieved_at=
                self.now
                - timedelta(hours=7)
        )

        configured = replace(
            self.configured(),
            weather_stale_after_hours=6,
        )

        with self.api(
            configured
        ) as (
            _,
            client,
        ):
            response = client.get(
                "/v1/weather-forecast"
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            self.assertEqual(
                response.json()[
                    "source"
                ][
                    "freshness"
                ],
                "stale",
            )

            self.assert_core_ready(
                client
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
