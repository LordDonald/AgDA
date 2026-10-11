from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import importlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    OPEN_METEO_MODEL,
    OpenMeteoFetchResult,
    WeatherClientError,
)
from packages.data_sources.weather_forecasts import (
    WeatherForecastRecord,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
    build_open_meteo_snapshot,
)


command_spec = importlib.util.spec_from_file_location(
    "agda_weather_ingestion_command",
    Path(__file__).resolve().parents[2]
    / "tools"
    / "ingest_weather_forecast.py",
)

command = importlib.util.module_from_spec(
    command_spec
)

command_spec.loader.exec_module(
    command
)

store_module = importlib.import_module(
    "packages.data_sources.weather_snapshot_store"
)


class FakeWeatherClient:

    def __init__(
        self,
        *,
        limits,
        retrieved_at,
        failure=None,
    ):
        self.limits = limits
        self.retrieved_at = retrieved_at
        self.failure = failure
        self.calls = []

    def fetch(
        self,
        query,
    ):
        self.calls.append(
            query
        )

        if self.failure is not None:
            raise self.failure

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
            for hour in range(
                query.forecast_days * 24
            )
        )

        snapshot = build_open_meteo_snapshot(
            query,
            records,
            self.retrieved_at,
        )

        return OpenMeteoFetchResult(
            records=records,
            snapshot=snapshot,
            requested_from=
                records[0].valid_at,
            requested_to=
                records[-1].valid_at,
            retrieved_at=
                self.retrieved_at,
            requests_made=1,
            missing_value_count=0,
        )


