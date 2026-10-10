"""Deterministic durable FEWS snapshot and registry integration checks.

This script uses temporary SQLite databases and scripted responses only. It never
contacts FEWS or writes to release data.
"""

from contextlib import closing
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from packages.data_sources.contracts import FreshnessStatus, SourceType
from packages.data_sources.fews_ingestion import (
    FewsIngestionError,
    build_fews_source_definition,
    refresh_fews_market_prices,
    restore_fews_market_prices,
)
from packages.data_sources.providers.fews_http_client import (
    FewsClientLimits,
    FewsHTTPError,
    FewsMarketPriceClient,
    FewsMarketPriceQuery,
)
from packages.data_sources.providers.fews_market_prices import FEWS_MARKET_SOURCE_ID
from packages.data_sources.registry import SourceRegistry
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore,
    SnapshotConflictError,
    SnapshotScopeError,
    SnapshotStoreError,
)


RETRIEVED_AT = datetime(2026, 10, 10, 1, 43, 41, 208041, timezone.utc)


def query(**changes):
    args = {
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 2, 28),
        "cpcv2": "R01122",
    }
    args.update(changes)
    return FewsMarketPriceQuery(**args)


def raw_record(**changes):
    record = {
        "period_date": "2025-01-31",
        "country_code": "NG",
        "admin_1": "Abia",
        "admin_2": "Aba North",
        "fnid": "NG0000M001",
        "market": "Aba",
        "market_id": 57682,
        "cpcv2": "R01122AC",
        "cpcv2_description": "Maize grain (corn), other, white",
        "product": "Maize Grain (White)",
        "price_type": "Retail",
        "product_source": "Local",
        "unit": "kg",
        "currency": "NGN",
        "value": "998.123456789012345678901234567890",
        "dataseries": 15312,
        "source_organization": "FEWS NET",
        "source_document": "FEWS NET, Nigeria, Price (weekly)",
        "collection_status": "Published",
        "modified": "2026-07-21T23:02:24",
        "longitude": "7.370630",
        "latitude": "5.107190",
        "pct_change_from_one_year_ago": 12.5,
    }
    record.update(changes)
    return record


def client(records=None, *, retrieved_at=RETRIEVED_AT, page_size=100):
    values = [raw_record()] if records is None else records

    def get_json(url, *, timeout_seconds, max_response_bytes):
        return {"count": len(values), "next": None, "results": list(values)}

    return FewsMarketPriceClient(
        limits=FewsClientLimits(page_size=page_size),
        get_json=get_json,
        clock=lambda: retrieved_at,
    )


def result(records=None, *, retrieved_at=RETRIEVED_AT, request=None, page_size=100):
    return client(records, retrieved_at=retrieved_at, page_size=page_size).fetch(
        query() if request is None else request
    )


class TemporaryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agda-fews-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "snapshots" / "fews.sqlite3"
        self.store = FewsSnapshotStore(self.path)


