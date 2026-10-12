from contextlib import ExitStack, contextmanager
from dataclasses import replace
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
internal_external_sources_module = importlib.import_module(
    "apps.api.app.routes.internal_external_sources"
)


def sample_weather_fetch(
    retrieved_at: datetime,
):
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
                Decimal("26.5"),
            relative_humidity_2m_pct=
                Decimal("83"),
            precipitation_mm=
                Decimal("0.2"),
            source_issued_at=None,
        )
        for hour in range(24)
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
        missing_value_count=0,
    )

    return query, result


class WeatherSnapshotRuntimeTests(
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
                    "Runtime must never query Open-Meteo."
                ),
            )
        )

    def configured(
        self,
        *,
        path=None,
        stale_after_hours=6,
    ):
        return replace(
            self.settings,
            weather_snapshot_path=
                str(
                    path
                    or self.path
                ),
            weather_stale_after_hours=
                stale_after_hours,
        )

    def save(
        self,
        *,
        retrieved_at=None,
    ):
        query, result = sample_weather_fetch(
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

    @contextmanager
    def api(
        self,
        configured_settings,
    ):
        runtime = (
            runtime_module.AgDARuntime()
        )

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    runtime_module,
                    "settings",
                    configured_settings,
                )
            )

            stack.enter_context(
                patch.object(
                    internal_external_sources_module,
                    "settings",
                    configured_settings,
                )
            )

            for module in (
                main_module,
                health_module,
                sources_module,
                internal_external_sources_module,
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

    def assert_ready(
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

    def test_disabled_weather_restore_never_opens_store(
        self,
    ):
        with patch.object(
            runtime_module,
            "WeatherSnapshotStore",
        ) as constructor:

            with self.api(
                self.settings
            ) as (
                runtime,
                client,
            ):
                self.assert_ready(
                    client
                )

                self.assertEqual(
                    runtime.weather_snapshot_restore_status,
                    "disabled",
                )

                payload = client.get(
                    "/v1/sources"
                ).json()

                self.assertEqual(
                    payload[
                        "external_sources"
                    ][
                        "weather_snapshot_restore_status"
                    ],
                    "disabled",
                )

                # Existing FEWS compatibility field
                # must retain its original meaning.
                self.assertEqual(
                    payload[
                        "external_sources"
                    ][
                        "snapshot_restore_status"
                    ],
                    "disabled",
                )

            constructor.assert_not_called()

    def test_missing_weather_store_registers_unknown_source(
        self,
    ):
        with self.api(
            self.configured()
        ) as (
            runtime,
            client,
        ):
            self.assert_ready(
                client
            )

            payload = client.get(
                "/v1/sources"
            ).json()

            self.assertEqual(
                runtime.weather_snapshot_restore_status,
                "missing",
            )

            self.assertEqual(
                payload[
                    "external_sources"
                ][
                    "weather_snapshot_restore_status"
                ],
                "missing",
            )

            source = next(
                source
                for source
                in payload["sources"]
                if source["source_id"]
                == OPEN_METEO_FORECAST_SOURCE_ID
            )

            self.assertEqual(
                source["freshness"],
                "unknown",
            )

            self.assertIsNone(
                source["record_count"]
            )

            self.assertFalse(
                self.path.exists()
            )

    def test_saved_weather_snapshot_restores_query_and_provenance(
        self,
    ):
        query, result, stored = (
            self.save()
        )

        with self.api(
            self.configured()
        ) as (
            runtime,
            client,
        ):
            self.assert_ready(
                client
            )

            payload = client.get(
                "/v1/sources"
            ).json()

            source = next(
                source
                for source
                in payload["sources"]
                if source["source_id"]
                == OPEN_METEO_FORECAST_SOURCE_ID
            )

            self.assertEqual(
                source["query"],
                effective_open_meteo_query(
                    query
                ),
            )

            self.assertEqual(
                source["record_count"],
                24,
            )

            self.assertEqual(
                source["freshness"],
                "fresh",
            )

            self.assertEqual(
                runtime.weather_snapshot_restore_status,
                "loaded",
            )

            self.assertEqual(
                runtime._weather_forecast_snapshot,
                stored,
            )

            self.assertEqual(
                runtime.source_registry.get_snapshot(
                    OPEN_METEO_FORECAST_SOURCE_ID
                ),
                result.snapshot,
            )

    def test_corrupt_weather_store_does_not_break_core_readiness(
        self,
    ):
        self.path.write_text(
            "private storage detail",
            encoding="utf-8",
        )

        with self.assertLogs(
            runtime_module.logger,
            level="WARNING",
        ) as logs:

            with self.api(
                self.configured()
            ) as (
                runtime,
                client,
            ):
                self.assert_ready(
                    client
                )

                self.assertEqual(
                    runtime.weather_snapshot_restore_status,
                    "error",
                )

                payload = client.get(
                    "/v1/sources"
                ).json()

                self.assertEqual(
                    payload[
                        "external_sources"
                    ][
                        "weather_snapshot_restore_status"
                    ],
                    "error",
                )

                serialized = json.dumps(
                    payload
                )

                self.assertNotIn(
                    str(
                        self.path
                    ),
                    serialized,
                )

                self.assertNotIn(
                    "private storage detail",
                    serialized,
                )

        self.assertTrue(
            any(
                "Weather snapshot restore failed"
                in entry
                for entry
                in logs.output
            )
        )

    def test_stale_weather_does_not_break_core_readiness(
        self,
    ):
        self.save(
            retrieved_at=
                self.now
                - timedelta(hours=7)
        )

        with self.api(
            self.configured(
                stale_after_hours=6
            )
        ) as (
            runtime,
            client,
        ):
            self.assert_ready(
                client
            )

            payload = client.get(
                "/v1/sources"
            ).json()

            source = next(
                source
                for source
                in payload["sources"]
                if source["source_id"]
                == OPEN_METEO_FORECAST_SOURCE_ID
            )

            self.assertEqual(
                source["freshness"],
                "stale",
            )

            self.assertEqual(
                runtime.weather_snapshot_restore_status,
                "loaded",
            )


    def test_internal_reload_adopts_newer_weather_snapshot_without_restart(
        self,
    ):
        operations_token = (
            "phase27-real-runtime-token"
        )

        _, _, older = self.save(
            retrieved_at=
                self.now
                - timedelta(hours=1)
        )

        configured_settings = replace(
            self.configured(),
            operations_token=
                operations_token,
        )

        with self.api(
            configured_settings
        ) as (
            runtime,
            client,
        ):
            self.assertEqual(
                runtime._weather_forecast_snapshot,
                older,
            )

            self.assert_ready(
                client
            )

            _, _, newer = self.save(
                retrieved_at=self.now
            )

            # Writing the newer snapshot to SQLite
            # must not mutate the running process
            # until explicit adoption occurs.
            self.assertEqual(
                runtime._weather_forecast_snapshot,
                older,
            )

            response = client.post(
                (
                    "/v1/internal/"
                    "external-sources/reload"
                ),
                json={
                    "source": "weather",
                },
                headers={
                    "X-AgDA-Operations-Token":
                        operations_token,
                },
            )

            self.assertEqual(
                response.status_code,
                200,
                response.text,
            )

            payload = response.json()

            self.assertEqual(
                payload["status"],
                "reloaded",
            )

            self.assertEqual(
                payload["source"],
                "weather",
            )

            self.assertIsNone(
                payload["fews"]
            )

            self.assertEqual(
                payload["weather"][
                    "before_snapshot_id"
                ],
                older.snapshot_id,
            )

            self.assertEqual(
                payload["weather"][
                    "after_snapshot_id"
                ],
                newer.snapshot_id,
            )

            self.assertTrue(
                payload["weather"][
                    "changed"
                ]
            )

            self.assertEqual(
                payload["weather"][
                    "restore_status"
                ],
                "loaded",
            )

            self.assertTrue(
                payload["core_ready"]
            )

            # Same process, no restart:
            # active runtime now holds the
            # newly persisted snapshot.
            self.assertEqual(
                runtime._weather_forecast_snapshot,
                newer,
            )

            self.assert_ready(
                client
            )

            sources = client.get(
                "/v1/sources"
            )

            self.assertEqual(
                sources.status_code,
                200,
            )

            weather = next(
                source
                for source
                in sources.json()[
                    "sources"
                ]
                if source["source_id"]
                == OPEN_METEO_FORECAST_SOURCE_ID
            )

            self.assertEqual(
                weather["retrieved_at"],
                self.now.isoformat(),
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
