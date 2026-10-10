import tempfile
from contextlib import closing
import unittest
import json
import sqlite3
from hashlib import sha256
from decimal import Decimal
from pathlib import Path

from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_MODEL,
    OpenMeteoForecastQuery,
)
from packages.data_sources.contracts import (
    SourceDefinition,
    SourceType,
)
from packages.data_sources.registry import SourceRegistry
from packages.data_sources.weather_ingestion import (
    WeatherIngestionError,
    refresh_weather_forecast,
    restore_weather_forecast,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
    WeatherSnapshotStoreError,
    effective_open_meteo_query,
)


class WeatherSnapshotStoreContractTests(
    unittest.TestCase
):

    def test_effective_query_is_explicit_and_stable(
        self,
    ):
        query = OpenMeteoForecastQuery(
            latitude=Decimal("5.10719"),
            longitude=Decimal("7.37063"),
            forecast_days=3,
        )

        self.assertEqual(
            effective_open_meteo_query(
                query
            ),
            {
                "latitude": "5.10719",
                "longitude": "7.37063",
                "forecast_days": 3,
                "model": OPEN_METEO_MODEL,
            },
        )

    def test_effective_query_rejects_wrong_type(
        self,
    ):
        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            effective_open_meteo_query(
                object()
            )

    def test_constructor_does_not_create_database(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            path = (
                Path(temp)
                / "weather.sqlite3"
            )

            store = WeatherSnapshotStore(
                path
            )

            self.assertEqual(
                store.path,
                path.resolve(),
            )
            self.assertFalse(
                path.exists()
            )

    def test_memory_database_is_rejected(
        self,
    ):
        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            WeatherSnapshotStore(
                ":memory:"
            )

    def test_release_directory_is_protected(
        self,
    ):
        path = (
            Path.cwd()
            / "data"
            / "releases"
            / "weather.sqlite3"
        )

        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            WeatherSnapshotStore(
                path
            )

    def test_invalid_size_limit_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            WeatherSnapshotStore(
                "weather.sqlite3",
                max_snapshot_bytes=0,
            )

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    OpenMeteoFetchResult,
)
from packages.data_sources.weather_forecasts import (
    WeatherForecastRecord,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotConflictError,
    WeatherSnapshotScopeError,
    WeatherSnapshotStoreError,
    _decode,
    _encode,
    _validate_result,
    build_open_meteo_snapshot,
)