class SnapshotStoreTests(TemporaryStoreTests):
    def test_missing_store_reads_do_not_create_files_or_directories(self):
        self.assertIsNone(self.store.latest())
        self.assertIsNone(self.store.get("0" * 64))
        self.assertFalse(self.path.parent.exists())

    def test_round_trip_preserves_typed_records_query_snapshot_and_counters(self):
        fetched = result([
            raw_record(),
            raw_record(period_date="2025-02-28", market="Kano", market_id=57699,
                       admin_2=None, modified=None, longitude=None, latitude=None),
        ])
        saved = self.store.save(query(), fetched)
        reopened = FewsSnapshotStore(self.path)
        restored = reopened.latest()
        self.assertEqual(restored, saved)
        self.assertEqual(reopened.get(saved.snapshot_id), saved)
        self.assertEqual(restored.query, query())
        self.assertEqual(restored.result, fetched)
        first = restored.result.records[0]
        self.assertIsInstance(first.value, Decimal)
        self.assertEqual(str(first.value), raw_record()["value"])
        self.assertEqual(str(first.longitude), "7.370630")
        self.assertEqual(first.period_date, date(2025, 1, 31))
        self.assertEqual(first.source_modified_at, datetime(2026, 7, 21, 23, 2, 24))
        self.assertIsNone(restored.result.records[1].source_modified_at)
        self.assertEqual(restored.result.snapshot.retrieved_at, RETRIEVED_AT)
        self.assertEqual(restored.result.snapshot.refreshed_at, RETRIEVED_AT)

    def test_unknown_snapshot_id_returns_none_after_save(self):
        self.store.save(query(), result())
        self.assertIsNone(self.store.get("0" * 64))

    def test_exact_replay_is_idempotent(self):
        fetched = result()
        first = self.store.save(query(), fetched)
        self.assertEqual(self.store.save(query(), fetched), first)
        self.assertEqual(self.store.latest(), first)

    def test_new_retrieval_with_same_content_has_its_own_history_and_freshness(self):
        first = self.store.save(query(), result())
        second = self.store.save(query(), result(retrieved_at=RETRIEVED_AT + timedelta(hours=1)))
        self.assertNotEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(first.result.snapshot.dataset_version, second.result.snapshot.dataset_version)
        self.assertEqual(self.store.get(first.snapshot_id), first)
        self.assertEqual(self.store.latest(), second)

    def test_out_of_order_retrieval_is_retained_without_regressing_latest(self):
        newer = self.store.save(query(), result(retrieved_at=RETRIEVED_AT + timedelta(days=1)))
        older = self.store.save(query(), result([raw_record(value="950")]))
        self.assertEqual(self.store.get(older.snapshot_id), older)
        self.assertEqual(self.store.latest(), newer)

    def test_different_content_at_same_retrieval_instant_is_rejected(self):
        first = self.store.save(query(), result())
        with self.assertRaises(SnapshotConflictError):
            self.store.save(query(), result([raw_record(value="1050")]))
        self.assertEqual(self.store.latest(), first)

    def test_cpc_precedence_makes_unused_product_filter_the_same_scope(self):
        self.store.save(query(), result())
        request = query(product="ignored because CPCv2 is provided")
        fetched = result(request=request, retrieved_at=RETRIEVED_AT + timedelta(hours=1))
        saved = self.store.save(request, fetched)
        self.assertEqual(self.store.latest().snapshot_id, saved.snapshot_id)
        self.assertEqual(saved.result.snapshot.dataset_version, result().snapshot.dataset_version)

    def test_page_size_change_does_not_change_scope(self):
        self.store.save(query(), result(page_size=5))
        second = self.store.save(query(), result(page_size=200, retrieved_at=RETRIEVED_AT + timedelta(hours=1)))
        self.assertEqual(self.store.latest(), second)

    def test_changed_query_cannot_replace_existing_scope(self):
        first = self.store.save(query(), result())
        changes = (
            {"start_date": date(2025, 1, 2)},
            {"end_date": date(2025, 3, 31)},
            {"cpcv2": "R01122AC"},
            {"cpcv2": None, "product": "maize"},
        )
        for change in changes:
            request = query(**change)
            with self.subTest(change=change), self.assertRaises(SnapshotScopeError):
                self.store.save(request, result(request=request, retrieved_at=RETRIEVED_AT + timedelta(hours=1)))
            self.assertEqual(self.store.latest(), first)

    def test_empty_fetch_cannot_be_persisted(self):
        with self.assertRaises(SnapshotStoreError):
            self.store.save(query(), result([]))
        self.assertFalse(self.path.exists())

    def test_snapshot_metadata_must_match_canonical_records(self):
        good = result()
        self.store.save(query(), good)
        bad_snapshots = (
            replace(good.snapshot, record_count=2),
            replace(good.snapshot, source_id="other_source"),
            replace(good.snapshot, dataset_version="fews-monthly-v1:" + "0" * 64),
            replace(good.snapshot, observed_from=datetime(2025, 1, 1, tzinfo=timezone.utc)),
            replace(good.snapshot, observed_to=datetime(2025, 2, 28, tzinfo=timezone.utc)),
            replace(good.snapshot, refreshed_at=RETRIEVED_AT - timedelta(hours=1)),
            replace(good.snapshot, retrieved_at=RETRIEVED_AT + timedelta(hours=1)),
        )
        for snapshot in bad_snapshots:
            with self.subTest(snapshot=snapshot), self.assertRaises(SnapshotStoreError):
                self.store.save(query(), replace(good, snapshot=snapshot))
        self.assertEqual(self.store.latest().result, good)

    def test_missing_snapshot_or_records_cannot_be_persisted(self):
        good = result()
        for bad in (replace(good, snapshot=None), replace(good, records=())):
            with self.subTest(bad=bad), self.assertRaises(SnapshotStoreError):
                self.store.save(query(), bad)
        self.assertFalse(self.path.exists())

    def test_naive_result_retrieval_timestamp_is_rejected(self):
        with self.assertRaises(SnapshotStoreError):
            self.store.save(query(), replace(result(), retrieved_at=RETRIEVED_AT.replace(tzinfo=None)))
        self.assertFalse(self.path.exists())

    def test_invalid_counters_are_rejected(self):
        good = result()
        for updates in (
            {"pages_fetched": 0}, {"requests_made": 0},
            {"pages_fetched": -1}, {"requests_made": True},
            {"pages_fetched": 2, "requests_made": 1},
        ):
            with self.subTest(updates=updates), self.assertRaises(SnapshotStoreError):
                self.store.save(query(), replace(good, **updates))

    def test_record_source_or_query_scope_tampering_is_rejected(self):
        good = result()
        for updates in (
            {"source_id": "another_source"}, {"country_code": "GH"},
            {"cpcv2": "R01123"}, {"price_type": "Wholesale"},
            {"period_date": date(2024, 12, 31)},
        ):
            changed = replace(good.records[0], **updates)
            with self.subTest(updates=updates), self.assertRaises(SnapshotStoreError):
                self.store.save(query(), replace(good, records=(changed,)))

    def test_size_limit_rejects_save_without_replacing_good_snapshot(self):
        first = self.store.save(query(), result())
        limited = FewsSnapshotStore(self.path, max_snapshot_bytes=32)
        with self.assertRaises(SnapshotStoreError):
            limited.save(query(), result(retrieved_at=RETRIEVED_AT + timedelta(hours=1)))
        self.assertEqual(self.store.latest(), first)

    def test_size_limit_is_also_enforced_on_read(self):
        saved = self.store.save(query(), result())
        limited = FewsSnapshotStore(self.path, max_snapshot_bytes=32)
        with self.assertRaises(SnapshotStoreError):
            limited.latest()
        with self.assertRaises(SnapshotStoreError):
            limited.get(saved.snapshot_id)

    def test_sqlite_connection_failure_does_not_replace_prior_good_snapshot(self):
        first = self.store.save(query(), result())
        with patch("packages.data_sources.snapshot_store.sqlite3.connect", side_effect=sqlite3.OperationalError("disk unavailable")):
            with self.assertRaises(SnapshotStoreError):
                self.store.save(query(), result(retrieved_at=RETRIEVED_AT + timedelta(hours=1)))
        self.assertEqual(self.store.latest(), first)

    def test_transaction_rolls_back_if_an_insert_fails_before_commit(self):
        first = self.store.save(query(), result())
        native_connect = sqlite3.connect
        inserted = []

        class FailingConnection(sqlite3.Connection):
            def execute(self, statement, parameters=()):
                cursor = super().execute(statement, parameters)
                if statement.startswith("INSERT INTO fews_market_price_snapshots"):
                    inserted.append(True)
                    raise sqlite3.OperationalError("simulated failure after insertion")
                return cursor

        def connect(*args, **kwargs):
            return native_connect(*args, **kwargs, factory=FailingConnection)

        with patch("packages.data_sources.snapshot_store.sqlite3.connect", side_effect=connect):
            with self.assertRaises(SnapshotStoreError):
                self.store.save(query(), result(retrieved_at=RETRIEVED_AT + timedelta(hours=1)))
        self.assertEqual(inserted, [True])
        self.assertEqual(self.store.latest(), first)
        with closing(native_connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM fews_market_price_snapshots").fetchone()[0], 1)

    def test_failed_first_transaction_can_be_retried_without_manual_cleanup(self):
        native_connect = sqlite3.connect
        inserted = []

        class FailingConnection(sqlite3.Connection):
            def execute(self, statement, parameters=()):
                cursor = super().execute(statement, parameters)
                if statement.startswith("INSERT INTO fews_market_price_snapshots"):
                    inserted.append(True)
                    raise sqlite3.OperationalError("simulated first-save failure")
                return cursor

        def connect(*args, **kwargs):
            return native_connect(*args, **kwargs, factory=FailingConnection)

        registry = SourceRegistry()
        with patch("packages.data_sources.snapshot_store.sqlite3.connect", side_effect=connect):
            with self.assertRaises(SnapshotStoreError):
                refresh_fews_market_prices(query(), store=self.store, registry=registry, client=client())
        self.assertEqual(inserted, [True])
        self.assertTrue(self.path.exists())
        self.assertFalse(registry.contains(FEWS_MARKET_SOURCE_ID))
        self.assertIsNone(self.store.latest())
        self.assertIsNone(self.store.get("0" * 64))
        fetched = refresh_fews_market_prices(query(), store=self.store, registry=registry, client=client())
        self.assertEqual(self.store.latest().result, fetched)
        self.assertEqual(registry.get_snapshot(FEWS_MARKET_SOURCE_ID), fetched.snapshot)

    def test_unrelated_database_schema_is_not_treated_as_an_empty_store(self):
        self.path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE unrelated_application_data (value TEXT NOT NULL)")
            connection.execute("INSERT INTO unrelated_application_data VALUES ('preserve me')")
        with self.assertRaises(SnapshotStoreError):
            self.store.latest()
        with self.assertRaises(SnapshotStoreError):
            self.store.save(query(), result())
        registry = SourceRegistry()
        source_client = client()
        with patch.object(source_client, "fetch", side_effect=AssertionError("must reject before HTTP")):
            with self.assertRaises(SnapshotStoreError):
                refresh_fews_market_prices(query(), store=self.store, registry=registry, client=source_client)
        self.assertFalse(registry.contains(FEWS_MARKET_SOURCE_ID))
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT value FROM unrelated_application_data").fetchall(), [("preserve me",)])
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall(), [("unrelated_application_data",)])

    def test_corrupted_payload_checksum_is_rejected_on_latest_and_get(self):
        saved = self.store.save(query(), result())
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "UPDATE fews_market_price_snapshots SET payload = payload || ? WHERE snapshot_id = ?",
                (" ", saved.snapshot_id),
            )
        with self.assertRaises(SnapshotStoreError):
            self.store.latest()
        with self.assertRaises(SnapshotStoreError):
            self.store.get(saved.snapshot_id)

    def test_rehashed_tampered_records_still_fail_dataset_validation(self):
        saved = self.store.save(query(), result())
        with closing(sqlite3.connect(self.path)) as connection, connection:
            payload = connection.execute(
                "SELECT payload FROM fews_market_price_snapshots WHERE snapshot_id = ?", (saved.snapshot_id,),
            ).fetchone()[0]
            envelope = json.loads(payload)
            envelope["records"][0]["value"] = "999.99"
            tampered = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
            tampered_id = sha256(tampered.encode("utf-8")).hexdigest()
            connection.execute(
                "UPDATE fews_market_price_snapshots SET payload = ?, snapshot_id = ? WHERE snapshot_id = ?",
                (tampered, tampered_id, saved.snapshot_id),
            )
        with self.assertRaises(SnapshotStoreError):
            self.store.get(tampered_id)

    def test_tampered_retrieval_index_is_rejected(self):
        self.store.save(query(), result())
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "UPDATE fews_market_price_snapshots SET retrieved_at = ?",
                ((RETRIEVED_AT + timedelta(days=100)).isoformat(timespec="microseconds"),),
            )
        with self.assertRaises(SnapshotStoreError):
            self.store.latest()

    def test_tampered_scope_index_is_rejected(self):
        self.store.save(query(), result())
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE fews_market_price_snapshots SET scope_json = '{}' ")
        with self.assertRaises(SnapshotStoreError):
            self.store.latest()

    def test_non_database_existing_file_is_rejected_and_preserved(self):
        self.path.parent.mkdir(parents=True)
        original = b"not an AgDA database"
        self.path.write_bytes(original)
        with self.assertRaises(SnapshotStoreError):
            self.store.latest()
        with self.assertRaises(SnapshotStoreError):
            self.store.save(query(), result())
        self.assertEqual(self.path.read_bytes(), original)

    def test_repository_release_directory_is_protected(self):
        repository = Path(__file__).resolve().parents[2]
        protected = repository / "data" / "releases" / "fews-test.sqlite3"
        with self.assertRaises((ValueError, SnapshotStoreError)):
            FewsSnapshotStore(protected)
        self.assertFalse(protected.exists())


