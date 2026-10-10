"""Read-only market-price API behavior against deterministic saved snapshots."""

from contextlib import ExitStack, contextmanager
from dataclasses import fields, replace
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
from packages.data_sources.market_prices import MarketPriceRecord
from packages.data_sources.providers.fews_http_client import (
    FewsMarketPriceClient,
    FewsMarketPriceQuery,
    build_fews_snapshot,
)
from packages.data_sources.providers.fews_market_prices import FEWS_MARKET_SOURCE_ID
from packages.data_sources.registry import SourceRegistry
from packages.data_sources.snapshot_store import FewsSnapshotStore, effective_fews_query


runtime_module = importlib.import_module("apps.api.app.core.runtime")
main_module = importlib.import_module("apps.api.app.main")
health_module = importlib.import_module("apps.api.app.routes.health")
sources_module = importlib.import_module("apps.api.app.routes.sources")
market_module = importlib.import_module("apps.api.app.routes.market_prices")


def sample_fetch(retrieved_at):
    query = FewsMarketPriceQuery(
        start_date=date(2025, 1, 1), end_date=date(2025, 3, 31), cpcv2="R01122",
    )
    base = {
        "period_date": "2025-01-31", "country_code": "NG",
        "admin_1": "Abia", "admin_2": "Aba North", "fnid": "NG0000M001",
        "market": "Aba", "market_id": 57682, "cpcv2": "R01122AC",
        "cpcv2_description": "Maize grain (corn), other, white",
        "product": "Maize Grain (White)", "price_type": "Retail",
        "product_source": "Local", "unit": "kg", "currency": "NGN",
        "value": "12345678901234567890.123456789", "dataseries": 15312,
        "source_organization": "FEWS NET", "source_document": "Nigeria, Price (weekly)",
        "collection_status": "Published", "modified": "2026-07-21T23:02:24",
        "longitude": "7.370630000000001", "latitude": "5.107190000000001",
    }
    variations = (
        {},
        {"market": "Kano", "admin_1": "Kano", "market_id": 2,
         "cpcv2": "R01122AB", "product": "Maize Grain (Yellow)", "value": "900.10"},
        {"period_date": "2025-02-28", "value": "998.10"},
        {"period_date": "2025-02-28", "market": "Nnewi", "admin_1": "Anambra",
         "market_id": 3, "value": "1100.00"},
        {"period_date": "2025-03-31", "market": "Aba North", "market_id": 4,
         "cpcv2": "R01122AB", "product": "Maize Grain (Yellow)", "value": "1050.50"},
        {"period_date": "2025-03-31", "market": "Unspecified", "market_id": 5,
         "admin_1": None, "admin_2": None, "fnid": None, "longitude": None,
         "latitude": None, "modified": None, "value": "1000"},
    )
    records = [{**base, **variation} for variation in variations]
    next_url = query.url(100) + "&offset=100"
    pages = iter((
        {"results": records[:2], "next": next_url},
        {"results": records[2:], "next": None},
    ))
    return query, FewsMarketPriceClient(
        get_json=lambda *args, **kwargs: next(pages), clock=lambda: retrieved_at,
    ).fetch(query)