class WeatherIngestionCommandTests(
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
            / "snapshots"
            / "weather.sqlite3"
        )

        self.retrieved_at = datetime(
            2026,
            10,
            10,
            12,
            0,
            tzinfo=timezone.utc,
        )

        self.network = self.enterContext(
            patch(
                "packages.data_sources.providers."
                "open_meteo_forecast._get_json",
                side_effect=AssertionError(
                    "Command tests must never "
                    "contact Open-Meteo."
                ),
            )
        )

    def tearDown(
        self,
    ):
        self.network.assert_not_called()

    def invoke(
        self,
        *arguments,
    ):
        output = StringIO()

        with redirect_stdout(
            output
        ):
            status = command.main(
                [
                    "--database",
                    str(
                        self.path
                    ),
                    *arguments,
                ]
            )

        return (
            status,
            output.getvalue(),
        )

    def live(
        self,
        *,
        failure=None,
        arguments=(),
    ):
        clients = []

        def client_factory(
            *,
            limits,
        ):
            client = FakeWeatherClient(
                limits=limits,
                retrieved_at=
                    self.retrieved_at,
                failure=failure,
            )

            clients.append(
                client
            )

            return client

        with patch.object(
            command,
            "OpenMeteoForecastClient",
            side_effect=
                client_factory,
        ):
            status, output = self.invoke(
                "--live",
                *arguments,
            )

        return (
            status,
            output,
            clients,
        )

    def database_hash(
        self,
    ):
        return sha256(
            self.path.read_bytes()
        ).hexdigest()

    def test_no_action_never_opens_store_or_client(
        self,
    ):
        with patch.object(
            command,
            "WeatherSnapshotStore",
        ) as store, patch.object(
            command,
            "OpenMeteoForecastClient",
        ) as client:

            status, output = self.invoke()

        self.assertEqual(
            status,
            0,
        )

        self.assertIn(
            "Choose --live",
            output,
        )

        store.assert_not_called()
        client.assert_not_called()

        self.assertFalse(
            self.path.parent.exists()
        )

    def test_inspect_missing_store_creates_no_files_or_client(
        self,
    ):
        with patch.object(
            command,
            "OpenMeteoForecastClient",
        ) as client:

            status, output = self.invoke(
                "--inspect"
            )

        self.assertEqual(
            status,
            0,
        )

        payload = json.loads(
            output
        )

        self.assertEqual(
            payload["status"],
            "missing",
        )

        self.assertIsNone(
            payload["snapshot"]
        )

        self.assertIsNone(
            payload["query"]
        )

        self.assertIsNone(
            payload["requests_made"]
        )

        self.assertFalse(
            self.path.parent.exists()
        )

        client.assert_not_called()

    def test_live_saves_and_inspect_returns_same_snapshot_without_http(
        self,
    ):
        status, output, clients = self.live(
            arguments=(
                "--days",
                "3",
                "--max-records",
                "100",
                "--timeout-seconds",
                "7",
                "--max-response-bytes",
                "4096",
            )
        )

        self.assertEqual(
            status,
            0,
        )

        saved = json.loads(
            output
        )

        self.assertEqual(
            saved["status"],
            "stored",
        )

        self.assertEqual(
            saved["fetched_record_count"],
            72,
        )

        self.assertEqual(
            saved["requests_made"],
            1,
        )

        self.assertEqual(
            saved["missing_value_count"],
            0,
        )

        self.assertEqual(
            saved["query"],
            {
                "latitude":
                    "5.10719",
                "longitude":
                    "7.37063",
                "forecast_days":
                    3,
                "model":
                    OPEN_METEO_MODEL,
            },
        )

        self.assertEqual(
            saved["snapshot"][
                "retrieved_at"
            ],
            self.retrieved_at.isoformat(),
        )

        self.assertEqual(
            clients[0].limits.max_records,
            100,
        )

        self.assertEqual(
            clients[0].limits.timeout_seconds,
            7.0,
        )

        self.assertEqual(
            clients[0].limits.max_response_bytes,
            4096,
        )

        self.assertEqual(
            len(
                clients[0].calls
            ),
            1,
        )

        checksum = (
            self.database_hash()
        )

        with patch.object(
            command,
            "OpenMeteoForecastClient",
        ) as client:

            inspect_status, inspect_output = (
                self.invoke(
                    "--inspect"
                )
            )

        self.assertEqual(
            inspect_status,
            0,
        )

        inspected = json.loads(
            inspect_output
        )

        self.assertEqual(
            inspected["status"],
            "loaded",
        )

        for field in (
            "snapshot_id",
            "snapshot",
            "query",
        ):
            self.assertEqual(
                inspected[field],
                saved[field],
            )

        self.assertIsNone(
            inspected[
                "fetched_record_count"
            ]
        )

        self.assertIsNone(
            inspected[
                "requests_made"
            ]
        )

        self.assertIsNone(
            inspected[
                "missing_value_count"
            ]
        )

        self.assertEqual(
            self.database_hash(),
            checksum,
        )

        self.assertEqual(
            WeatherSnapshotStore(
                self.path
            ).latest().snapshot_id,
            saved["snapshot_id"],
        )

        client.assert_not_called()

    def test_http_failure_preserves_prior_snapshot(
        self,
    ):
        status, output, _ = self.live()

        self.assertEqual(
            status,
            0,
        )

        previous = json.loads(
            output
        )

        checksum = (
            self.database_hash()
        )

        self.retrieved_at = (
            self.retrieved_at
            + timedelta(hours=1)
        )

        status, output, clients = self.live(
            failure=WeatherClientError(
                "Synthetic weather failure"
            )
        )

        self.assertEqual(
            status,
            2,
        )

        self.assertIn(
            "Weather ingestion failed",
            output,
        )

        self.assertIn(
            "Synthetic weather failure",
            output,
        )

        self.assertEqual(
            self.database_hash(),
            checksum,
        )

        self.assertEqual(
            WeatherSnapshotStore(
                self.path
            ).latest().snapshot_id,
            previous["snapshot_id"],
        )

        self.assertEqual(
            len(
                clients[0].calls
            ),
            1,
        )

    def test_initial_http_failure_creates_no_database(
        self,
    ):
        status, output, clients = self.live(
            failure=WeatherClientError(
                "Synthetic timeout"
            )
        )

        self.assertEqual(
            status,
            2,
        )

        self.assertIn(
            "Weather ingestion failed",
            output,
        )

        self.assertFalse(
            self.path.parent.exists()
        )

        self.assertEqual(
            len(
                clients[0].calls
            ),
            1,
        )

    def test_release_database_path_is_rejected_before_http(
        self,
    ):
        protected = (
            Path(
                store_module.__file__
            )
            .resolve()
            .parents[2]
            / "data"
            / "releases"
            / "test_weather_ingestion_command_forbidden.sqlite3"
        )

        self.assertFalse(
            protected.exists()
        )

        output = StringIO()

        with patch.object(
            command,
            "OpenMeteoForecastClient",
        ) as client, redirect_stdout(
            output
        ):

            status = command.main(
                [
                    "--live",
                    "--database",
                    str(
                        protected
                    ),
                ]
            )

        self.assertEqual(
            status,
            2,
        )

        self.assertIn(
            "data/releases",
            output.getvalue(),
        )

        self.assertFalse(
            protected.exists()
        )

        client.assert_not_called()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
