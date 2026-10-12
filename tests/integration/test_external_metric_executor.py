from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch
from packages.data_sources.external_selection import ExternalSelection
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from packages.data_sources.external_executor import (
    ExternalExecutionStatus,
    ExternalMetricExecutor,
)
from packages.data_sources.external_metrics import (
    build_external_metric_registry,
)
from packages.data_sources.external_router import (
    ExternalQuestionRouter,
)
from packages.data_sources.market_prices import (
    MarketPriceRecord,
)
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
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore,
)
from packages.data_sources.weather_forecasts import (
    WeatherForecastRecord,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
    build_open_meteo_snapshot,
)


class ExternalMetricExecutorTests(
    unittest.TestCase
):

    def setUp(self):
        registry = build_external_metric_registry()

        self.router = ExternalQuestionRouter(
            registry
        )

        self.executor = ExternalMetricExecutor(
            registry
        )

        self.retrieved_at = datetime(
            2026,
            10,
            10,
            12,
            tzinfo=timezone.utc,
        )

    def market_snapshot(self):
        query = FewsMarketPriceQuery(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            cpcv2="R01122AC",
        )

        records = (
            MarketPriceRecord(
                source_id="fews_net_market_prices_ng",
                period_date=date(2025, 1, 31),
                country_code="NG",
                admin_1="Abia",
                admin_2="Aba North",
                fnid="NG0000M001",
                market="Aba",
                market_id=1,
                cpcv2="R01122AC",
                cpcv2_description="White maize",
                product="Maize Grain (White)",
                price_type="Retail",
                product_source="Local",
                unit="kg",
                currency="NGN",
                value=Decimal("998.10"),
                dataseries=1,
                source_organization="FEWS NET",
                source_document=None,
                collection_status="Published",
                source_modified_at=None,
                longitude=Decimal("7.37063"),
                latitude=Decimal("5.10719"),
            ),
            MarketPriceRecord(
                source_id="fews_net_market_prices_ng",
                period_date=date(2025, 1, 31),
                country_code="NG",
                admin_1="Borno",
                admin_2="Biu",
                fnid="NG0000M002",
                market="Biu",
                market_id=2,
                cpcv2="R01122AC",
                cpcv2_description="White maize",
                product="Maize Grain (White)",
                price_type="Retail",
                product_source="Local",
                unit="kg",
                currency="NGN",
                value=Decimal("511.65"),
                dataseries=2,
                source_organization="FEWS NET",
                source_document=None,
                collection_status="Published",
                source_modified_at=None,
                longitude=Decimal("12.1928"),
                latitude=Decimal("10.6137"),
            ),
        )

        snapshot = build_fews_snapshot(
            query,
            records,
            self.retrieved_at,
        )

        result = FewsFetchResult(
            records=records,
            snapshot=snapshot,
            retrieved_at=self.retrieved_at,
            pages_fetched=1,
            requests_made=1,
        )

        with TemporaryDirectory() as temp:
            store = FewsSnapshotStore(
                Path(temp) / "fews.sqlite3"
            )

            return store.save(
                query,
                result,
            )

    def weather_snapshot(self):
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
            self.retrieved_at,
        )

        result = OpenMeteoFetchResult(
            records=records,
            snapshot=snapshot,
            requested_from=records[0].valid_at,
            requested_to=records[-1].valid_at,
            retrieved_at=self.retrieved_at,
            requests_made=1,
            missing_value_count=0,
        )

        with TemporaryDirectory() as temp:
            store = WeatherSnapshotStore(
                Path(temp) / "weather.sqlite3"
            )

            return store.save(
                query,
                result,
            )

    def test_highest_market_price_ranking(self):
        result = self.executor.execute(
            self.router.route(
                "Which market has the highest maize price?"
            ),
            market_snapshot=self.market_snapshot(),
            weather_snapshot=None,
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.ANSWERED,
        )

        self.assertEqual(
            result.rows[0]["market"],
            "Aba",
        )

        self.assertEqual(
            result.rows[0]["value"],
            "998.10",
        )

    def test_lowest_market_price_ranking(self):
        result = self.executor.execute(
            self.router.route(
                "Which market has the lowest maize price?"
            ),
            market_snapshot=self.market_snapshot(),
            weather_snapshot=None,
        )

        self.assertEqual(
            result.rows[0]["market"],
            "Biu",
        )

    def test_unspecified_market_price_needs_clarification(self):
        result = self.executor.execute(
            self.router.route(
                "What is the maize price?"
            ),
            market_snapshot=self.market_snapshot(),
            weather_snapshot=None,
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.NEEDS_CLARIFICATION,
        )

    def test_temperature_range(self):
        result = self.executor.execute(
            self.router.route(
                "What is the forecast temperature range?"
            ),
            market_snapshot=None,
            weather_snapshot=self.weather_snapshot(),
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.ANSWERED,
        )

        self.assertEqual(
            result.rows[0]["minimum"],
            "20",
        )

        self.assertEqual(
            result.rows[0]["maximum"],
            "43",
        )

        self.assertEqual(
            result.rows[0]["unit"],
            "°C",
        )

    def test_temperature_value_needs_hour_clarification(self):
        result = self.executor.execute(
            self.router.route(
                "What is the forecast temperature?"
            ),
            market_snapshot=None,
            weather_snapshot=self.weather_snapshot(),
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.NEEDS_CLARIFICATION,
        )

    def test_rain_question_reports_expected_rain(self):
        result = self.executor.execute(
            self.router.route(
                "Will it rain?"
            ),
            market_snapshot=None,
            weather_snapshot=self.weather_snapshot(),
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.ANSWERED,
        )

        self.assertTrue(
            result.rows[0]["rain_expected"]
        )

        self.assertEqual(
            result.rows[0]["rainy_hours"],
            2,
        )

    def test_total_rain_sums_hourly_forecast(self):
        result = self.executor.execute(
            self.router.route(
                "How much rain is forecast?"
            ),
            market_snapshot=None,
            weather_snapshot=self.weather_snapshot(),
        )

        self.assertEqual(
            result.rows[0]["total"],
            "3.0",
        )

        self.assertEqual(
            result.rows[0]["unit"],
            "mm",
        )

    def test_missing_market_snapshot_is_unavailable(self):
        result = self.executor.execute(
            self.router.route(
                "Which market has the highest maize price?"
            ),
            market_snapshot=None,
            weather_snapshot=None,
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.UNAVAILABLE,
        )

    def test_missing_weather_snapshot_is_unavailable(self):
        result = self.executor.execute(
            self.router.route(
                "Will it rain?"
            ),
            market_snapshot=None,
            weather_snapshot=None,
        )

        self.assertEqual(
            result.status,
            ExternalExecutionStatus.UNAVAILABLE,
        )


    def run_market(self, *, records=None, selection=None, question="Which market has the highest maize price?", **kwargs):
        stored = self.market_snapshot()
        if records is not None:
            stored = replace(stored, result=replace(stored.result, records=records))
        return self.executor.execute(
            self.router.route(question), market_snapshot=stored, weather_snapshot=None,
            selection=selection, **kwargs,
        )

    def run_weather(self, *, stored=None, selection=None, question="What is the forecast temperature range?"):
        return self.executor.execute(
            self.router.route(question), market_snapshot=None,
            weather_snapshot=stored or self.weather_snapshot(), selection=selection,
        )

    def test_explicit_market_selection_is_exact_case_insensitive(self):
        result = self.run_market(
            question="What is the maize price?",
            selection=ExternalSelection(market=" aba ", admin_1="ABIA", cpcv2="r01122ac", period_date=date(2025, 1, 31)),
        )
        self.assertEqual(result.status, ExternalExecutionStatus.ANSWERED)
        self.assertEqual(result.rows[0]["value"], "998.10")
        self.assertEqual(result.rows[0]["cpcv2"], "R01122AC")
        self.assertEqual(result.rows[0]["price_type"], "Retail")

    def test_unknown_and_partial_market_selectors_are_unavailable(self):
        for selection in (
            ExternalSelection(market="A"), ExternalSelection(admin_1="Missing"),
            ExternalSelection(cpcv2="R01122"), ExternalSelection(period_date=date(2025, 1, 1)),
        ):
            with self.subTest(selection=selection):
                result = self.run_market(selection=selection)
                self.assertEqual(result.status, ExternalExecutionStatus.UNAVAILABLE)
                self.assertEqual(result.rows, ())
                self.assertTrue(result.reason)

    def test_empty_market_records_are_unavailable(self):
        for question in ("What is the maize price?", "Highest maize price"):
            with self.subTest(question=question):
                self.assertEqual(self.run_market(records=(), question=question).status, ExternalExecutionStatus.UNAVAILABLE)

    def test_market_ranking_rejects_every_mixed_dimension(self):
        first, second = self.market_snapshot().result.records
        for changes in (
            {"period_date": date(2025, 2, 28)}, {"cpcv2": "R01122AB"},
            {"product": "Maize Grain (Yellow)"}, {"currency": "USD"},
            {"unit": "50 kg"}, {"price_type": "Wholesale"},
            {"product_source": "Imported"}, {"product_source": None}, {"country_code": "GH"},
        ):
            with self.subTest(changes=changes):
                result = self.run_market(records=(first, replace(second, **changes)))
                self.assertEqual(result.status, ExternalExecutionStatus.NEEDS_CLARIFICATION)
                self.assertFalse(result.rows)

    def test_market_metric_refuses_homogeneous_wrong_contract(self):
        records = self.market_snapshot().result.records
        for changes in (
            {"cpcv2": "R01122AB"}, {"product": "Maize Grain (Yellow)"},
            {"currency": "USD"}, {"unit": "50 kg"}, {"price_type": "Wholesale"},
            {"country_code": "GH"}, {"source_id": "unrelated"},
        ):
            for question in ("Highest maize price", "What is the maize price?"):
                with self.subTest(changes=changes, question=question):
                    changed = tuple(replace(record, **changes) for record in records)
                    if question == "What is the maize price?":
                        changed = changed[:1]
                    result = self.run_market(records=changed, question=question)
                    self.assertEqual(result.status, ExternalExecutionStatus.UNAVAILABLE)
                    self.assertFalse(result.rows)

    def test_explicit_period_avoids_cross_period_ranking(self):
        first, second = self.market_snapshot().result.records
        records = (first, second, replace(first, period_date=date(2025, 2, 28), value=Decimal("9000")))
        result = self.run_market(records=records, selection=ExternalSelection(period_date=date(2025, 1, 31)))
        self.assertEqual([row["value"] for row in result.rows], ["998.10", "511.65"])

    def test_multiple_observations_for_selected_market_require_clarification(self):
        first = self.market_snapshot().result.records[0]
        records = (first, replace(first, period_date=date(2025, 2, 28)))
        result = self.run_market(records=records, question="What is the maize price?", selection=ExternalSelection(market="Aba"))
        self.assertEqual(result.status, ExternalExecutionStatus.NEEDS_CLARIFICATION)

    def test_duplicate_market_observations_cannot_be_ranked(self):
        first = self.market_snapshot().result.records[0]
        result = self.run_market(records=(first, replace(first, value=Decimal("900"))))
        self.assertEqual(result.status, ExternalExecutionStatus.NEEDS_CLARIFICATION)

    def test_explicit_ranking_order_and_limit_override_question(self):
        result = self.run_market(selection=ExternalSelection(descending=False), max_items=1)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["market"], "Biu")
        self.assertEqual(result.rows[0]["rank"], 1)

    def test_ranking_ties_are_deterministic(self):
        first, second = self.market_snapshot().result.records
        records = (replace(second, value=first.value), first)
        for descending in (True, False):
            result = self.run_market(records=records, selection=ExternalSelection(descending=descending))
            self.assertEqual([row["market"] for row in result.rows], ["Aba", "Biu"])

    def test_temperature_and_humidity_specific_hour(self):
        hour = datetime(2026, 10, 10, 5, tzinfo=timezone.utc)
        for question, value, unit in (
            ("What is the forecast temperature?", "25", "°C"),
            ("What is the forecast humidity?", "80", "%"),
        ):
            with self.subTest(question=question):
                result = self.run_weather(question=question, selection=ExternalSelection(valid_from=hour, valid_to=hour))
                self.assertEqual(result.status, ExternalExecutionStatus.ANSWERED)
                self.assertEqual(result.rows[0]["value"], value)
                self.assertEqual(result.rows[0]["unit"], unit)
                self.assertEqual(result.rows[0]["valid_at"], hour.isoformat())
                self.assertEqual(result.rows[0]["expected_hours"], 1)

    def test_hour_range_is_inclusive_and_reports_selected_bounds(self):
        start = datetime(2026, 10, 10, 5, tzinfo=timezone.utc)
        end = start + timedelta(hours=1)
        result = self.run_weather(selection=ExternalSelection(valid_from=start, valid_to=end))
        row = result.rows[0]
        self.assertEqual((row["minimum"], row["maximum"]), ("25", "26"))
        self.assertEqual(row["forecast_valid_from"], start.isoformat())
        self.assertEqual(row["forecast_valid_to"], end.isoformat())
        self.assertEqual((row["expected_hours"], row["hours_with_values"], row["missing_hours"]), (2, 2, 0))
        self.assertEqual(row["data_quality"], "complete")

    def test_one_sided_forecast_bounds_use_saved_opposite_bound(self):
        stored = self.weather_snapshot()
        for selection, count in (
            (ExternalSelection(valid_from=stored.result.requested_to), 1),
            (ExternalSelection(valid_to=stored.result.requested_from), 1),
        ):
            result = self.run_weather(stored=stored, selection=selection)
            self.assertEqual(result.rows[0]["expected_hours"], count)

    def test_out_of_coverage_forecast_is_not_silently_truncated(self):
        stored = self.weather_snapshot()
        start, end = stored.result.requested_from, stored.result.requested_to
        for selection in (
            ExternalSelection(valid_from=start - timedelta(hours=1)),
            ExternalSelection(valid_to=end + timedelta(hours=1)),
            ExternalSelection(valid_from=end + timedelta(hours=1)),
            ExternalSelection(valid_to=start - timedelta(hours=1)),
            ExternalSelection(valid_from=start - timedelta(days=1), valid_to=end + timedelta(days=1)),
        ):
            with self.subTest(selection=selection):
                result = self.run_weather(stored=stored, selection=selection)
                self.assertEqual(result.status, ExternalExecutionStatus.UNAVAILABLE)
                self.assertFalse(result.rows)

    def test_coordinates_match_request_and_not_grid_cell(self):
        stored = self.weather_snapshot()
        exact = ExternalSelection(latitude=stored.query.latitude, longitude=stored.query.longitude)
        self.assertEqual(self.run_weather(stored=stored, selection=exact).status, ExternalExecutionStatus.ANSWERED)
        first = stored.result.records[0]
        for latitude, longitude in (
            (first.grid_latitude, first.grid_longitude),
            (stored.query.latitude + Decimal("0.001"), stored.query.longitude),
            (stored.query.latitude, stored.query.longitude + Decimal("0.001")),
        ):
            result = self.run_weather(stored=stored, selection=ExternalSelection(latitude=latitude, longitude=longitude))
            self.assertEqual(result.status, ExternalExecutionStatus.UNAVAILABLE)

    def test_partial_precipitation_total_reports_coverage(self):
        stored = self.weather_snapshot()
        records = tuple(replace(record, precipitation_mm=None) if index in (0, 5) else record
                        for index, record in enumerate(stored.result.records))
        stored = replace(stored, result=replace(stored.result, records=records))
        result = self.run_weather(stored=stored, question="How much rain is forecast?")
        row = result.rows[0]
        self.assertEqual(row["total"], "1.5")
        self.assertEqual((row["expected_hours"], row["hours_with_values"], row["missing_hours"]), (24, 22, 2))
        self.assertEqual(row["data_quality"], "partial")
        self.assertEqual(row["interval_start"], "2026-10-09T23:00:00+00:00")
        self.assertEqual(row["interval_end"], "2026-10-10T23:00:00+00:00")

    def test_precipitation_selection_sums_only_inclusive_hours(self):
        start = datetime(2026, 10, 10, 5, tzinfo=timezone.utc)
        for end, total, count in ((start, "1.5", 1), (start + timedelta(hours=1), "3.0", 2)):
            result = self.run_weather(
                question="How much rain is forecast?",
                selection=ExternalSelection(valid_from=start, valid_to=end),
            )
            row = result.rows[0]
            self.assertEqual(row["total"], total)
            self.assertEqual(row["expected_hours"], count)
            self.assertEqual(row["interval_start"], (start - timedelta(hours=1)).isoformat())
            self.assertEqual(row["interval_end"], end.isoformat())

    def test_empty_weather_selection_is_unavailable(self):
        stored = self.weather_snapshot()
        changed = replace(stored, result=replace(stored.result, records=()))
        result = self.run_weather(stored=changed)
        self.assertEqual(result.status, ExternalExecutionStatus.UNAVAILABLE)
        self.assertFalse(result.rows)

    def test_forecast_extrema_ties_use_earliest_time(self):
        stored = self.weather_snapshot()
        changed = replace(stored, result=replace(stored.result, records=tuple(reversed(stored.result.records))))
        result = self.run_weather(stored=changed, question="Forecast humidity range")
        row = result.rows[0]
        self.assertEqual(row["minimum_valid_at"], stored.result.requested_from.isoformat())
        self.assertEqual(row["maximum_valid_at"], stored.result.requested_from.isoformat())

    def test_missing_precipitation_does_not_assert_no_rain(self):
        stored = self.weather_snapshot()
        records = tuple(replace(record, precipitation_mm=None if index == 0 else Decimal("0"))
                        for index, record in enumerate(stored.result.records))
        stored = replace(stored, result=replace(stored.result, records=records))
        result = self.run_weather(stored=stored, question="Will it rain?")
        self.assertIsNone(result.rows[0]["rain_expected"])
        self.assertEqual(result.rows[0]["data_quality"], "partial")
        self.assertEqual(result.rows[0]["rainy_hours"], 0)

    def test_known_positive_rain_with_missing_hour_is_still_expected(self):
        stored = self.weather_snapshot()
        records = tuple(replace(record, precipitation_mm=None) if index == 0 else record
                        for index, record in enumerate(stored.result.records))
        stored = replace(stored, result=replace(stored.result, records=records))
        result = self.run_weather(stored=stored, question="Will it rain?")
        self.assertIs(result.rows[0]["rain_expected"], True)
        self.assertEqual(result.rows[0]["data_quality"], "partial")

    def test_complete_zero_precipitation_is_no_rain(self):
        stored = self.weather_snapshot()
        hour = stored.result.requested_from
        result = self.run_weather(stored=stored, question="Will it rain?", selection=ExternalSelection(valid_from=hour, valid_to=hour))
        self.assertIs(result.rows[0]["rain_expected"], False)
        self.assertEqual(result.rows[0]["data_quality"], "complete")

    def test_all_missing_measure_values_are_unavailable(self):
        stored = self.weather_snapshot()
        for question, field in (
            ("How much rain is forecast?", "precipitation_mm"), ("Will it rain?", "precipitation_mm"),
            ("Forecast temperature range", "temperature_2m_c"), ("Forecast humidity range", "relative_humidity_2m_pct"),
        ):
            with self.subTest(question=question):
                records = tuple(replace(record, **{field: None}) for record in stored.result.records)
                changed = replace(stored, result=replace(stored.result, records=records))
                result = self.run_weather(stored=changed, question=question)
                self.assertEqual(result.status, ExternalExecutionStatus.UNAVAILABLE)
                self.assertFalse(result.rows)

    def test_missing_record_is_counted_in_forecast_coverage(self):
        stored = self.weather_snapshot()
        changed = replace(stored, result=replace(stored.result, records=stored.result.records[1:]))
        result = self.run_weather(stored=changed)
        self.assertEqual(result.rows[0]["expected_hours"], 24)
        self.assertEqual(result.rows[0]["missing_hours"], 1)
        self.assertEqual(result.rows[0]["data_quality"], "partial")

    def test_one_nonmissing_hour_does_not_resolve_a_multi_hour_value_request(self):
        stored = self.weather_snapshot()
        records = tuple(replace(record, temperature_2m_c=None) if index else record
                        for index, record in enumerate(stored.result.records))
        changed = replace(stored, result=replace(stored.result, records=records))
        self.assertEqual(self.run_weather(stored=changed, question="Forecast temperature").status,
                         ExternalExecutionStatus.NEEDS_CLARIFICATION)

    def test_duplicate_hour_or_wrong_coordinate_record_is_unavailable(self):
        stored = self.weather_snapshot()
        first = stored.result.records[0]
        for records in (
            (*stored.result.records, first),
            (replace(first, requested_latitude=Decimal("0")), *stored.result.records[1:]),
        ):
            changed = replace(stored, result=replace(stored.result, records=records))
            self.assertEqual(self.run_weather(stored=changed).status, ExternalExecutionStatus.UNAVAILABLE)

    def test_source_specific_selectors_rejected_before_missing_snapshot(self):
        for question, selection in (
            ("Maize price", ExternalSelection(valid_from=self.retrieved_at)),
            ("Maize price", ExternalSelection(latitude=Decimal("0"), longitude=Decimal("0"))),
            ("Forecast temperature", ExternalSelection(market="Aba")),
            ("Forecast temperature", ExternalSelection(period_date=date(2025, 1, 31))),
            ("Forecast temperature", ExternalSelection(descending=False)),
        ):
            with self.subTest(question=question, selection=selection), self.assertRaises(ValueError):
                self.executor.execute(self.router.route(question), market_snapshot=None, weather_snapshot=None, selection=selection)

    def test_executor_validates_operation_source_selection_and_bounds(self):
        route = self.router.route("Maize price")
        for changed_route, kwargs, error in (
            (replace(route, operation="sum"), {}, ValueError),
            (replace(route, source_id="open_meteo_forecast"), {}, ValueError),
            (route, {"selection": {}}, TypeError),
            (route, {"max_items": 0}, ValueError),
            (route, {"max_items": 21}, ValueError),
            (route, {"max_items": True}, ValueError),
        ):
            with self.subTest(route=changed_route, kwargs=kwargs), self.assertRaises(error):
                self.executor.execute(changed_route, market_snapshot=None, weather_snapshot=None, **kwargs)

    def test_executor_performs_no_network_storage_or_refresh_io(self):
        market = self.market_snapshot()
        weather = self.weather_snapshot()
        with patch("builtins.open", side_effect=AssertionError("file I/O")), \
             patch("sqlite3.connect", side_effect=AssertionError("storage I/O")), \
             patch("urllib.request.build_opener", side_effect=AssertionError("network I/O")):
            for question in ("Highest maize price", "Forecast temperature range", "How much rain is forecast?"):
                result = self.executor.execute(self.router.route(question), market_snapshot=market, weather_snapshot=weather)
                self.assertEqual(result.status, ExternalExecutionStatus.ANSWERED)


