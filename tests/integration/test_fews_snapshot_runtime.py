"""Deterministic local snapshot hydration, configuration, and API isolation checks."""

from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.app.core.settings import AppSettings
from packages.data_sources.providers.fews_http_client import (
    FewsMarketPriceClient,
    FewsMarketPriceQuery,
)
from packages.data_sources.providers.fews_market_prices import FEWS_MARKET_SOURCE_ID
from packages.data_sources.snapshot_store import FewsSnapshotStore, effective_fews_query


runtime_module = importlib.import_module("apps.api.app.core.runtime")
main_module = importlib.import_module("apps.api.app.main")
health_module = importlib.import_module("apps.api.app.routes.health")
sources_module = importlib.import_module("apps.api.app.routes.sources")


def sample_fetch(retrieved_at, *, cpcv2="R01122AC"):
    query = FewsMarketPriceQuery(
        start_date=date(2025, 1, 1), end_date=date(2025, 1, 31), cpcv2=cpcv2,
        product="ignored because CPCv2 is supplied",
    )
    raw = {
        "period_date": "2025-01-31", "country_code": "NG", "market": "Aba",
        "market_id": 57682, "cpcv2": cpcv2, "product": "Maize Grain (White)",
        "price_type": "Retail", "unit": "kg", "currency": "NGN",
        "value": "998.10", "source_organization": "FEWS NET",
        "modified": "2026-07-21T23:02:24",
    }
    result = FewsMarketPriceClient(
        get_json=lambda *args, **kwargs: {"results": [raw], "next": None},
        clock=lambda: retrieved_at,
    ).fetch(query)
    return query, result


class FewsSnapshotRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "fews.sqlite3"
        with patch.dict(os.environ, {}, clear=True):
            self.settings = AppSettings.from_env()
        self.now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
        contract_clock = self.enterContext(patch(
            "packages.data_sources.contracts.datetime", wraps=datetime,
        ))
        contract_clock.now.return_value = self.now
        self.network = self.enterContext(patch(
            "packages.data_sources.providers.fews_http_client._get_json",
            side_effect=AssertionError("Runtime must never query FEWS."),
        ))

    def save(self, *, path=None, retrieved_at=None, cpcv2="R01122AC"):
        query, result = sample_fetch(retrieved_at or self.now, cpcv2=cpcv2)
        FewsSnapshotStore(path or self.path).save(query, result)
        return query, result

    def configured(self, *, path=None, stale_after_hours=48):
        return replace(
            self.settings, fews_snapshot_path=str(path or self.path),
            fews_stale_after_hours=stale_after_hours,
        )

    @contextmanager
    def api(self, configured_settings):
        runtime = runtime_module.AgDARuntime()
        with ExitStack() as stack:
            stack.enter_context(patch.object(runtime_module, "settings", configured_settings))
            for module in (main_module, health_module, sources_module):
                stack.enter_context(patch.object(module, "runtime", runtime))
            client = stack.enter_context(TestClient(main_module.app))
            yield runtime, client
        self.network.assert_not_called()

    def assert_ready(self, client):
        for endpoint in ("/v1/ready", "/v1/health"):
            response = client.get(endpoint)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["ready"])
            self.assertEqual(response.json()["data_version"], "wave5_v1")
            self.assertFalse(response.json()["external_sources"]["affects_core_readiness"])

    def test_configuration_defaults_blank_and_explicit_path(self):
        self.assertIsNone(self.settings.fews_snapshot_path)
        self.assertEqual(self.settings.fews_stale_after_hours, 48)
        with patch.dict(os.environ, {"AGDA_FEWS_SNAPSHOT_PATH": "  "}, clear=True):
            self.assertIsNone(AppSettings.from_env().fews_snapshot_path)
        with patch.dict(os.environ, {
            "AGDA_FEWS_SNAPSHOT_PATH": f"  {self.path}  ",
            "AGDA_FEWS_STALE_AFTER_HOURS": "72",
        }, clear=True):
            settings = AppSettings.from_env()
            self.assertEqual(settings.fews_snapshot_path, str(self.path))
            self.assertEqual(settings.fews_stale_after_hours, 72)
        for invalid in ("0", "-1", "invalid"):
            with self.subTest(invalid=invalid), patch.dict(os.environ, {
                "AGDA_FEWS_STALE_AFTER_HOURS": invalid,
            }, clear=True), self.assertRaises(ValueError):
                AppSettings.from_env()

    def test_disabled_runtime_never_opens_store(self):
        with patch.object(runtime_module, "FewsSnapshotStore") as constructor:
            with self.api(self.settings) as (runtime, client):
                self.assert_ready(client)
                runtime.reload_fews_snapshot()
                payload = client.get("/v1/sources").json()
                self.assertEqual(payload["sources"], [])
                self.assertEqual(payload["external_sources"]["status"], "not_configured")
                self.assertEqual(payload["external_sources"]["snapshot_restore_status"], "disabled")
            constructor.assert_not_called()

    def test_missing_store_registers_unknown_source_without_creating_file(self):
        with self.api(self.configured()) as (_, client):
            self.assert_ready(client)
            payload = client.get("/v1/sources").json()
            self.assertEqual(payload["external_sources"]["snapshot_restore_status"], "missing")
            source = payload["sources"][0]
            self.assertEqual(source["source_id"], FEWS_MARKET_SOURCE_ID)
            self.assertEqual(source["freshness"], "unknown")
            self.assertIsNone(source["record_count"])
            self.assertNotIn("query", source)
            self.assertFalse(self.path.exists())

    def test_restart_hydrates_exact_snapshot_and_effective_query(self):
        query, result = self.save()
        for _ in range(2):
            with self.api(self.configured(stale_after_hours=72)) as (runtime, client):
                self.assert_ready(client)
                payload = client.get("/v1/sources").json()
                self.assertEqual(payload["external_sources"]["snapshot_restore_status"], "loaded")
                source = payload["sources"][0]
                self.assertEqual(source["query"], effective_fews_query(query))
                self.assertNotIn("product", source["query"])
                self.assertEqual(source["stale_after_hours"], 72)
                self.assertEqual(source["record_count"], 1)
                self.assertEqual(source["retrieved_at"], result.retrieved_at.isoformat())
                self.assertEqual(source["refreshed_at"], result.retrieved_at.isoformat())
                self.assertEqual(runtime.source_registry.get_snapshot(FEWS_MARKET_SOURCE_ID), result.snapshot)
                self.assertNotIn(str(self.path), json.dumps(payload))

    def test_corrupt_store_does_not_block_readiness_or_expose_details(self):
        self.path.write_bytes(b"broken snapshot: private storage detail")
        with self.assertLogs(runtime_module.logger, level="WARNING") as logs:
            with self.api(self.configured()) as (_, client):
                self.assert_ready(client)
                payload = client.get("/v1/sources").json()
                self.assertEqual(payload["external_sources"]["snapshot_restore_status"], "error")
                self.assertEqual(payload["sources"][0]["freshness"], "unknown")
                self.assertNotIn(str(self.path), json.dumps(payload))
                self.assertNotIn("private storage detail", json.dumps(payload))
        self.assertTrue(any("FEWS snapshot restore failed" in entry for entry in logs.output))
        self.assertNotIn(str(self.path), " ".join(logs.output))
        self.assertNotIn("private storage detail", " ".join(logs.output))

    def test_reload_failure_preserves_last_good_snapshot_and_query(self):
        query, result = self.save()
        with self.api(self.configured()) as (runtime, client):
            self.path.write_bytes(b"broken")
            with self.assertLogs(runtime_module.logger, level="WARNING"):
                runtime.reload_fews_snapshot()
            self.assertEqual(runtime.fews_snapshot_restore_status, "error")
            self.assertEqual(runtime.source_registry.get_snapshot(FEWS_MARKET_SOURCE_ID), result.snapshot)
            self.assertEqual(runtime.external_source_manifest()[0]["query"], effective_fews_query(query))
            self.assert_ready(client)

    def test_reload_missing_store_preserves_last_good_snapshot_and_query(self):
        query, result = self.save()
        with self.api(self.configured()) as (runtime, client):
            with patch.object(runtime_module, "settings", self.configured(
                path=Path(self.directory.name) / "missing.sqlite3",
            )):
                runtime.reload_fews_snapshot()
            self.assertEqual(runtime.fews_snapshot_restore_status, "missing")
            self.assertEqual(runtime.source_registry.get_snapshot(FEWS_MARKET_SOURCE_ID), result.snapshot)
            self.assertEqual(runtime.external_source_manifest()[0]["query"], effective_fews_query(query))
            self.assert_ready(client)

    def test_reload_same_content_later_retrieval_advances_freshness(self):
        _, previous = self.save(retrieved_at=self.now - timedelta(hours=2))
        with self.api(self.configured()) as (runtime, _):
            _, latest = self.save()
            self.assertEqual(latest.snapshot.dataset_version, previous.snapshot.dataset_version)
            runtime.reload_fews_snapshot()
            self.assertEqual(runtime.source_registry.get_snapshot(FEWS_MARKET_SOURCE_ID), latest.snapshot)
            self.assertEqual(runtime.external_source_manifest()[0]["retrieved_at"], self.now.isoformat())

    def test_older_restore_does_not_roll_back_snapshot_or_query(self):
        latest_query, latest_result = self.save()
        older_path = Path(self.directory.name) / "older.sqlite3"
        self.save(path=older_path, retrieved_at=self.now - timedelta(hours=1), cpcv2="R01122AB")
        with self.api(self.configured()) as (runtime, _):
            with patch.object(runtime_module, "settings", self.configured(path=older_path)):
                runtime.reload_fews_snapshot()
            self.assertEqual(runtime.source_registry.get_snapshot(FEWS_MARKET_SOURCE_ID), latest_result.snapshot)
            self.assertEqual(runtime.external_source_manifest()[0]["query"], effective_fews_query(latest_query))

    def test_stale_external_source_preserves_core_readiness(self):
        self.save(retrieved_at=self.now - timedelta(hours=49))
        with self.api(self.configured()) as (_, client):
            self.assert_ready(client)
            payload = client.get("/v1/sources").json()
            self.assertEqual(payload["external_sources"]["status"], "degraded")
            self.assertEqual(payload["sources"][0]["freshness"], "stale")


if __name__ == "__main__":
    unittest.main(verbosity=2)
