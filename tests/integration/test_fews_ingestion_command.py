"""Offline command checks using the real client, service, and temporary SQLite stores."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
from hashlib import sha256
import importlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from packages.data_sources.providers.fews_http_client import (
    FewsHTTPError,
    FewsMarketPriceClient,
)
from packages.data_sources.snapshot_store import FewsSnapshotStore


command_spec = importlib.util.spec_from_file_location(
    "agda_fews_ingestion_command",
    Path(__file__).resolve().parents[2] / "tools" / "ingest_fews_market_prices.py",
)
command = importlib.util.module_from_spec(command_spec)
command_spec.loader.exec_module(command)
store_module = importlib.import_module("packages.data_sources.snapshot_store")


def sample_page():
    return {
        "results": [{
            "period_date": "2025-01-31", "country_code": "NG", "market": "Aba",
            "market_id": 57682, "cpcv2": "R01122AC", "product": "Maize Grain (White)",
            "price_type": "Retail", "unit": "kg", "currency": "NGN",
            "value": "998.10", "source_organization": "FEWS NET",
            "modified": "2026-07-21T23:02:24",
        }],
        "next": None,
    }


class FewsIngestionCommandTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "snapshots" / "fews.sqlite3"
        self.retrieved_at = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
        self.network = self.enterContext(patch(
            "packages.data_sources.providers.fews_http_client._get_json",
            side_effect=AssertionError("Command tests must never contact FEWS."),
        ))

    def tearDown(self):
        self.network.assert_not_called()

    def invoke(self, *arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = command.main(["--database", str(self.path), *arguments])
        return status, output.getvalue()

    def live(self, *, page=None, failure=None, arguments=()):
        transport = Mock(side_effect=failure) if failure else Mock(return_value=page or sample_page())
        clients = []

        def client_factory(*, limits):
            client = FewsMarketPriceClient(
                limits=limits, get_json=transport, clock=lambda: self.retrieved_at,
            )
            clients.append(client)
            return client

        with patch.object(command, "FewsMarketPriceClient", side_effect=client_factory):
            status, output = self.invoke("--live", *arguments)
        return status, output, transport, clients

    def database_hash(self):
        return sha256(self.path.read_bytes()).hexdigest()

    def test_no_action_never_opens_store_or_client(self):
        with patch.object(command, "FewsSnapshotStore") as store, patch.object(
            command, "FewsMarketPriceClient",
        ) as client:
            status, output = self.invoke()
        self.assertEqual(status, 0)
        self.assertIn("Choose --live", output)
        store.assert_not_called()
        client.assert_not_called()
        self.assertFalse(self.path.parent.exists())

    def test_inspect_missing_store_does_not_create_files_or_client(self):
        with patch.object(command, "FewsMarketPriceClient") as client:
            status, output = self.invoke("--inspect")
        self.assertEqual(status, 0)
        payload = json.loads(output)
        self.assertEqual(payload["status"], "missing")
        self.assertIsNone(payload["snapshot"])
        self.assertIsNone(payload["query"])
        self.assertIsNone(payload["requests_made"])
        self.assertFalse(self.path.parent.exists())
        client.assert_not_called()

    def test_live_saves_and_fresh_inspect_returns_same_snapshot_without_http(self):
        status, output, transport, clients = self.live(arguments=(
            "--page-size", "5", "--max-pages", "2", "--max-requests", "2", "--max-records", "10",
        ))
        self.assertEqual(status, 0)
        saved = json.loads(output)
        self.assertEqual(saved["status"], "stored")
        self.assertEqual(saved["fetched_record_count"], 1)
        self.assertEqual(saved["pages_fetched"], 1)
        self.assertEqual(saved["requests_made"], 1)
        self.assertEqual(saved["query"], {
            "country_code": "NG", "schedule": "Monthly", "start_date": "2025-01-01",
            "end_date": "2025-01-31", "price_type": "Retail", "cpcv2": "R01122AC",
        })
        self.assertEqual(saved["snapshot"]["retrieved_at"], self.retrieved_at.isoformat())
        self.assertEqual(saved["snapshot"]["refreshed_at"], self.retrieved_at.isoformat())
        self.assertEqual(clients[0].limits.page_size, 5)
        self.assertEqual(clients[0].limits.max_pages, 2)
        self.assertEqual(clients[0].limits.max_requests, 2)
        self.assertEqual(clients[0].limits.max_records, 10)
        transport.assert_called_once()
        self.assertIn("schedule=Monthly", transport.call_args.args[0])
        checksum = self.database_hash()
        with patch.object(command, "FewsMarketPriceClient") as client:
            inspect_status, inspect_output = self.invoke("--inspect")
        self.assertEqual(inspect_status, 0)
        inspected = json.loads(inspect_output)
        self.assertEqual(inspected["status"], "loaded")
        for field in ("snapshot_id", "snapshot", "query"):
            self.assertEqual(inspected[field], saved[field])
        self.assertIsNone(inspected["fetched_record_count"])
        self.assertIsNone(inspected["requests_made"])
        self.assertEqual(self.database_hash(), checksum)
        self.assertEqual(FewsSnapshotStore(self.path).latest().snapshot_id, saved["snapshot_id"])
        client.assert_not_called()

    def test_empty_live_fetch_retains_prior_snapshot_and_database(self):
        status, output, _, _ = self.live()
        self.assertEqual(status, 0)
        previous = json.loads(output)
        checksum = self.database_hash()
        self.retrieved_at = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
        status, output, transport, _ = self.live(page={"results": [], "next": None})
        self.assertEqual(status, 0)
        payload = json.loads(output)
        self.assertEqual(payload["status"], "no_data_previous_snapshot_retained")
        self.assertEqual(payload["fetched_record_count"], 0)
        self.assertEqual(payload["requests_made"], 1)
        for field in ("snapshot_id", "snapshot", "query"):
            self.assertEqual(payload[field], previous[field])
        self.assertEqual(self.database_hash(), checksum)
        transport.assert_called_once()

    def test_empty_initial_live_fetch_creates_no_database(self):
        status, output, transport, _ = self.live(page={"results": [], "next": None})
        self.assertEqual(status, 0)
        payload = json.loads(output)
        self.assertEqual(payload["status"], "no_data")
        self.assertIsNone(payload["snapshot"])
        self.assertIsNone(payload["snapshot_id"])
        self.assertFalse(self.path.parent.exists())
        transport.assert_called_once()

    def test_http_failure_returns_two_without_changing_prior_snapshot(self):
        status, output, _, _ = self.live()
        self.assertEqual(status, 0)
        previous = json.loads(output)
        checksum = self.database_hash()
        status, output, transport, _ = self.live(failure=FewsHTTPError("Synthetic HTTP failure"))
        self.assertEqual(status, 2)
        self.assertIn("FEWS ingestion failed", output)
        self.assertIn("Synthetic HTTP failure", output)
        self.assertEqual(self.database_hash(), checksum)
        self.assertEqual(FewsSnapshotStore(self.path).latest().snapshot_id, previous["snapshot_id"])
        transport.assert_called_once()

    def test_initial_http_failure_creates_no_database(self):
        status, output, transport, _ = self.live(failure=FewsHTTPError("Synthetic timeout"))
        self.assertEqual(status, 2)
        self.assertIn("FEWS ingestion failed", output)
        self.assertFalse(self.path.parent.exists())
        transport.assert_called_once()

    def test_release_database_path_is_rejected_before_http(self):
        protected = (
            Path(store_module.__file__).resolve().parents[2] / "data" / "releases"
            / "test_fews_ingestion_command_forbidden.sqlite3"
        )
        self.assertFalse(protected.exists())
        output = StringIO()
        with patch.object(command, "FewsMarketPriceClient") as client, redirect_stdout(output):
            status = command.main(["--live", "--database", str(protected)])
        self.assertEqual(status, 2)
        self.assertIn("data/releases", output.getvalue())
        self.assertFalse(protected.exists())
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