class IngestionTests(TemporaryStoreTests):
    def setUp(self):
        super().setUp()
        self.registry = SourceRegistry()

    def refresh(self, *, request=None, source_client=None, registry=None):
        return refresh_fews_market_prices(
            query() if request is None else request,
            store=self.store,
            registry=self.registry if registry is None else registry,
            client=client() if source_client is None else source_client,
        )

    def test_definition_describes_monthly_nigeria_market_data(self):
        definition = build_fews_source_definition(stale_after_hours=72)
        self.assertEqual(definition.source_id, FEWS_MARKET_SOURCE_ID)
        self.assertEqual(definition.source_type, SourceType.MARKET_PRICE)
        self.assertEqual(definition.stale_after_hours, 72)
        self.assertIn("monthly", definition.methodology_note.lower())
        self.assertIn("nigeria", definition.geographic_scope.lower())
        self.assertTrue(definition.attribution)

    def test_complete_refresh_persists_before_publishing_to_registry(self):
        original_record_snapshot = self.registry.record_snapshot

        def publish(snapshot):
            persisted = FewsSnapshotStore(self.path).latest()
            self.assertIsNotNone(persisted)
            self.assertEqual(persisted.result.snapshot, snapshot)
            original_record_snapshot(snapshot)

        with patch.object(self.registry, "record_snapshot", side_effect=publish) as publication:
            fetched = self.refresh()
        publication.assert_called_once_with(fetched.snapshot)
        self.assertEqual(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID), fetched.snapshot)
        self.assertEqual(self.store.latest().result, fetched)

    def test_restart_restores_the_last_snapshot_without_network(self):
        fetched = self.refresh()
        restarted_registry = SourceRegistry()
        with patch("packages.data_sources.providers.fews_http_client._get_json", side_effect=AssertionError("Unexpected HTTP request")):
            restored = restore_fews_market_prices(store=FewsSnapshotStore(self.path), registry=restarted_registry)
        self.assertEqual(restored.result, fetched)
        self.assertEqual(restarted_registry.get_snapshot(FEWS_MARKET_SOURCE_ID), fetched.snapshot)

    def test_missing_store_restore_registers_unknown_source_without_writes(self):
        restored = restore_fews_market_prices(store=self.store, registry=self.registry)
        self.assertIsNone(restored)
        state = self.registry.get_state(FEWS_MARKET_SOURCE_ID, now=RETRIEVED_AT)
        self.assertIsNone(state.snapshot)
        self.assertEqual(state.freshness, FreshnessStatus.UNKNOWN)
        self.assertFalse(self.path.parent.exists())

    def test_empty_first_fetch_creates_no_store_or_registry_state(self):
        fetched = self.refresh(source_client=client([]))
        self.assertEqual(fetched.records, ())
        self.assertIsNone(fetched.snapshot)
        self.assertFalse(self.registry.contains(FEWS_MARKET_SOURCE_ID))
        self.assertFalse(self.path.parent.exists())

    def test_empty_refresh_preserves_prior_data_and_freshness(self):
        first = self.refresh()
        stored = self.store.latest()
        self.refresh(source_client=client([], retrieved_at=RETRIEVED_AT + timedelta(days=1)))
        self.assertEqual(self.store.latest(), stored)
        self.assertEqual(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID), first.snapshot)

    def test_failed_fetch_preserves_prior_data_and_freshness(self):
        first = self.refresh()
        stored = self.store.latest()
        failing = client()
        with patch.object(failing, "fetch", side_effect=FewsHTTPError("timeout")):
            with self.assertRaises(FewsHTTPError):
                self.refresh(source_client=failing)
        self.assertEqual(self.store.latest(), stored)
        self.assertEqual(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID), first.snapshot)

    def test_store_failure_leaves_prior_registry_snapshot_unchanged(self):
        first = self.refresh()
        stored = self.store.latest()
        with patch.object(self.store, "save", side_effect=SnapshotStoreError("disk full")):
            with self.assertRaises(SnapshotStoreError):
                self.refresh(source_client=client(retrieved_at=RETRIEVED_AT + timedelta(days=1)))
        self.assertEqual(self.store.latest(), stored)
        self.assertEqual(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID), first.snapshot)

    def test_first_save_failure_does_not_register_source(self):
        with patch.object(self.store, "save", side_effect=SnapshotStoreError("disk full")):
            with self.assertRaises(SnapshotStoreError):
                self.refresh()
        self.assertFalse(self.registry.contains(FEWS_MARKET_SOURCE_ID))
        self.assertFalse(self.path.exists())

    def test_query_mismatch_preserves_store_and_registry(self):
        first = self.refresh()
        saved = self.store.latest()
        with self.assertRaises(SnapshotScopeError):
            self.refresh(request=query(cpcv2="R01122AC"), source_client=client(retrieved_at=RETRIEVED_AT + timedelta(hours=1)))
        self.assertEqual(self.store.latest(), saved)
        self.assertEqual(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID), first.snapshot)

    def test_conflicting_registry_definition_is_rejected_before_fetch(self):
        conflict = replace(build_fews_source_definition(), provider="Different provider")
        self.registry.register(conflict)
        source_client = client()
        with patch.object(source_client, "fetch", side_effect=AssertionError("must reject before fetching")):
            with self.assertRaises(FewsIngestionError):
                self.refresh(source_client=source_client)
        self.assertEqual(self.registry.get_definition(FEWS_MARKET_SOURCE_ID), conflict)
        self.assertIsNone(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID))
        self.assertFalse(self.path.exists())

    def test_restore_rejects_conflicting_registry_definition(self):
        self.store.save(query(), result())
        conflict = replace(build_fews_source_definition(), provider="Different provider")
        self.registry.register(conflict)
        with self.assertRaises(FewsIngestionError):
            restore_fews_market_prices(store=self.store, registry=self.registry)
        self.assertIsNone(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID))

    def test_equal_time_registry_snapshot_conflict_does_not_write_store(self):
        self.registry.register(build_fews_source_definition())
        current = result().snapshot
        self.registry.record_snapshot(current)
        with self.assertRaises(FewsIngestionError):
            self.refresh(source_client=client([raw_record(value="1050")]))
        self.assertEqual(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID), current)
        self.assertFalse(self.path.exists())

    def test_older_refresh_cannot_regress_registry_or_store(self):
        recent = self.refresh(source_client=client(retrieved_at=RETRIEVED_AT + timedelta(days=1)))
        stored = self.store.latest()
        older = self.refresh(source_client=client([raw_record(value="950")]))
        self.assertEqual(older.retrieved_at, RETRIEVED_AT)
        self.assertEqual(self.store.latest(), stored)
        self.assertEqual(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID), recent.snapshot)

    def test_restore_cannot_regress_a_more_recent_registry_snapshot(self):
        self.store.save(query(), result())
        self.registry.register(build_fews_source_definition())
        newer = result(retrieved_at=RETRIEVED_AT + timedelta(days=1)).snapshot
        self.registry.record_snapshot(newer)
        restore_fews_market_prices(store=self.store, registry=self.registry)
        self.assertEqual(self.registry.get_snapshot(FEWS_MARKET_SOURCE_ID), newer)

    def test_new_retrieval_updates_freshness_but_preserves_provider_modified_time(self):
        self.refresh()
        second_time = RETRIEVED_AT + timedelta(days=4)
        second = self.refresh(source_client=client(retrieved_at=second_time))
        state = self.registry.get_state(FEWS_MARKET_SOURCE_ID, now=second_time + timedelta(hours=1))
        self.assertEqual(state.freshness, FreshnessStatus.FRESH)
        self.assertEqual(state.snapshot.refreshed_at, second_time)
        self.assertEqual(second.records[0].source_modified_at, datetime(2026, 7, 21, 23, 2, 24))
        self.assertEqual(self.registry.get_state(FEWS_MARKET_SOURCE_ID, now=second_time + timedelta(hours=49)).freshness, FreshnessStatus.STALE)

    def test_repeated_restore_and_refresh_reuse_the_same_source_definition(self):
        restore_fews_market_prices(store=self.store, registry=self.registry)
        self.refresh()
        restore_fews_market_prices(store=self.store, registry=self.registry)
        self.refresh()
        self.assertEqual(len(self.registry.list_definitions()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