class ExternalSelectionTests(unittest.TestCase):
    def test_selector_is_frozen_and_normalizes_text(self):
        selection = ExternalSelection(market=" Aba ")
        self.assertEqual(selection.market, "Aba")
        with self.assertRaises(FrozenInstanceError):
            selection.market = "Biu"

    def test_invalid_selectors_are_rejected(self):
        hour = datetime(2026, 10, 10, tzinfo=timezone.utc)
        for kwargs in (
            {"market": " "}, {"admin_1": 3}, {"cpcv2": ""},
            {"period_date": hour}, {"period_date": "2025-01-31"},
            {"valid_from": datetime(2026, 10, 10)},
            {"valid_from": hour.replace(minute=1)},
            {"valid_from": hour.replace(tzinfo=timezone(timedelta(hours=1)))},
            {"valid_to": "2026-10-10T00:00:00Z"},
            {"valid_from": hour + timedelta(hours=1), "valid_to": hour},
            {"latitude": Decimal("0")}, {"longitude": Decimal("0")},
            {"latitude": Decimal("NaN"), "longitude": Decimal("0")},
            {"latitude": Decimal("91"), "longitude": Decimal("0")},
            {"latitude": Decimal("0"), "longitude": Decimal("181")},
            {"latitude": 5.1, "longitude": Decimal("0")},
            {"descending": 1}, {"market": "Aba", "valid_from": hour},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ExternalSelection(**kwargs)


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
