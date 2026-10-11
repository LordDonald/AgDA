"""Deterministic forecast contract/client checks; no requests reach a provider."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from http.client import HTTPException, IncompleteRead
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler

from packages.data_sources.contracts import SourceSnapshot, SourceType
from packages.data_sources.weather_forecasts import WeatherForecastRecord
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    OPEN_METEO_FORECAST_URL,
    OPEN_METEO_MODEL,
    OpenMeteoForecastClient,
    OpenMeteoForecastQuery,
    WeatherClientLimits,
    WeatherHTTPError,
    WeatherLimitError,
    WeatherResponseError,
    build_open_meteo_source_definition,
    normalize_open_meteo_forecast,
)


START_DATE = date(2026, 10, 10)
ANCHOR_AT = datetime(2026, 10, 10, 12, 30, tzinfo=timezone.utc)
RETRIEVED_AT = ANCHOR_AT + timedelta(seconds=2)
FIRST_HOUR = datetime(2026, 10, 10, tzinfo=timezone.utc)
MODULE = "packages.data_sources.providers.open_meteo_forecast"
VARIABLES = ("temperature_2m", "relative_humidity_2m", "precipitation")


def query(**changes):
    values = {"latitude": Decimal("5.10719"),
              "longitude": Decimal("7.37063"), "forecast_days": 1}
    values.update(changes)
    return OpenMeteoForecastQuery(**values)


def payload(*, forecast_days=1, start_date=START_DATE):
    start = datetime.combine(start_date, datetime.min.time(), timezone.utc)
    count = forecast_days * 24
    return {
        "latitude": 5.125,
        "longitude": 7.375,
        "generationtime_ms": 0.045,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 81.0,
        "hourly_units": {"time": "unixtime", "temperature_2m": "\u00b0C",
                         "relative_humidity_2m": "%", "precipitation": "mm"},
        "hourly": {
            "time": [int((start + timedelta(hours=i)).timestamp())
                     for i in range(count)],
            "temperature_2m": [26.5] * count,
            "relative_humidity_2m": [83] * count,
            "precipitation": [0.2] * count,
        },
    }


def record(**changes):
    values = {
        "source_id": OPEN_METEO_FORECAST_SOURCE_ID,
        "model": OPEN_METEO_MODEL,
        "requested_latitude": Decimal("5.10719"),
        "requested_longitude": Decimal("7.37063"),
        "grid_latitude": Decimal("5.125"),
        "grid_longitude": Decimal("7.375"),
        "valid_at": FIRST_HOUR,
        "temperature_2m_c": Decimal("26.5"),
        "relative_humidity_2m_pct": Decimal("83"),
        "precipitation_mm": Decimal("0.2"),
    }
    values.update(changes)
    return WeatherForecastRecord(**values)


class ScriptedHTTP:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, url, *, timeout_seconds, max_response_bytes):
        self.calls.append((url, timeout_seconds, max_response_bytes))
        if len(self.calls) > 1:
            raise AssertionError("Unexpected second request")
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def fetch(response=None, request=None, **limits):
    http = ScriptedHTTP(payload() if response is None else response)
    clock = MagicMock(side_effect=[ANCHOR_AT, RETRIEVED_AT])
    result = OpenMeteoForecastClient(
        get_json=http, clock=clock, limits=WeatherClientLimits(**limits),
    ).fetch(query() if request is None else request)
    return result, http, clock


class ContractTests(unittest.TestCase):
    def test_forecast_record_is_immutable_and_keeps_unknown_issue_time(self):
        sample = record()
        self.assertIsNone(sample.source_issued_at)
        self.assertEqual(sample.valid_at, FIRST_HOUR)
        self.assertEqual(sample.temperature_2m_c, Decimal("26.5"))
        with self.assertRaises(FrozenInstanceError):
            sample.temperature_2m_c = Decimal("25")

    def test_null_measurements_are_preserved_as_unknown_not_zero(self):
        sample = record(temperature_2m_c=None, relative_humidity_2m_pct=None,
                        precipitation_mm=None)
        self.assertIsNone(sample.temperature_2m_c)
        self.assertIsNone(sample.relative_humidity_2m_pct)
        self.assertIsNone(sample.precipitation_mm)

    def test_invalid_numeric_types_and_nonfinite_values_are_rejected(self):
        fields = ("requested_latitude", "requested_longitude", "grid_latitude",
                  "grid_longitude", "temperature_2m_c",
                  "relative_humidity_2m_pct", "precipitation_mm")
        for field in fields:
            for value in (True, "1", 1.5, Decimal("NaN"), Decimal("Infinity")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    record(**{field: value})

    def test_invalid_physical_bounds_are_rejected(self):
        invalid = {"requested_latitude": Decimal("90.1"),
                   "requested_longitude": Decimal("-180.1"),
                   "grid_latitude": Decimal("-90.1"),
                   "grid_longitude": Decimal("180.1"),
                   "temperature_2m_c": Decimal("-273.16"),
                   "relative_humidity_2m_pct": Decimal("100.1"),
                   "precipitation_mm": Decimal("-0.01")}
        for field, value in invalid.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                record(**{field: value})
        with self.assertRaises(ValueError):
            record(relative_humidity_2m_pct=Decimal("-0.1"))

    def test_valid_boundary_measurements_are_kept(self):
        sample = record(temperature_2m_c=Decimal("-273.15"),
                        relative_humidity_2m_pct=Decimal("100"),
                        precipitation_mm=Decimal("0"))
        self.assertEqual(sample.precipitation_mm, 0)
        self.assertEqual(sample.temperature_2m_c, Decimal("-273.15"))

    def test_invalid_validity_and_issue_timestamps_are_rejected(self):
        for value in (datetime(2026, 10, 10), FIRST_HOUR + timedelta(minutes=1),
                      FIRST_HOUR + timedelta(microseconds=1), "2026-10-10", True,
                      datetime(2026, 10, 10, tzinfo=timezone(timedelta(hours=1)))):
            with self.subTest(value=value), self.assertRaises(ValueError):
                record(valid_at=value)
        with self.assertRaises(ValueError):
            record(source_issued_at=datetime(2026, 10, 10))

    def test_precipitation_interval_is_the_preceding_hour(self):
        sample = record()
        self.assertEqual(sample.precipitation_period_start,
                         datetime(2026, 10, 9, 23, tzinfo=timezone.utc))

    def test_definition_identifies_forecast_and_retrieval_age_policy(self):
        definition = build_open_meteo_source_definition()
        self.assertEqual(definition.source_id, OPEN_METEO_FORECAST_SOURCE_ID)
        self.assertEqual(definition.source_type, SourceType.WEATHER_FORECAST)
        self.assertEqual(definition.stale_after_hours, 6)
        self.assertTrue(definition.attribution)
        self.assertIn("forecast", definition.methodology_note.lower())
        self.assertIn("retriev", definition.methodology_note.lower())


class QueryTests(unittest.TestCase):
    def test_explicit_model_units_utc_and_date_window(self):
        request = query(forecast_days=3)
        url = request.url(START_DATE)
        parts = urlsplit(url)
        endpoint = urlsplit(OPEN_METEO_FORECAST_URL)
        self.assertEqual((parts.scheme, parts.netloc, parts.path),
                         (endpoint.scheme, endpoint.netloc, endpoint.path))
        params = parse_qs(parts.query)
        expected = {
            "latitude": "5.10719", "longitude": "7.37063",
            "start_date": "2026-10-10", "end_date": "2026-10-12",
            "models": "ecmwf_ifs025", "timezone": "GMT", "timeformat": "unixtime",
            "temperature_unit": "celsius", "precipitation_unit": "mm",
            "cell_selection": "nearest", "elevation": "nan",
        }
        for key, value in expected.items():
            with self.subTest(parameter=key):
                self.assertEqual(params[key], [value])
        self.assertEqual(set(params["hourly"][0].split(",")), set(VARIABLES))
        self.assertNotIn("current", params)
        self.assertNotIn("daily", params)

    def test_default_horizon_is_three_days_and_maximum_is_seven(self):
        request = OpenMeteoForecastQuery(Decimal("5.1"), Decimal("7.3"))
        self.assertEqual(request.forecast_days, 3)
        params = parse_qs(urlsplit(query(forecast_days=7).url(START_DATE)).query)
        self.assertEqual(params["end_date"], ["2026-10-16"])

    def test_invalid_horizons_coordinates_and_dates_are_rejected(self):
        invalid = (
            {"forecast_days": 0}, {"forecast_days": 8}, {"forecast_days": True},
            {"forecast_days": 1.5}, {"forecast_days": "3"},
            {"latitude": Decimal("90.1")}, {"longitude": Decimal("-180.1")},
            {"latitude": True}, {"latitude": Decimal("NaN")},
            {"longitude": Decimal("Infinity")}, {"latitude": "5.1"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                query(**changes)
        for value in ("2026-10-10", ANCHOR_AT, True):
            with self.subTest(start_date=value), self.assertRaises(ValueError):
                query().url(value)

    def test_invalid_limits_are_rejected(self):
        for field in ("max_records", "max_response_bytes"):
            for value in (0, -1, True, 1.5, "10"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    WeatherClientLimits(**{field: value})
        for value in (0, -1, True, "20", float("inf"), float("nan")):
            with self.subTest(timeout=value), self.assertRaises(ValueError):
                WeatherClientLimits(timeout_seconds=value)


class NormalizationTests(unittest.TestCase):
    def normalize(self, response):
        return normalize_open_meteo_forecast(response, query(), START_DATE)

    def test_hourly_records_preserve_requested_and_grid_location(self):
        records = self.normalize(payload())
        self.assertIsInstance(records, tuple)
        self.assertEqual(len(records), 24)
        sample = records[0]
        self.assertEqual(sample.requested_latitude, Decimal("5.10719"))
        self.assertEqual(sample.grid_latitude, Decimal("5.125"))
        self.assertEqual(sample.requested_longitude, Decimal("7.37063"))
        self.assertEqual(sample.grid_longitude, Decimal("7.375"))
        self.assertEqual(sample.source_id, OPEN_METEO_FORECAST_SOURCE_ID)
        self.assertEqual(sample.model, "ecmwf_ifs025")
        self.assertEqual(sample.valid_at, FIRST_HOUR)
        self.assertEqual(records[-1].valid_at, FIRST_HOUR + timedelta(hours=23))
        self.assertEqual(sample.temperature_2m_c, Decimal("26.5"))
        self.assertEqual(sample.relative_humidity_2m_pct, Decimal("83"))
        self.assertEqual(sample.precipitation_mm, Decimal("0.2"))
        self.assertIsNone(sample.source_issued_at)

    def test_null_sample_is_allowed_when_other_hours_have_values(self):
        response = payload()
        for name in VARIABLES:
            response["hourly"][name][0] = None
        records = self.normalize(response)
        self.assertIsNone(records[0].temperature_2m_c)
        self.assertIsNone(records[0].relative_humidity_2m_pct)
        self.assertIsNone(records[0].precipitation_mm)
        self.assertEqual(records[1].precipitation_mm, Decimal("0.2"))

    def test_wholly_null_response_is_rejected(self):
        response = payload()
        for name in VARIABLES:
            response["hourly"][name] = [None] * 24
        with self.assertRaises(WeatherResponseError):
            self.normalize(response)

    def test_absent_nonobject_and_provider_error_payloads_are_rejected(self):
        for response in (None, [], [payload()], "{}", {},
                         {"error": True, "reason": "Invalid model"}):
            with self.subTest(kind=type(response).__name__), self.assertRaises(WeatherResponseError):
                self.normalize(response)
        response = payload()
        response["error"] = True
        with self.assertRaises(WeatherResponseError):
            self.normalize(response)

    def test_required_top_level_metadata_cannot_be_missing(self):
        for key in ("latitude", "longitude", "utc_offset_seconds", "timezone",
                    "hourly_units", "hourly"):
            response = payload()
            del response[key]
            with self.subTest(key=key), self.assertRaises(WeatherResponseError):
                self.normalize(response)

    def test_timezone_must_be_utc_with_zero_offset(self):
        for zone in ("GMT", "UTC", "Etc/GMT", "Etc/UTC"):
            response = payload()
            response["timezone"] = zone
            with self.subTest(timezone=zone):
                self.assertEqual(len(self.normalize(response)), 24)
        for changes in ({"timezone": "Africa/Lagos"}, {"utc_offset_seconds": 3600},
                        {"utc_offset_seconds": False}, {"timezone": None}):
            response = payload()
            response.update(changes)
            with self.subTest(changes=changes), self.assertRaises(WeatherResponseError):
                self.normalize(response)

    def test_wrong_missing_or_ambiguous_units_are_rejected(self):
        for key, invalid in (("time", "iso8601"), ("temperature_2m", "\u00b0F"),
                             ("relative_humidity_2m", "fraction"), ("precipitation", "inch")):
            for replacement in (invalid, None):
                response = payload()
                if replacement is None:
                    del response["hourly_units"][key]
                else:
                    response["hourly_units"][key] = replacement
                with self.subTest(key=key, replacement=replacement), self.assertRaises(WeatherResponseError):
                    self.normalize(response)

    def test_missing_short_long_and_nonarray_hourly_fields_are_rejected(self):
        for field in ("time", *VARIABLES):
            for mode in ("missing", "short", "long", "nonarray"):
                response = payload()
                if mode == "missing":
                    del response["hourly"][field]
                elif mode == "short":
                    response["hourly"][field].pop()
                elif mode == "long":
                    response["hourly"][field].append(response["hourly"][field][-1])
                else:
                    response["hourly"][field] = {"0": 1}
                with self.subTest(field=field, mode=mode), self.assertRaises(WeatherResponseError):
                    self.normalize(response)

    def test_duplicate_gap_shift_reordering_and_noninteger_time_are_rejected(self):
        for mode in ("duplicate", "gap", "shift", "reversed", "float", "bool"):
            response = payload()
            times = response["hourly"]["time"]
            if mode == "duplicate":
                times[1] = times[0]
            elif mode == "gap":
                times[4] += 3600
            elif mode == "shift":
                response["hourly"]["time"] = [stamp + 3600 for stamp in times]
            elif mode == "reversed":
                times.reverse()
            elif mode == "float":
                times[0] = float(times[0])
            else:
                times[0] = True
            with self.subTest(mode=mode), self.assertRaises(WeatherResponseError):
                self.normalize(response)

    def test_bad_measurement_values_and_physical_ranges_fail_closed(self):
        for field in VARIABLES:
            values = [True, "1", {}, [], float("nan"), float("inf")]
            if field == "temperature_2m":
                values.append(-273.16)
            elif field == "relative_humidity_2m":
                values.extend([-0.1, 100.1])
            else:
                values.append(-0.1)
            for value in values:
                response = payload()
                response["hourly"][field][5] = value
                with self.subTest(field=field, value=value), self.assertRaises(WeatherResponseError):
                    self.normalize(response)

    def test_invalid_or_remote_grid_coordinates_are_rejected(self):
        for changes in ({"latitude": None}, {"latitude": True}, {"latitude": "5.125"},
                        {"latitude": float("nan")}, {"longitude": 181},
                        {"latitude": 12.0}, {"longitude": 8.0}):
            response = payload()
            response.update(changes)
            with self.subTest(changes=changes), self.assertRaises(WeatherResponseError):
                self.normalize(response)

    def test_unknown_fields_are_ignored_without_becoming_issue_time(self):
        original = self.normalize(payload())
        response = payload()
        response["model_run"] = "2026-10-10T06:00:00Z"
        response["generationtime_ms"] = 99999
        response["hourly"]["derived_drought_index"] = [42] * 24
        response["hourly_units"]["derived_drought_index"] = "unitless"
        self.assertEqual(self.normalize(response), original)


class FetchTests(unittest.TestCase):
    def test_result_snapshot_uses_successful_retrieval_and_forecast_validity(self):
        result, http, clock = fetch(timeout_seconds=7.5, max_response_bytes=50000)
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(http.calls[0], (query().url(START_DATE), 7.5, 50000))
        self.assertEqual(clock.call_count, 2)
        self.assertEqual(result.requests_made, 1)
        self.assertEqual(result.retrieved_at, RETRIEVED_AT)
        self.assertEqual(result.requested_from, FIRST_HOUR)
        self.assertEqual(result.requested_to, FIRST_HOUR + timedelta(hours=23))
        self.assertEqual(result.missing_value_count, 0)
        self.assertIsInstance(result.snapshot, SourceSnapshot)
        self.assertEqual(result.snapshot.source_id, OPEN_METEO_FORECAST_SOURCE_ID)
        self.assertEqual(result.snapshot.record_count, 24)
        self.assertEqual(result.snapshot.observed_from, FIRST_HOUR)
        self.assertEqual(result.snapshot.observed_to, result.requested_to)
        self.assertEqual(result.snapshot.refreshed_at, RETRIEVED_AT)
        self.assertEqual(result.snapshot.retrieved_at, RETRIEVED_AT)
        self.assertTrue(result.snapshot.dataset_version.startswith("open-meteo-hourly-v1:"))
        self.assertTrue(all(item.source_issued_at is None for item in result.records))

    def test_midnight_crossing_does_not_shift_the_requested_forecast_window(self):
        before = datetime(2026, 10, 10, 23, 59, 59, tzinfo=timezone.utc)
        after = before + timedelta(seconds=3)
        http = ScriptedHTTP(payload())
        result = OpenMeteoForecastClient(get_json=http,
            clock=MagicMock(side_effect=[before, after])).fetch(query())
        self.assertEqual(result.requested_from, FIRST_HOUR)
        self.assertEqual(result.snapshot.retrieved_at, after)
        self.assertEqual(parse_qs(urlsplit(http.calls[0][0]).query)["start_date"],
                         ["2026-10-10"])

    def test_clock_is_normalized_to_utc_before_selecting_request_date(self):
        local = datetime(2026, 10, 9, 21, 30,
                         tzinfo=timezone(timedelta(hours=-5)))
        http = ScriptedHTTP(payload())
        result = OpenMeteoForecastClient(get_json=http,
            clock=MagicMock(side_effect=[local, local + timedelta(seconds=2)])).fetch(query())
        self.assertEqual(result.requested_from, FIRST_HOUR)
        self.assertEqual(result.retrieved_at.utcoffset(), timedelta(0))

    def test_requested_hour_budget_is_checked_before_http(self):
        http = ScriptedHTTP(payload(forecast_days=3))
        with self.assertRaises(WeatherLimitError):
            OpenMeteoForecastClient(get_json=http, clock=lambda: ANCHOR_AT,
                limits=WeatherClientLimits(max_records=71)).fetch(query(forecast_days=3))
        self.assertEqual(http.calls, [])

    def test_overbudget_response_is_rejected_even_with_injected_http(self):
        response = payload()
        response["hourly"]["time"].extend([0] * 145)
        with self.assertRaises(WeatherLimitError):
            fetch(response)

    def test_naive_initial_clock_fails_before_request(self):
        http = ScriptedHTTP(payload())
        with self.assertRaises(ValueError):
            OpenMeteoForecastClient(get_json=http,
                clock=lambda: datetime(2026, 10, 10)).fetch(query())
        self.assertEqual(http.calls, [])

    def test_invalid_retrieval_clock_cannot_create_successful_snapshot(self):
        for after in (ANCHOR_AT - timedelta(seconds=1), datetime(2026, 10, 10)):
            http = ScriptedHTTP(payload())
            with self.subTest(retrieval=after), self.assertRaises(ValueError):
                OpenMeteoForecastClient(get_json=http,
                    clock=MagicMock(side_effect=[ANCHOR_AT, after])).fetch(query())
            self.assertEqual(len(http.calls), 1)

    def test_maximum_seven_day_window_fits_default_budget(self):
        result, http, _ = fetch(payload(forecast_days=7), query(forecast_days=7))
        self.assertEqual(len(result.records), 168)
        self.assertEqual(result.snapshot.record_count, 168)
        self.assertEqual(len(http.calls), 1)

    def test_missing_value_count_counts_measurements_not_hours(self):
        response = payload()
        response["hourly"]["temperature_2m"][0] = None
        response["hourly"]["relative_humidity_2m"][0] = None
        response["hourly"]["precipitation"][5] = None
        result, _, _ = fetch(response)
        self.assertEqual(result.missing_value_count, 3)
        self.assertEqual(result.snapshot.record_count, 24)

    def test_content_version_ignores_retrieval_and_generation_duration(self):
        first, _, _ = fetch()
        response = payload()
        response["generationtime_ms"] = 999.1
        second = OpenMeteoForecastClient(get_json=ScriptedHTTP(response),
            clock=lambda: RETRIEVED_AT + timedelta(hours=1)).fetch(query())
        self.assertEqual(first.snapshot.dataset_version, second.snapshot.dataset_version)
        self.assertNotEqual(first.retrieved_at, second.retrieved_at)

    def test_content_version_changes_for_values_and_requested_location(self):
        original, _, _ = fetch()
        response = payload()
        response["hourly"]["precipitation"][0] = 0.3
        changed_value, _, _ = fetch(response)
        changed_query, _, _ = fetch(request=query(latitude=Decimal("5.10720")))
        self.assertNotEqual(original.snapshot.dataset_version, changed_value.snapshot.dataset_version)
        self.assertNotEqual(original.snapshot.dataset_version, changed_query.snapshot.dataset_version)

    def test_invalid_later_hour_never_returns_a_partial_success(self):
        response = payload()
        response["hourly"]["relative_humidity_2m"][-1] = 101
        http = ScriptedHTTP(response)
        with self.assertRaises(WeatherResponseError):
            OpenMeteoForecastClient(get_json=http, clock=lambda: ANCHOR_AT).fetch(query())
        self.assertEqual(len(http.calls), 1)


class TransportTests(unittest.TestCase):
    def run_response(self, body, status=200, *, max_response_bytes=65536):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = status
        if isinstance(body, Exception):
            response.read.side_effect = body
        else:
            response.read.return_value = body
        opener = MagicMock()
        opener.open.return_value = response
        with patch(MODULE + ".build_opener", return_value=opener):
            result = OpenMeteoForecastClient(
                limits=WeatherClientLimits(timeout_seconds=7.5,
                                            max_response_bytes=max_response_bytes),
                clock=lambda: ANCHOR_AT,
            ).fetch(query())
        return result, opener, response

    def test_native_transport_bounds_read_and_timeout(self):
        result, opener, response = self.run_response(json.dumps(payload()).encode())
        self.assertEqual(result.snapshot.record_count, 24)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 7.5)
        response.read.assert_called_once_with(65537)
        opener.open.assert_called_once()
        response.__exit__.assert_called_once()

    def test_response_size_limit_rejects_oversized_body(self):
        with self.assertRaises(WeatherLimitError):
            self.run_response(b"x" * 65, max_response_bytes=64)

    def test_http_errors_and_network_errors_never_retry(self):
        for error in (URLError("unavailable"), TimeoutError("timed out"),
                      HTTPError(OPEN_METEO_FORECAST_URL, 429, "limited", {}, None)):
            opener = MagicMock()
            opener.open.side_effect = error
            with self.subTest(error=type(error).__name__), \
                    patch(MODULE + ".build_opener", return_value=opener), \
                    self.assertRaises(WeatherHTTPError):
                OpenMeteoForecastClient(clock=lambda: ANCHOR_AT).fetch(query())
            opener.open.assert_called_once()

    def test_unsuccessful_status_is_not_accepted_as_forecast(self):
        for status in (201, 204, 301, 429, 500):
            with self.subTest(status=status), self.assertRaises(WeatherHTTPError):
                self.run_response(json.dumps(payload()).encode(), status)

    def test_incomplete_http_response_is_wrapped(self):
        for error in (IncompleteRead(b"partial", 100), HTTPException("bad response")):
            with self.subTest(error=type(error).__name__), self.assertRaises(WeatherHTTPError):
                self.run_response(error)

    def test_malformed_encoding_json_and_nonfinite_json_are_rejected(self):
        for body in (b"not json", b"\xff", b"[]", b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(body=body), self.assertRaises(WeatherResponseError):
                self.run_response(body)

    def test_native_json_numbers_retain_decimal_precision(self):
        value = "26.12345678901234567890123456789"
        response = payload()
        response["hourly"]["temperature_2m"][0] = value
        body = json.dumps(response).replace('"' + value + '"', value)
        result, _, _ = self.run_response(body.encode())
        self.assertEqual(result.records[0].temperature_2m_c, Decimal(value))

    def test_redirect_handler_refuses_followup_requests(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = json.dumps(payload()).encode()
        opener = MagicMock()
        opener.open.return_value = response
        with patch(MODULE + ".build_opener", return_value=opener) as builder:
            OpenMeteoForecastClient(clock=lambda: ANCHOR_AT).fetch(query())
        handlers = [handler for handler in builder.call_args.args
                    if isinstance(handler, HTTPRedirectHandler)]
        self.assertEqual(len(handlers), 1)
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.assertIsNone(handlers[0].redirect_request(None, None, status,
                    "Redirect", {}, "https://example.invalid/redirect"))
        opener.open.assert_called_once()


class ProbeCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = Path(__file__).resolve().parents[2] / "tools" / "probe_weather_forecast.py"
        spec = importlib.util.spec_from_file_location("weather_probe_under_test", script)
        cls.command = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.command)

    def run_command(self, arguments, result=None, error=None):
        client = MagicMock()
        if error is not None:
            client.fetch.side_effect = error
        else:
            client.fetch.return_value = result
        output = io.StringIO()
        with patch.object(self.command, "OpenMeteoForecastClient", return_value=client) as factory, \
                patch("sys.argv", ["probe_weather_forecast.py", *arguments]), \
                patch("sys.stdout", output), \
                patch("builtins.open", side_effect=AssertionError("Probe attempted disk I/O")), \
                patch(MODULE + ".build_opener", side_effect=AssertionError("Unexpected network request")):
            code = self.command.main()
        return code, output.getvalue(), factory, client

    def test_default_invocation_never_constructs_client_or_fetches(self):
        code, output, factory, client = self.run_command([])
        self.assertEqual(code, 0)
        self.assertIn("disabled", output.lower())
        factory.assert_not_called()
        client.fetch.assert_not_called()

    def test_live_mocked_probe_emits_provenance_and_precise_values(self):
        result, _, _ = fetch(payload(forecast_days=3), query(forecast_days=3))
        code, output, factory, client = self.run_command(["--live"], result)
        self.assertEqual(code, 0)
        summary = json.loads(output)
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["data_quality"], "complete")
        self.assertEqual(summary["record_count"], 72)
        self.assertEqual(summary["requests_made"], 1)
        self.assertEqual(summary["source_type"], "weather_forecast")
        self.assertEqual(summary["model"], OPEN_METEO_MODEL)
        self.assertEqual(summary["snapshot"]["retrieved_at"], RETRIEVED_AT.isoformat())
        self.assertEqual(summary["first_record"]["temperature_2m_c"], "26.5")
        self.assertIsNone(summary["first_record"]["source_issued_at"])
        self.assertNotIn("records", summary)
        factory.assert_called_once()
        client.fetch.assert_called_once_with(query(forecast_days=3))

    def test_partial_probe_reports_missing_measurements(self):
        response = payload()
        response["hourly"]["temperature_2m"][2] = None
        result, _, _ = fetch(response)
        code, output, _, _ = self.run_command(["--live", "--days", "1"], result)
        self.assertEqual(code, 0)
        summary = json.loads(output)
        self.assertEqual(summary["data_quality"], "partial")
        self.assertEqual(summary["missing_value_count"], 1)
        self.assertEqual(summary["record_count"], 24)

    def test_limits_and_coordinates_are_forwarded_to_client(self):
        result, _, _ = fetch()
        code, _, factory, client = self.run_command([
            "--live", "--days", "1", "--latitude", "6.5", "--longitude", "8.5",
            "--max-records", "24", "--timeout-seconds", "3.5",
            "--max-response-bytes", "50000",
        ], result)
        self.assertEqual(code, 0)
        self.assertEqual(factory.call_args.kwargs["limits"],
                         WeatherClientLimits(max_records=24, timeout_seconds=3.5,
                                             max_response_bytes=50000))
        client.fetch.assert_called_once_with(OpenMeteoForecastQuery(
            latitude=Decimal("6.5"), longitude=Decimal("8.5"), forecast_days=1))

    def test_validation_failure_returns_two_without_constructing_client(self):
        for arguments in (["--live", "--latitude", "NaN"], ["--live", "--days", "8"],
                          ["--live", "--max-records", "0"]):
            with self.subTest(arguments=arguments):
                code, output, factory, client = self.run_command(arguments)
                self.assertEqual(code, 2)
                self.assertIn("failed", output.lower())
                factory.assert_not_called()
                client.fetch.assert_not_called()

    def test_fetch_failures_return_two_without_success_payload(self):
        for error in (WeatherHTTPError("Unavailable"), WeatherLimitError("Over budget"),
                      WeatherResponseError("Bad units")):
            with self.subTest(error=type(error).__name__):
                code, output, _, client = self.run_command(["--live"], error=error)
                self.assertEqual(code, 2)
                self.assertIn("failed", output.lower())
                self.assertNotIn('"status": "complete"', output)
                client.fetch.assert_called_once()

    def test_malformed_coordinate_is_a_clean_usage_error(self):
        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as raised:
            self.run_command(["--live", "--latitude", "not-a-number"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
