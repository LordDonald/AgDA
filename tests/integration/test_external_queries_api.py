"""HTTP contracts and isolation guarantees for explicit external selections."""

from contextlib import ExitStack, contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
import importlib
import unittest
from unittest.mock import patch

from tests.integration import test_external_question_api as fixtures
from packages.data_sources.snapshot_store import FewsSnapshotStore
from packages.data_sources.weather_snapshot_store import WeatherSnapshotStore


queries_module = importlib.import_module("apps.api.app.routes.external_queries")


class ExternalQueriesAPITests(unittest.TestCase):
    # Reuse setup helpers without inheriting and rerunning another suite's tests.
    setUp = fixtures.ExternalQuestionAPITests.setUp
    save_fews = fixtures.ExternalQuestionAPITests.save_fews
    save_weather = fixtures.ExternalQuestionAPITests.save_weather
    configured = fixtures.ExternalQuestionAPITests.configured
    ask = fixtures.ExternalQuestionAPITests.ask

    @contextmanager
    def api(self, configured_settings):
        with fixtures.ExternalQuestionAPITests.api(self, configured_settings) as (runtime, client):
            with patch.object(queries_module, "runtime", runtime):
                yield runtime, client

    def query(self, client, metric_id="market_price_ngn_per_kg", operation="value", **fields):
        return client.post("/v1/external-queries", json={
            "metric_id": metric_id, "operation": operation, **fields,
        })

    def assert_core_ready(self, client):
        response = client.get("/v1/ready")
        self.assertEqual(response.status_code, 200)
        health = response.json()
        self.assertTrue(health["ready"])
        self.assertEqual(health["data_version"], "wave5_v1")
        self.assertEqual(health["release_state"], "stable")
        self.assertEqual(health["metric_version"], "1.0.0")
        self.assertEqual(health["registered_metrics"], 18)
        self.assertFalse(health["external_sources"]["affects_core_readiness"])
        return health

    def test_market_selection_returns_exact_observation_and_provenance(self):
        self.save_fews()
        with self.api(self.configured(weather=False)) as (runtime, client):
            stored = runtime.market_price_snapshot()
            response = self.query(client, selection={
                "market": "  bIU ", "admin_1": "borno", "cpcv2": "r01122ac",
                "period_date": "2025-01-31",
            }, snapshot_id=stored.snapshot_id)
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["status"], "answered")
            self.assertEqual(body["domain"], "external")
            self.assertFalse(body["affects_core_readiness"])
            self.assertEqual(body["snapshot_id"], stored.snapshot_id)
            self.assertEqual(body["source"]["source_id"], "fews_net_market_prices_ng")
            self.assertEqual(body["source"]["record_count"], 3)
            self.assertEqual(body["source"]["query"]["cpcv2"], "R01122AC")
            self.assertEqual(body["source"]["retrieved_at"], self.now.isoformat())
            self.assertEqual(body["rows"][0]["market"], "Biu")
            self.assertEqual(body["rows"][0]["value"], "511.65")
            self.assertEqual(body["rows"][0]["unit"], "NGN/kg")
            self.assertEqual(len(body["rows"]), 1)
            self.assertIn("historical", body["answer_text"])
            self.assert_core_ready(client)

    def test_market_unknown_filters_do_not_fall_back_to_full_snapshot(self):
        self.save_fews()
        with self.api(self.configured(weather=False)) as (_, client):
            for selection in (
                {"market": "Nonexistent"}, {"admin_1": "Lagos"},
                {"cpcv2": "R01122ZZ"}, {"period_date": "2025-01-30"},
            ):
                with self.subTest(selection=selection):
                    response = self.query(client, selection=selection)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["status"], "unavailable")
                    self.assertEqual(response.json()["rows"], [])

    def test_ambiguous_value_requires_selection_and_rank_respects_direction_and_limit(self):
        self.save_fews()
        with self.api(self.configured(weather=False)) as (_, client):
            body = self.query(client).json()
            self.assertEqual(body["status"], "needs_clarification")
            self.assertEqual(body["rows"], [])
            body = self.query(client, operation="rank", selection={
                "descending": False, "period_date": "2025-01-31",
            }, max_items=2).json()
            self.assertEqual(body["status"], "answered")
            self.assertEqual([row["market"] for row in body["rows"]], ["Biu", "Gombe"])
            self.assertEqual([row["rank"] for row in body["rows"]], [1, 2])
            self.assertIn("lowest", body["answer_text"])

    def test_exact_forecast_hour_normalizes_timezone_and_returns_single_value(self):
        self.save_weather()
        with self.api(self.configured(fews=False)) as (_, client):
            for metric, expected in (
                ("forecast_temperature_2m_c", "25"),
                ("forecast_relative_humidity_2m_pct", "80"),
            ):
                with self.subTest(metric=metric):
                    response = self.query(client, metric_id=metric, selection={
                        "valid_from": "2026-10-10T07:00:00+02:00",
                        "valid_to": "2026-10-10T00:00:00-05:00",
                        "latitude": "5.10719", "longitude": "7.37063",
                    })
                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    self.assertEqual(body["status"], "answered")
                    self.assertEqual(body["rows"][0]["value"], expected)
                    self.assertEqual(body["rows"][0]["valid_at"], "2026-10-10T05:00:00+00:00")
                    self.assertEqual(body["selection"]["valid_from"], "2026-10-10T05:00:00Z")
                    self.assertIn(expected, body["answer_text"])
                    self.assertEqual(body["rows"][0]["expected_hours"], 1)

    def test_forecast_subrange_and_precipitation_interval_are_explicit(self):
        self.save_weather()
        with self.api(self.configured(fews=False)) as (_, client):
            selection = {"valid_from": "2026-10-10T05:00:00Z", "valid_to": "2026-10-10T06:00:00Z"}
            response = self.query(client, metric_id="forecast_temperature_2m_c", operation="range", selection=selection)
            self.assertEqual(response.status_code, 200)
            row = response.json()["rows"][0]
            self.assertEqual((row["minimum"], row["maximum"]), ("25", "26"))
            self.assertEqual(row["hours_with_values"], 2)
            response = self.query(client, metric_id="forecast_precipitation_mm", operation="sum", selection=selection)
            self.assertEqual(response.status_code, 200)
            row = response.json()["rows"][0]
            self.assertEqual(row["total"], "3.0")
            self.assertEqual(row["interval_start"], "2026-10-10T04:00:00+00:00")
            self.assertEqual(row["interval_end"], "2026-10-10T06:00:00+00:00")
            self.assertIn("preceding hour", response.json()["time_semantics"])

    def test_forecast_unknown_coordinates_and_out_of_bounds_do_not_clip_or_fallback(self):
        self.save_weather()
        with self.api(self.configured(fews=False)) as (_, client):
            for selection in (
                {"latitude": "6.1", "longitude": "7.37063"},
                {"valid_from": "2026-10-09T23:00:00Z"},
                {"valid_to": "2026-10-11T00:00:00Z"},
            ):
                with self.subTest(selection=selection):
                    response = self.query(client, metric_id="forecast_temperature_2m_c", operation="range", selection=selection)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["status"], "unavailable")
                    self.assertEqual(response.json()["rows"], [])

    def test_strict_request_validation_rejects_unknown_fields_and_invalid_values(self):
        self.save_fews()
        self.save_weather()
        invalid = (
            {"extra": True}, {"metric_id": "median_completed_yield"},
            {"operation": "average"}, {"operation": "sum"},
            {"snapshot_id": "abc"}, {"snapshot_id": "A" * 64},
            {"snapshot_id": 123},
            {"operation": "rank", "max_items": 0},
            {"operation": "rank", "max_items": 21},
            {"operation": "rank", "max_items": True},
            {"operation": "rank", "max_items": "2"},
            {"operation": "rank", "max_items": 1.5},
            {"max_items": 5}, {"selection": {"descending": True}},
            {"selection": {"unexpected": "field"}},
            {"selection": {"period_date": "2025-02-30"}},
            {"selection": {"period_date": 1738281600}},
            {"selection": {"period_date": "1738281600"}},
            {"selection": {"period_date": "2025-01-31T00:00:00Z"}},
            {"selection": {"market": "   "}},
            {"selection": {"market": 123}},
            {"operation": "rank", "selection": {"descending": "false"}},
            {"selection": {"valid_from": "2026-10-10T05:00:00Z"}},
        )
        with self.api(self.configured()) as (_, client):
            for fields in invalid:
                with self.subTest(fields=fields):
                    self.assertEqual(self.query(client, **fields).status_code, 422)

    def test_strict_forecast_selection_validation(self):
        self.save_weather()
        invalid = (
            {"valid_from": "2026-10-10T05:00:00"},
            {"valid_from": "2026-10-10T05:01:00Z"},
            {"valid_from": "2026-10-10T05:00:01Z"},
            {"valid_from": 1791608400},
            {"valid_from": "1791608400"},
            {"valid_to": "1791608400"},
            {"valid_from": "not-a-date"},
            {"valid_from": "0001-01-01T00:00:00+01:00"},
            {"valid_to": "9999-12-31T23:00:00-01:00"},
            {"valid_from": "2026-10-10T06:00:00Z", "valid_to": "2026-10-10T05:00:00Z"},
            {"latitude": "5.10719"}, {"longitude": "7.37063"},
            {"latitude": "91", "longitude": "7.37063"},
            {"latitude": "5.10719", "longitude": "181"},
            {"latitude": "NaN", "longitude": "7.37063"},
            {"market": "Aba"}, {"period_date": "2025-01-31"},
            {"valid_from": "2026-10-10T05:00:00Z", "market": "Aba"},
        )
        with self.api(self.configured(fews=False)) as (_, client):
            for selection in invalid:
                with self.subTest(selection=selection):
                    response = self.query(client, metric_id="forecast_temperature_2m_c", selection=selection)
                    self.assertEqual(response.status_code, 422)

    def test_snapshot_pin_mismatch_is_conflict_and_does_not_compute(self):
        self.save_fews()
        self.save_weather()
        with self.api(self.configured()) as (runtime, client):
            with patch.object(runtime.external_metric_executor, "execute", side_effect=AssertionError("must not compute")):
                for metric in ("market_price_ngn_per_kg", "forecast_temperature_2m_c"):
                    with self.subTest(metric=metric):
                        response = self.query(client, metric_id=metric, snapshot_id="0" * 64)
                        self.assertEqual(response.status_code, 409)
            self.assert_core_ready(client)

    def test_missing_precipitation_is_labeled_partial_and_not_a_dry_forecast(self):
        self.save_weather()
        with self.api(self.configured(fews=False)) as (runtime, client):
            captured = runtime.weather_forecast_snapshot()
            records = tuple(
                replace(record, precipitation_mm=None if record.valid_at.hour == 5 else Decimal("0"))
                for record in captured.result.records
            )
            revised = replace(captured, result=replace(captured.result, records=records, missing_value_count=1))
            with patch.object(runtime, "weather_forecast_snapshot", return_value=revised):
                selection = {"valid_from": "2026-10-10T05:00:00Z", "valid_to": "2026-10-10T06:00:00Z"}
                response = self.query(client, metric_id="forecast_precipitation_mm", selection=selection)
                self.assertEqual(response.status_code, 200)
                body = response.json()
                row = body["rows"][0]
                self.assertEqual(row["data_quality"], "partial")
                self.assertEqual((row["hours_with_values"], row["missing_hours"]), (1, 1))
                self.assertIsNone(row["rain_expected"])
                self.assertIn("cannot be determined", body["answer_text"])
                response = self.query(client, metric_id="forecast_precipitation_mm", operation="sum", selection=selection)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["rows"][0]["total"], "0")
                self.assertIn("Partial sum", response.json()["answer_text"])
                self.assertIn("1 are missing", response.json()["answer_text"])

    def test_disabled_sources_return_unavailable_without_affecting_wave5(self):
        with self.api(self.configured(fews=False, weather=False)) as (_, client):
            for metric in ("market_price_ngn_per_kg", "forecast_temperature_2m_c"):
                with self.subTest(metric=metric):
                    self.assertEqual(self.query(client, metric_id=metric).status_code, 503)
            self.assert_core_ready(client)

    def test_corrupt_external_stores_do_not_affect_wave5(self):
        self.fews_path.write_bytes(b"not a sqlite database")
        self.weather_path.write_bytes(b"not a sqlite database")
        with self.api(self.configured()) as (_, client):
            for metric in ("market_price_ngn_per_kg", "forecast_temperature_2m_c"):
                with self.subTest(metric=metric):
                    self.assertEqual(self.query(client, metric_id=metric).status_code, 503)
            health = self.assert_core_ready(client)
            self.assertEqual(health["external_sources"]["snapshot_restore_status"], "error")
            self.assertEqual(health["external_sources"]["weather_snapshot_restore_status"], "error")

    def test_stale_snapshots_are_labeled_and_never_block_core_readiness(self):
        self.save_fews()
        self.save_weather()
        with patch("packages.data_sources.contracts.datetime", wraps=datetime) as clock:
            clock.now.return_value = self.now + timedelta(days=60)
            with self.api(self.configured()) as (_, client):
                requests = (
                    {"operation": "rank"},
                    {"metric_id": "forecast_temperature_2m_c", "operation": "range"},
                )
                for fields in requests:
                    with self.subTest(fields=fields):
                        response = self.query(client, **fields)
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()["status"], "answered")
                        self.assertEqual(response.json()["source"]["freshness"], "stale")
                health = self.assert_core_ready(client)
                self.assertEqual(health["external_sources"]["stale_sources"], 2)

    def test_requests_never_contact_providers_or_read_write_snapshot_stores(self):
        self.save_fews()
        self.save_weather()
        with self.api(self.configured()) as (_, client):
            # Provider calls already fail in setUp. Patch stores after startup:
            # requests must use accepted in-memory data, with no persistence I/O.
            with ExitStack() as stack:
                for store in (FewsSnapshotStore, WeatherSnapshotStore):
                    for method in ("latest", "save"):
                        stack.enter_context(patch.object(store, method, side_effect=AssertionError("request store I/O")))
                stack.enter_context(patch("sqlite3.connect", side_effect=AssertionError("request database I/O")))
                self.assertEqual(self.query(client, operation="rank").status_code, 200)
                self.assertEqual(self.query(client, metric_id="forecast_temperature_2m_c", operation="range").status_code, 200)

    def test_provenance_and_rows_use_captured_snapshot_during_runtime_replacement(self):
        self.save_fews()
        self.save_weather()
        with self.api(self.configured()) as (runtime, client):
            for metric, accessor, runtime_field, operation, question in (
                ("market_price_ngn_per_kg", "market_price_snapshot", "_fews_market_snapshot", "rank",
                 "Which market has the highest maize price?"),
                ("forecast_temperature_2m_c", "weather_forecast_snapshot", "_weather_forecast_snapshot", "range",
                 "What is the forecast temperature range?"),
            ):
                with self.subTest(metric=metric):
                    captured = getattr(runtime, accessor)()
                    newer_snapshot = replace(
                        captured.result.snapshot,
                        retrieved_at=self.now + timedelta(hours=1),
                        dataset_version=captured.result.snapshot.dataset_version + ":newer",
                    )
                    replacement_records = tuple(
                        replace(record, **({"value": Decimal("1")} if operation == "rank"
                                           else {"temperature_2m_c": Decimal("99")}))
                        for record in captured.result.records
                    )
                    replacement = replace(captured, snapshot_id="f" * 64,
                                          result=replace(captured.result, snapshot=newer_snapshot,
                                                         records=replacement_records,
                                                         retrieved_at=self.now + timedelta(hours=1)))
                    original_execute = runtime.external_metric_executor.execute

                    def refresh_during_execution(*args, **kwargs):
                        setattr(runtime, runtime_field, replacement)
                        runtime.source_registry.record_snapshot(newer_snapshot)
                        return original_execute(*args, **kwargs)

                    for endpoint in ("explicit", "natural_language"):
                        with self.subTest(endpoint=endpoint):
                            setattr(runtime, runtime_field, captured)
                            runtime.source_registry.record_snapshot(captured.result.snapshot)
                            with patch.object(runtime.external_metric_executor, "execute", side_effect=refresh_during_execution):
                                if endpoint == "explicit":
                                    response = self.query(client, metric_id=metric, operation=operation, snapshot_id=captured.snapshot_id)
                                else:
                                    response = self.ask(client, question)
                            self.assertEqual(response.status_code, 200)
                            body = response.json()
                            self.assertEqual(body["status"], "answered")
                            if endpoint == "natural_language":
                                self.assertEqual(body["data_version"], captured.result.snapshot.dataset_version)
                                body = body["result"]
                            self.assertEqual(body["snapshot_id"], captured.snapshot_id)
                            self.assertEqual(body["source"]["retrieved_at"], captured.result.retrieved_at.isoformat())
                            self.assertEqual(body["source"]["dataset_version"], captured.result.snapshot.dataset_version)
                            self.assertNotEqual(body["source"]["retrieved_at"], newer_snapshot.retrieved_at.isoformat())
                            if operation == "rank":
                                self.assertEqual(body["rows"][0]["value"], "998.10")
                            else:
                                self.assertEqual((body["rows"][0]["minimum"], body["rows"][0]["maximum"]), ("20", "43"))

    def test_core_price_change_and_climate_questions_still_use_wave5(self):
        self.save_fews()
        self.save_weather()
        with self.api(self.configured()) as (_, client):
            for question, expected_metric in (
                ("What is the median maize price change?", "median_same_basis_price_change"),
                ("How likely are very high temperatures?", "climate_likely_share"),
                ("How likely are late rains?", "climate_likely_share"),
            ):
                with self.subTest(question=question):
                    response = self.ask(client, question)
                    self.assertEqual(response.status_code, 200)
                    body = response.json()
                    self.assertEqual(body["status"], "answered")
                    self.assertEqual(body["question_specification"]["metric_id"], expected_metric)
                    self.assertEqual(body["data_version"], "wave5_v1")
                    self.assertEqual(body["metric_version"], "1.0.0")

    def test_mixed_external_core_requests_are_reframed_without_partial_answers(self):
        self.save_fews()
        self.save_weather()
        with self.api(self.configured()) as (_, client):
            for question in (
                "Compare maize yield with maize price.",
                "Compare community climate risk with forecast temperature.",
                "Compare price change with Open-Meteo rainfall.",
                "What is FEWS maize price change?",
            ):
                with self.subTest(question=question):
                    body = self.ask(client, question).json()
                    self.assertEqual(body["status"], "reframe_required")
                    self.assertIsNone(body["result"])
                    self.assertIn("one dataset at a time", body["answer_text"])

    def test_qualified_natural_language_never_silently_discards_filters(self):
        self.save_fews()
        self.save_weather()
        with self.api(self.configured()) as (_, client):
            for question in (
                "What is the maize price in Aba?", "What is the rice price?",
                "What is the maize price in January 2025?",
                "Will it rain tomorrow?", "What is the temperature in Lagos?",
                "Show the highest temperature at 05:00 UTC.",
            ):
                with self.subTest(question=question):
                    body = self.ask(client, question).json()
                    self.assertEqual(body["status"], "reframe_required")
                    self.assertIsNone(body["result"])
                    self.assertIn("/v1/external-queries", body["answer_text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