class WeatherSnapshotValidationTests(
    unittest.TestCase
):

    def _query(self):
        return OpenMeteoForecastQuery(
            latitude=Decimal("5.10719"),
            longitude=Decimal("7.37063"),
            forecast_days=1,
        )

    def _records(
        self,
        *,
        null_temperature=False,
    ):
        start = datetime(
            2026,
            10,
            10,
            0,
            0,
            tzinfo=timezone.utc,
        )

        records = []

        for hour in range(24):
            records.append(
                WeatherForecastRecord(
                    source_id=
                        OPEN_METEO_FORECAST_SOURCE_ID,
                    model=
                        OPEN_METEO_MODEL,
                    requested_latitude=
                        Decimal("5.10719"),
                    requested_longitude=
                        Decimal("7.37063"),
                    grid_latitude=
                        Decimal("5.125"),
                    grid_longitude=
                        Decimal("7.375"),
                    valid_at=
                        start
                        + timedelta(hours=hour),
                    temperature_2m_c=(
                        None
                        if (
                            null_temperature
                            and hour == 0
                        )
                        else Decimal("26.5")
                    ),
                    relative_humidity_2m_pct=
                        Decimal("83"),
                    precipitation_mm=
                        Decimal("0.2"),
                    source_issued_at=None,
                )
            )

        return tuple(
            records
        )

    def _result(
        self,
        *,
        retrieved_at=None,
        null_temperature=False,
        missing_value_count=None,
    ):
        query = self._query()
        records = self._records(
            null_temperature=
                null_temperature
        )

        if retrieved_at is None:
            retrieved_at = datetime(
                2026,
                10,
                10,
                2,
                30,
                tzinfo=timezone.utc,
            )

        snapshot = build_open_meteo_snapshot(
            query,
            records,
            retrieved_at,
        )

        if missing_value_count is None:
            missing_value_count = (
                1
                if null_temperature
                else 0
            )

        return OpenMeteoFetchResult(
            records=records,
            snapshot=snapshot,
            requested_from=
                records[0].valid_at,
            requested_to=
                records[-1].valid_at,
            retrieved_at=
                retrieved_at,
            requests_made=1,
            missing_value_count=
                missing_value_count,
        )

    def test_encoding_is_deterministic(
        self,
    ):
        query = self._query()
        result = self._result()

        self.assertEqual(
            _encode(
                query,
                result,
            ),
            _encode(
                query,
                result,
            ),
        )

    def test_content_identity_ignores_retrieval_time(
        self,
    ):
        query = self._query()
        records = self._records()

        first = build_open_meteo_snapshot(
            query,
            records,
            datetime(
                2026,
                10,
                10,
                2,
                30,
                tzinfo=timezone.utc,
            ),
        )

        second = build_open_meteo_snapshot(
            query,
            records,
            datetime(
                2026,
                10,
                10,
                3,
                30,
                tzinfo=timezone.utc,
            ),
        )

        self.assertEqual(
            first.dataset_version,
            second.dataset_version,
        )

        self.assertNotEqual(
            first.retrieved_at,
            second.retrieved_at,
        )

    def test_query_scope_mismatch_is_rejected(
        self,
    ):
        result = self._result()

        other_query = OpenMeteoForecastQuery(
            latitude=Decimal("5.20000"),
            longitude=Decimal("7.37063"),
            forecast_days=1,
        )

        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            _validate_result(
                other_query,
                result,
            )

    def test_tampered_snapshot_is_rejected(
        self,
    ):
        query = self._query()
        result = self._result()

        tampered_snapshot = replace(
            result.snapshot,
            dataset_version=(
                "open-meteo-hourly-v1:"
                + ("0" * 64)
            ),
        )

        tampered_result = replace(
            result,
            snapshot=tampered_snapshot,
        )

        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            _validate_result(
                query,
                tampered_result,
            )

    def test_null_measurement_is_preserved(
        self,
    ):
        query = self._query()
        result = self._result(
            null_temperature=True
        )

        _validate_result(
            query,
            result,
        )

        self.assertIsNone(
            result.records[0]
            .temperature_2m_c
        )

        self.assertEqual(
            result.missing_value_count,
            1,
        )

    def test_missing_value_count_mismatch_is_rejected(
        self,
    ):
        query = self._query()

        result = self._result(
            missing_value_count=1
        )

        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            _validate_result(
                query,
                result,
            )



    def test_decode_round_trip_preserves_typed_result(
        self,
    ):
        query = self._query()
        result = self._result()

        payload = _encode(
            query,
            result,
        )

        snapshot_id = sha256(
            payload.encode("utf-8")
        ).hexdigest()

        stored = _decode(
            snapshot_id,
            payload,
        )

        self.assertEqual(
            stored.snapshot_id,
            snapshot_id,
        )

        self.assertEqual(
            stored.query,
            query,
        )

        self.assertEqual(
            stored.result,
            result,
        )

    def test_decode_preserves_null_measurement(
        self,
    ):
        query = self._query()
        result = self._result(
            null_temperature=True
        )

        payload = _encode(
            query,
            result,
        )

        snapshot_id = sha256(
            payload.encode("utf-8")
        ).hexdigest()

        stored = _decode(
            snapshot_id,
            payload,
        )

        self.assertIsNone(
            stored.result.records[0]
            .temperature_2m_c
        )

        self.assertEqual(
            stored.result.missing_value_count,
            1,
        )

    def test_decode_rejects_checksum_tampering(
        self,
    ):
        query = self._query()
        result = self._result()

        payload = _encode(
            query,
            result,
        )

        snapshot_id = sha256(
            payload.encode("utf-8")
        ).hexdigest()

        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            _decode(
                snapshot_id,
                payload + " ",
            )

    def test_decode_rejects_rehashed_scope_tampering(
        self,
    ):
        query = self._query()
        result = self._result()

        data = json.loads(
            _encode(
                query,
                result,
            )
        )

        data["query"][
            "latitude"
        ] = "6.00000"

        tampered_payload = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
        )

        tampered_id = sha256(
            tampered_payload.encode("utf-8")
        ).hexdigest()

        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            _decode(
                tampered_id,
                tampered_payload,
            )

    def test_decode_rejects_numeric_decimal_storage(
        self,
    ):
        query = self._query()
        result = self._result()

        data = json.loads(
            _encode(
                query,
                result,
            )
        )

        data["records"][0][
            "temperature_2m_c"
        ] = 26.5

        tampered_payload = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
        )

        tampered_id = sha256(
            tampered_payload.encode("utf-8")
        ).hexdigest()

        with self.assertRaises(
            WeatherSnapshotStoreError
        ):
            _decode(
                tampered_id,
                tampered_payload,
            )



    def test_missing_store_read_does_not_create_file(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            database = (
                Path(temp)
                / "weather.sqlite3"
            )

            store = WeatherSnapshotStore(
                database
            )

            self.assertIsNone(
                store.latest()
            )

            self.assertFalse(
                database.exists()
            )

    def test_invalid_snapshot_id_is_rejected(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            for snapshot_id in (
                "",
                "abc",
                "g" * 64,
                "0" * 63,
                "0" * 65,
            ):
                with self.subTest(
                    snapshot_id=snapshot_id
                ):
                    with self.assertRaises(
                        WeatherSnapshotStoreError
                    ):
                        store.get(
                            snapshot_id
                        )

    def test_empty_sqlite_file_is_no_saved_state(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            database = (
                Path(temp)
                / "weather.sqlite3"
            )

            connection = sqlite3.connect(
                database
            )
            connection.close()

            store = WeatherSnapshotStore(
                database
            )

            self.assertIsNone(
                store.latest()
            )

    def test_unrelated_schema_is_rejected(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            database = (
                Path(temp)
                / "weather.sqlite3"
            )

            with closing(
                sqlite3.connect(
                    database
                )
            ) as connection:
                connection.execute(
                    "CREATE TABLE unrelated "
                    "(value TEXT)"
                )

            store = WeatherSnapshotStore(
                database
            )

            with self.assertRaises(
                WeatherSnapshotStoreError
            ):
                store.latest()

    def test_latest_and_get_read_valid_seeded_snapshot(
        self,
    ):
        query = self._query()
        result = self._result()

        payload = _encode(
            query,
            result,
        )

        snapshot_id = sha256(
            payload.encode("utf-8")
        ).hexdigest()

        scope_json = json.dumps(
            effective_open_meteo_query(
                query
            ),
            sort_keys=True,
            separators=(",", ":"),
        )

        with tempfile.TemporaryDirectory() as temp:
            database = (
                Path(temp)
                / "weather.sqlite3"
            )

            with closing(
                sqlite3.connect(
                    database
                )
            ) as connection:
                connection.execute(
                    "CREATE TABLE "
                    "weather_forecast_snapshots ("
                    "snapshot_id TEXT PRIMARY KEY, "
                    "retrieved_at TEXT NOT NULL UNIQUE, "
                    "scope_json TEXT NOT NULL, "
                    "payload TEXT NOT NULL)"
                )

                connection.execute(
                    "INSERT INTO "
                    "weather_forecast_snapshots "
                    "(snapshot_id, retrieved_at, "
                    "scope_json, payload) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        snapshot_id,
                        result.retrieved_at.isoformat(
                            timespec="microseconds"
                        ),
                        scope_json,
                        payload,
                    ),
                )

                connection.commit()

            store = WeatherSnapshotStore(
                database
            )

            latest = store.latest()
            exact = store.get(
                snapshot_id
            )

            self.assertIsNotNone(
                latest
            )

            self.assertEqual(
                latest,
                exact,
            )

            self.assertEqual(
                latest.query,
                query,
            )

            self.assertEqual(
                latest.result,
                result,
            )



    def test_first_save_round_trips_through_latest_and_get(
        self,
    ):
        query = self._query()
        result = self._result()

        with tempfile.TemporaryDirectory() as temp:
            database = (
                Path(temp)
                / "weather.sqlite3"
            )

            store = WeatherSnapshotStore(
                database
            )

            saved = store.save(
                query,
                result,
            )

            self.assertTrue(
                database.exists()
            )

            self.assertEqual(
                store.latest(),
                saved,
            )

            self.assertEqual(
                store.get(
                    saved.snapshot_id
                ),
                saved,
            )

    def test_exact_replay_is_idempotent(
        self,
    ):
        query = self._query()
        result = self._result()

        with tempfile.TemporaryDirectory() as temp:
            database = (
                Path(temp)
                / "weather.sqlite3"
            )

            store = WeatherSnapshotStore(
                database
            )

            first = store.save(
                query,
                result,
            )

            second = store.save(
                query,
                result,
            )

            self.assertEqual(
                first,
                second,
            )

            with closing(
                sqlite3.connect(
                    database
                )
            ) as connection:
                count = connection.execute(
                    "SELECT COUNT(*) "
                    "FROM weather_forecast_snapshots"
                ).fetchone()[0]

            self.assertEqual(
                count,
                1,
            )

    def test_newer_retrieval_becomes_latest(
        self,
    ):
        query = self._query()

        first = self._result(
            retrieved_at=datetime(
                2026,
                10,
                10,
                2,
                30,
                tzinfo=timezone.utc,
            )
        )

        second = self._result(
            retrieved_at=datetime(
                2026,
                10,
                10,
                3,
                30,
                tzinfo=timezone.utc,
            )
        )

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            store.save(
                query,
                first,
            )

            newest = store.save(
                query,
                second,
            )

            self.assertEqual(
                store.latest(),
                newest,
            )

    def test_older_retrieval_is_retained_without_regressing_latest(
        self,
    ):
        query = self._query()

        older = self._result(
            retrieved_at=datetime(
                2026,
                10,
                10,
                2,
                30,
                tzinfo=timezone.utc,
            )
        )

        newer = self._result(
            retrieved_at=datetime(
                2026,
                10,
                10,
                4,
                30,
                tzinfo=timezone.utc,
            )
        )

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            newest = store.save(
                query,
                newer,
            )

            saved_older = store.save(
                query,
                older,
            )

            self.assertEqual(
                store.latest(),
                newest,
            )

            self.assertEqual(
                store.get(
                    saved_older.snapshot_id
                ),
                saved_older,
            )

    def test_changed_query_scope_is_rejected(
        self,
    ):
        query = self._query()
        result = self._result()

        other_query = OpenMeteoForecastQuery(
            latitude=Decimal("6.00000"),
            longitude=Decimal("7.37063"),
            forecast_days=1,
        )

        other_records = tuple(
            replace(
                record,
                requested_latitude=
                    Decimal("6.00000"),
            )
            for record
            in result.records
        )

        other_result = replace(
            result,
            records=other_records,
            snapshot=build_open_meteo_snapshot(
                other_query,
                other_records,
                result.retrieved_at
                + timedelta(hours=1),
            ),
            retrieved_at=
                result.retrieved_at
                + timedelta(hours=1),
        )

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            original = store.save(
                query,
                result,
            )

            with self.assertRaises(
                WeatherSnapshotScopeError
            ):
                store.save(
                    other_query,
                    other_result,
                )

            self.assertEqual(
                store.latest(),
                original,
            )

    def test_conflicting_content_at_same_retrieval_time_is_rejected(
        self,
    ):
        query = self._query()
        original = self._result()

        changed_records = list(
            original.records
        )

        changed_records[0] = replace(
            changed_records[0],
            temperature_2m_c=
                Decimal("27.5"),
        )

        changed_records = tuple(
            changed_records
        )

        conflicting = replace(
            original,
            records=changed_records,
            snapshot=build_open_meteo_snapshot(
                query,
                changed_records,
                original.retrieved_at,
            ),
        )

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            saved = store.save(
                query,
                original,
            )

            with self.assertRaises(
                WeatherSnapshotConflictError
            ):
                store.save(
                    query,
                    conflicting,
                )

            self.assertEqual(
                store.latest(),
                saved,
            )

    def test_oversized_write_preserves_prior_good_snapshot(
        self,
    ):
        query = self._query()
        original = self._result()

        newer = self._result(
            retrieved_at=
                original.retrieved_at
                + timedelta(hours=1),
        )

        with tempfile.TemporaryDirectory() as temp:
            database = (
                Path(temp)
                / "weather.sqlite3"
            )

            normal_store = WeatherSnapshotStore(
                database
            )

            saved = normal_store.save(
                query,
                original,
            )

            tiny_store = WeatherSnapshotStore(
                database,
                max_snapshot_bytes=1,
            )

            with self.assertRaises(
                WeatherSnapshotStoreError
            ):
                tiny_store.save(
                    query,
                    newer,
                )

            self.assertEqual(
                normal_store.latest(),
                saved,
            )



class ScriptedWeatherClient:

    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def fetch(
        self,
        query,
    ):
        self.calls.append(
            query
        )
        return self.result


class WeatherIngestionTests(
    unittest.TestCase
):

    _query = WeatherSnapshotValidationTests._query
    _records = WeatherSnapshotValidationTests._records
    _result = WeatherSnapshotValidationTests._result

    def test_restore_missing_store_registers_source_without_http(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            registry = SourceRegistry()

            restored = restore_weather_forecast(
                store=store,
                registry=registry,
            )

            self.assertIsNone(
                restored
            )

            self.assertTrue(
                registry.contains(
                    OPEN_METEO_FORECAST_SOURCE_ID
                )
            )

            self.assertIsNone(
                registry.get_snapshot(
                    OPEN_METEO_FORECAST_SOURCE_ID
                )
            )

    def test_restore_saved_snapshot_publishes_without_http(
        self,
    ):
        query = self._query()
        result = self._result()

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            saved = store.save(
                query,
                result,
            )

            registry = SourceRegistry()

            restored = restore_weather_forecast(
                store=store,
                registry=registry,
            )

            self.assertEqual(
                restored,
                saved,
            )

            self.assertEqual(
                registry.get_snapshot(
                    OPEN_METEO_FORECAST_SOURCE_ID
                ),
                result.snapshot,
            )

    def test_refresh_persists_before_registry_publication(
        self,
    ):
        query = self._query()
        result = self._result()

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            registry = SourceRegistry()

            client = ScriptedWeatherClient(
                result
            )

            returned = refresh_weather_forecast(
                query,
                store=store,
                registry=registry,
                client=client,
            )

            self.assertEqual(
                returned,
                result,
            )

            self.assertEqual(
                client.calls,
                [query],
            )

            latest = store.latest()

            self.assertIsNotNone(
                latest
            )

            self.assertEqual(
                registry.get_snapshot(
                    OPEN_METEO_FORECAST_SOURCE_ID
                ),
                latest.result.snapshot,
            )

    def test_refresh_rejects_different_store_scope_before_http(
        self,
    ):
        query = self._query()
        result = self._result()

        other_query = OpenMeteoForecastQuery(
            latitude=Decimal("6.00000"),
            longitude=Decimal("7.37063"),
            forecast_days=1,
        )

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            store.save(
                query,
                result,
            )

            registry = SourceRegistry()

            client = ScriptedWeatherClient(
                result
            )

            with self.assertRaises(
                WeatherSnapshotScopeError
            ):
                refresh_weather_forecast(
                    other_query,
                    store=store,
                    registry=registry,
                    client=client,
                )

            self.assertEqual(
                client.calls,
                [],
            )

    def test_restore_older_snapshot_does_not_regress_registry(
        self,
    ):
        query = self._query()

        older = self._result(
            retrieved_at=datetime(
                2026,
                10,
                10,
                2,
                30,
                tzinfo=timezone.utc,
            )
        )

        newer = self._result(
            retrieved_at=datetime(
                2026,
                10,
                10,
                4,
                30,
                tzinfo=timezone.utc,
            )
        )

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            store.save(
                query,
                older,
            )

            registry = SourceRegistry()

            registry_definition = (
                restore_weather_forecast(
                    store=store,
                    registry=registry,
                )
            )

            self.assertIsNotNone(
                registry_definition
            )

            registry.record_snapshot(
                newer.snapshot
            )

            restored = restore_weather_forecast(
                store=store,
                registry=registry,
            )

            self.assertIsNotNone(
                restored
            )

            self.assertEqual(
                registry.get_snapshot(
                    OPEN_METEO_FORECAST_SOURCE_ID
                ),
                newer.snapshot,
            )

    def test_custom_stale_threshold_is_reflected_in_definition(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            registry = SourceRegistry()

            restore_weather_forecast(
                store=store,
                registry=registry,
                stale_after_hours=12,
            )

            definition = (
                registry.get_definition(
                    OPEN_METEO_FORECAST_SOURCE_ID
                )
            )

            self.assertEqual(
                definition.stale_after_hours,
                12,
            )

    def test_conflicting_registry_definition_is_rejected(
        self,
    ):
        registry = SourceRegistry()

        bad_definition = SourceDefinition(
            source_id=
                OPEN_METEO_FORECAST_SOURCE_ID,
            display_name=
                "Different weather source",
            source_type=
                SourceType.WEATHER_FORECAST,
            provider=
                "Other",
            geographic_scope=
                "Different",
            methodology_note=
                "Different",
            attribution=
                "Different",
            stale_after_hours=6,
        )

        registry.register(
            bad_definition
        )

        with tempfile.TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp)
                / "weather.sqlite3"
            )

            with self.assertRaises(
                WeatherIngestionError
            ):
                restore_weather_forecast(
                    store=store,
                    registry=registry,
                )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