class MarketPricesAPITests(unittest.TestCase):
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
            side_effect=AssertionError("Market-price API must never query FEWS."),
        ))

    def save(self, *, path=None, retrieved_at=None):
        query, result = sample_fetch(retrieved_at or self.now)
        stored = FewsSnapshotStore(path or self.path).save(query, result)
        return query, result, stored

    def configured(self, *, path=None):
        return replace(self.settings, fews_snapshot_path=str(path or self.path))

    @contextmanager
    def api(self, configured_settings=None):
        runtime = runtime_module.AgDARuntime()
        with ExitStack() as stack:
            stack.enter_context(patch.object(
                runtime_module, "settings", configured_settings or self.configured(),
            ))
            for module in (main_module, health_module, sources_module, market_module):
                stack.enter_context(patch.object(module, "runtime", runtime))
            client = stack.enter_context(TestClient(main_module.app))
            yield runtime, client
        self.network.assert_not_called()

    def assert_core_ready(self, client):
        response = client.get("/v1/ready")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ready"])
        self.assertEqual(response.json()["data_version"], "wave5_v1")
        self.assertFalse(response.json()["external_sources"]["affects_core_readiness"])

    def assert_unavailable(self, response):
        self.assertEqual(response.status_code, 503)
        payload = json.dumps(response.json())
        self.assertNotIn(str(self.path), payload)
        self.assertNotIn("private storage detail", payload)
        self.assertNotIn("sqlite", payload.lower())

    def test_loaded_snapshot_returns_canonical_records_and_full_provenance(self):
        query, result, stored = self.save()
        with self.api() as (_, client):
            response = client.get("/v1/market-prices")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["snapshot_id"], stored.snapshot_id)
            self.assertEqual(body["snapshot_restore_status"], "loaded")
            self.assertEqual(body["filters"], {})
            self.assertEqual(body["total"], 6)
            self.assertEqual(body["limit"], 50)
            self.assertEqual(body["offset"], 0)
            self.assertEqual(body["returned_count"], 6)
            self.assertIsNone(body["next_offset"])
            source = body["source"]
            self.assertEqual(source, client.get("/v1/sources").json()["sources"][0])
            self.assertEqual(source["query"], effective_fews_query(query))
            self.assertEqual(source["query"]["schedule"], "Monthly")
            self.assertEqual(source["source_id"], FEWS_MARKET_SOURCE_ID)
            self.assertEqual(source["record_count"], 6)
            self.assertEqual(source["freshness"], "fresh")
            self.assertEqual(source["dataset_version"], result.snapshot.dataset_version)
            self.assertEqual(source["retrieved_at"], self.now.isoformat())
            self.assertEqual(source["refreshed_at"], self.now.isoformat())
            self.assertEqual(source["observed_from"], "2025-01-31T00:00:00+00:00")
            self.assertEqual(source["observed_to"], "2025-03-31T00:00:00+00:00")
            first = body["records"][0]
            self.assertEqual(set(first), {field.name for field in fields(MarketPriceRecord)})
            self.assertEqual(first["period_date"], "2025-01-31")
            self.assertEqual(first["source_modified_at"], "2026-07-21T23:02:24")
            self.assertEqual(first["value"], "12345678901234567890.123456789")
            self.assertEqual(first["longitude"], "7.370630000000001")
            self.assertEqual(first["latitude"], "5.107190000000001")
            self.assertIsInstance(first["market_id"], int)
            self.assertIsNone(body["records"][-1]["source_modified_at"])
            self.assertIsNone(body["records"][-1]["longitude"])
            self.assertNotIn(str(self.path), json.dumps(body))

    def test_text_filters_are_trimmed_case_insensitive_and_exact(self):
        self.save()
        with self.api() as (_, client):
            cases = (
                ({"admin_1": "  aBiA  "}, 3, {"admin_1": "aBiA"}),
                ({"market": "  aBA  "}, 2, {"market": "aBA"}),
                ({"cpcv2": " r01122ac "}, 4, {"cpcv2": "r01122ac"}),
                ({"market": "Ab"}, 0, {"market": "Ab"}),
                ({"cpcv2": "R01122"}, 0, {"cpcv2": "R01122"}),
            )
            for params, expected, filters in cases:
                with self.subTest(params=params):
                    response = client.get("/v1/market-prices", params=params)
                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    self.assertEqual(body["total"], expected)
                    self.assertEqual(body["returned_count"], expected)
                    self.assertEqual(body["filters"], filters)
                    self.assertEqual(body["source"]["record_count"], 6)

    def test_combined_filters_and_inclusive_observation_dates(self):
        self.save()
        with self.api() as (_, client):
            filters = {
                "admin_1": "Abia", "market": "Aba", "cpcv2": "R01122AC",
                "start_date": "2025-02-28", "end_date": "2025-02-28",
            }
            response = client.get("/v1/market-prices", params=filters)
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["filters"], filters)
            self.assertEqual(body["total"], 1)
            self.assertEqual(body["records"][0]["period_date"], "2025-02-28")
            self.assertEqual(body["records"][0]["value"], "998.10")
            self.assertEqual(body["source"]["record_count"], 6)
            self.assertEqual(body["source"]["observed_from"], "2025-01-31T00:00:00+00:00")
            self.assertEqual(body["source"]["query"]["start_date"], "2025-01-01")

    def test_each_date_bound_filters_independently(self):
        self.save()
        with self.api() as (_, client):
            for filters, expected in (
                ({"start_date": "2025-02-28"}, 4),
                ({"end_date": "2025-02-28"}, 4),
                ({"start_date": "2026-01-01"}, 0),
            ):
                with self.subTest(filters=filters):
                    response = client.get("/v1/market-prices", params=filters)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["total"], expected)

    def test_empty_matches_return_successful_empty_page(self):
        self.save()
        with self.api() as (_, client):
            response = client.get("/v1/market-prices", params={"market": "Absent market"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["records"], [])
            self.assertEqual(body["total"], 0)
            self.assertEqual(body["returned_count"], 0)
            self.assertIsNone(body["next_offset"])
            self.assertEqual(body["source"]["record_count"], 6)

    def test_pagination_preserves_saved_order_and_pins_snapshot(self):
        _, result, stored = self.save()
        with self.api() as (_, client):
            received = []
            offset = 0
            for expected_next in (2, 4, None):
                response = client.get("/v1/market-prices", params={
                    "limit": 2, "offset": offset, "snapshot_id": stored.snapshot_id,
                })
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["snapshot_id"], stored.snapshot_id)
                self.assertEqual(body["total"], 6)
                self.assertEqual(body["limit"], 2)
                self.assertEqual(body["offset"], offset)
                self.assertEqual(body["returned_count"], 2)
                self.assertEqual(body["next_offset"], expected_next)
                received.extend((row["market"], row["period_date"]) for row in body["records"])
                offset = expected_next
            self.assertEqual(received, [(row.market, row.period_date.isoformat()) for row in result.records])

    def test_filtered_pagination_counts_only_matching_records(self):
        self.save()
        with self.api() as (_, client):
            response = client.get("/v1/market-prices", params={
                "admin_1": "Abia", "limit": 2, "offset": 2,
            })
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["total"], 3)
            self.assertEqual(body["returned_count"], 1)
            self.assertEqual(body["records"][0]["market"], "Aba North")
            self.assertIsNone(body["next_offset"])
            self.assertEqual(body["source"]["record_count"], 6)

    def test_offsets_at_and_beyond_end_are_empty(self):
        self.save()
        with self.api() as (_, client):
            for offset in (6, 1000000):
                with self.subTest(offset=offset):
                    response = client.get("/v1/market-prices", params={"offset": offset})
                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    self.assertEqual(body["total"], 6)
                    self.assertEqual(body["records"], [])
                    self.assertEqual(body["returned_count"], 0)
                    self.assertIsNone(body["next_offset"])

    def test_page_size_accepts_both_bounds(self):
        self.save()
        with self.api() as (_, client):
            for limit, expected in ((1, 1), (200, 6)):
                with self.subTest(limit=limit):
                    response = client.get("/v1/market-prices", params={"limit": limit})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["returned_count"], expected)

    def test_invalid_pagination_dates_and_filters_are_rejected(self):
        self.save()
        with self.api() as (_, client):
            cases = (
                {"limit": 0}, {"limit": -1}, {"limit": 201}, {"limit": "1.5"},
                {"limit": "bad"}, {"offset": -1}, {"offset": "0.5"},
                {"offset": "bad"}, {"start_date": "not-a-date"},
                {"end_date": "2025-02-30"},
                {"start_date": "2025-03-01", "end_date": "2025-01-01"},
                {"admin_1": "   "}, {"market": ""}, {"cpcv2": "  "},
                {"admin_1": "x" * 121}, {"market": "x" * 121},
                {"cpcv2": "x" * 65}, {"snapshot_id": ""},
                {"snapshot_id": "f" * 63}, {"snapshot_id": "g" * 64},
                {"snapshot_id": "A" * 64},
            )
            for params in cases:
                with self.subTest(params=params):
                    response = client.get("/v1/market-prices", params=params)
                    self.assertEqual(response.status_code, 422)

    def test_unknown_snapshot_pin_is_a_conflict(self):
        self.save()
        with self.api() as (_, client):
            response = client.get("/v1/market-prices", params={"snapshot_id": "0" * 64})
            self.assertEqual(response.status_code, 409)
            self.assertNotIn(str(self.path), json.dumps(response.json()))

    def test_new_retrieval_conflicts_with_old_pin_even_for_same_content(self):
        _, previous, old_stored = self.save(retrieved_at=self.now - timedelta(hours=1))
        with self.api() as (runtime, client):
            _, latest, new_stored = self.save()
            self.assertEqual(previous.snapshot.dataset_version, latest.snapshot.dataset_version)
            self.assertNotEqual(old_stored.snapshot_id, new_stored.snapshot_id)
            runtime.reload_fews_snapshot()
            response = client.get("/v1/market-prices", params={
                "snapshot_id": old_stored.snapshot_id, "offset": 2, "limit": 2,
            })
            self.assertEqual(response.status_code, 409)
            response = client.get("/v1/market-prices", params={"snapshot_id": new_stored.snapshot_id})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["source"]["retrieved_at"], self.now.isoformat())

    def test_requests_use_cached_snapshot_without_disk_or_provider_io(self):
        _, _, stored = self.save()
        with self.api() as (_, client):
            with ExitStack() as stack:
                calls = [stack.enter_context(patch.object(
                    FewsSnapshotStore, method,
                    side_effect=AssertionError("Request must use the restored snapshot cache."),
                )) for method in ("latest", "get", "save")]
                calls.append(stack.enter_context(patch(
                    "sqlite3.connect", side_effect=AssertionError("Request must not reopen SQLite."),
                )))
                calls.append(stack.enter_context(patch(
                    "builtins.open", side_effect=AssertionError("Request must not read files."),
                )))
                for params in ({}, {"market": "Aba", "snapshot_id": stored.snapshot_id}):
                    self.assertEqual(client.get("/v1/market-prices", params=params).status_code, 200)
                for call in calls:
                    call.assert_not_called()

    def test_disabled_source_is_unavailable_and_core_stays_ready(self):
        with patch.object(runtime_module, "FewsSnapshotStore") as constructor:
            with self.api(self.settings) as (_, client):
                self.assert_unavailable(client.get("/v1/market-prices"))
                self.assert_core_ready(client)
            constructor.assert_not_called()

    def test_missing_source_is_unavailable_without_creating_store(self):
        with self.api() as (_, client):
            self.assert_unavailable(client.get("/v1/market-prices"))
            self.assert_core_ready(client)
            self.assertFalse(self.path.exists())

    def test_corrupt_source_is_unavailable_without_exposing_storage_details(self):
        self.path.write_bytes(b"broken snapshot: private storage detail")
        with self.assertLogs(runtime_module.logger, level="WARNING"):
            with self.api() as (_, client):
                self.assert_unavailable(client.get("/v1/market-prices"))
                self.assert_core_ready(client)

    def test_unready_runtime_does_not_serve_cached_data(self):
        self.save()
        with self.api() as (runtime, client):
            runtime.ready = False
            self.assert_unavailable(client.get("/v1/market-prices"))

    def test_stale_snapshot_remains_readable_with_explicit_freshness(self):
        self.save(retrieved_at=self.now - timedelta(hours=49))
        with self.api() as (_, client):
            response = client.get("/v1/market-prices")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["source"]["freshness"], "stale")
            self.assertEqual(response.json()["returned_count"], 6)
            self.assert_core_ready(client)

    def test_failed_reload_keeps_last_good_records_and_exposes_restore_status(self):
        self.save()
        with self.api() as (runtime, client):
            before = client.get("/v1/market-prices").json()
            self.path.write_bytes(b"broken snapshot: private storage detail")
            with self.assertLogs(runtime_module.logger, level="WARNING"):
                runtime.reload_fews_snapshot()
            response = client.get("/v1/market-prices", params={"snapshot_id": before["snapshot_id"]})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["snapshot_restore_status"], "error")
            for name in ("snapshot_id", "source", "records"):
                self.assertEqual(body[name], before[name])
            self.assertNotIn("private storage detail", json.dumps(body))
            self.assert_core_ready(client)

    def test_missing_reload_keeps_last_good_records(self):
        self.save()
        with self.api() as (runtime, client):
            before = client.get("/v1/market-prices").json()
            self.path.unlink()
            runtime.reload_fews_snapshot()
            response = client.get("/v1/market-prices")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["snapshot_restore_status"], "missing")
            for name in ("snapshot_id", "source", "records"):
                self.assertEqual(body[name], before[name])
            self.assertFalse(self.path.exists())

    def test_older_reload_does_not_roll_back_cached_data(self):
        self.save()
        older_path = Path(self.directory.name) / "older.sqlite3"
        self.save(path=older_path, retrieved_at=self.now - timedelta(hours=1))
        with self.api() as (runtime, client):
            before = client.get("/v1/market-prices").json()
            with patch.object(runtime_module, "settings", self.configured(path=older_path)):
                runtime.reload_fews_snapshot()
                response = client.get("/v1/market-prices")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            for name in ("snapshot_id", "source", "records"):
                self.assertEqual(body[name], before[name])

    def test_disabling_source_after_restore_stops_serving_cached_data(self):
        self.save()
        with self.api() as (runtime, client):
            with patch.object(runtime_module, "settings", self.settings):
                runtime.reload_fews_snapshot()
                self.assert_unavailable(client.get("/v1/market-prices"))
                self.assert_core_ready(client)

    def test_registry_drift_does_not_pair_cached_records_with_other_provenance(self):
        query, result, _ = self.save()
        with self.api() as (runtime, client):
            other_snapshot = build_fews_snapshot(
                query, result.records, self.now + timedelta(hours=1),
            )
            runtime.source_registry.record_snapshot(other_snapshot)
            self.assert_unavailable(client.get("/v1/market-prices"))
            self.assert_core_ready(client)

    def test_replaced_empty_registry_does_not_serve_orphaned_cached_data(self):
        self.save()
        with self.api() as (runtime, client):
            runtime.source_registry = SourceRegistry()
            self.assert_unavailable(client.get("/v1/market-prices"))
            self.assert_core_ready(client)


if __name__ == "__main__":
    unittest.main(verbosity=2)
