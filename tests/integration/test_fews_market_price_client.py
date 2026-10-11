"""Deterministic FEWS client checks; running this file never contacts FEWS."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from http.client import HTTPException, IncompleteRead
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler

from packages.data_sources import SourceSnapshot
from packages.data_sources.providers.fews_http_client import (
    FewsClientLimits,
    FewsHTTPError,
    FewsLimitError,
    FewsMarketPriceClient,
    FewsMarketPriceQuery,
    FewsResponseError,
)
from packages.data_sources.providers.fews_market_prices import FEWS_MARKET_SOURCE_ID


RETRIEVED_AT = datetime(2026, 10, 9, 20, 30, tzinfo=timezone.utc)


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
        "value": "998.10",
        "dataseries": 15312,
        "source_organization": "FEWS NET",
        "source_document": "FEWS NET, Nigeria, Price (weekly)",
        "collection_status": "Published",
        "modified": "2026-07-21T23:02:24",
        "longitude": "7.37063",
        "latitude": "5.10719",
        "pct_change_from_one_year_ago": 12.5,
        "two_year_average": 900,
    }
    record.update(changes)
    return record


def query(**changes):
    args = {
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 2, 28),
        "cpcv2": "R01122",
    }
    args.update(changes)
    return FewsMarketPriceQuery(**args)


def page(records=(), next_url=None, count=902):
    return {"count": count, "next": next_url, "previous": None,
            "results": list(records)}


class ScriptedHTTP:
    """Capture exact requests and provide only the explicitly scripted pages."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, *, timeout_seconds, max_response_bytes):
        self.calls.append((url, timeout_seconds, max_response_bytes))
        if not self.responses:
            raise AssertionError("Client made an unexpected additional request")
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class QueryTests(unittest.TestCase):
    def test_explicit_monthly_ng_and_cpc_filter(self):
        url = query(product="maize").url(5)
        parts = urlsplit(url)
        self.assertEqual(parts.scheme, "https")
        self.assertEqual(parts.netloc, "fdw.fews.net")
        self.assertEqual(parts.path, "/api/marketpricefacts.json")
        params = parse_qs(parts.query)
        self.assertEqual(params["country_code"], ["NG"])
        self.assertEqual(params["schedule"], ["Monthly"])
        self.assertEqual(params["cpcv2"], ["R01122"])
        self.assertNotIn("product", params)
        self.assertEqual(params["price_type"], ["Retail"])
        self.assertEqual(params["page_size"], ["5"])
        self.assertEqual(params["start_date"], ["2025-01-01"])
        self.assertEqual(params["end_date"], ["2025-02-28"])
        fields = set(params["fields"][0].split(","))
        self.assertTrue({"period_date", "modified", "cpcv2", "value",
                         "source_organization"}.issubset(fields))
        self.assertNotIn("pct_change_from_one_year_ago", fields)
        self.assertNotIn("two_year_average", fields)

    def test_product_fallback_is_encoded_without_extra_parameters(self):
        params = parse_qs(urlsplit(query(
            cpcv2=None, product="maize & sorghum", end_date=None
        ).url(2)).query)
        self.assertEqual(params["product"], ["maize & sorghum"])
        self.assertNotIn("cpcv2", params)
        self.assertNotIn("end_date", params)
        self.assertNotIn("sorghum", params)

    def test_invalid_query_is_rejected_before_http(self):
        invalid = (
            {"cpcv2": None, "product": None},
            {"cpcv2": "", "product": None},
            {"cpcv2": None, "product": "   "},
            {"start_date": date(2025, 3, 1)},
            {"price_type": "   "},
            {"start_date": "2025-01-01"},
            {"start_date": datetime(2025, 1, 1, tzinfo=timezone.utc)},
            {"end_date": "2025-02-28"},
            {"cpcv2": True}, {"product": 1}, {"price_type": None},
            {"cpcv2": "R01122,R01121"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                query(**changes)

    def test_invalid_limits_are_rejected(self):
        invalid = (
            {"page_size": 0}, {"max_pages": 0}, {"max_requests": 0},
            {"max_records": 0}, {"timeout_seconds": 0},
            {"max_response_bytes": 0}, {"max_pages": -1},
            {"timeout_seconds": float("inf")},
            {"timeout_seconds": float("nan")},
            {"timeout_seconds": True}, {"timeout_seconds": "30"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                FewsClientLimits(**changes)
        for name in ("page_size", "max_pages", "max_requests", "max_records",
                     "max_response_bytes"):
            for value in (True, 1.5, float("inf"), "10"):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    FewsClientLimits(**{name: value})

    def test_url_page_size_rejects_nonpositive_or_noninteger_values(self):
        for size in (0, -1, True, 1.5):
            with self.subTest(size=size), self.assertRaises(ValueError):
                query().url(size)


class FetchTests(unittest.TestCase):
    def client(self, http, **limits):
        return FewsMarketPriceClient(
            limits=FewsClientLimits(**limits), get_json=http,
            clock=lambda: RETRIEVED_AT,
        )

    def test_short_pages_follow_next_verbatim_and_ignore_count(self):
        request = query()
        initial = request.url(5)
        # Nonsequential offset and an encoded parameter deliberately ensure the
        # client cannot rebuild this URL or infer the next offset from row count.
        next_url = initial.replace("?", "?offset=37&", 1).replace(
            "schedule=Monthly", "schedule=%4Donthly"
        )
        http = ScriptedHTTP(
            page([raw_record()], next_url, count=1),
            page([raw_record(period_date="2025-02-28", value="968.50")],
                 count=10000),
        )
        result = self.client(http, page_size=5).fetch(request)
        self.assertEqual([call[0] for call in http.calls], [initial, next_url])
        self.assertEqual(result.pages_fetched, 2)
        self.assertEqual(result.requests_made, 2)
        self.assertIsInstance(result.records, tuple)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[1].value, Decimal("968.50"))
        self.assertFalse(hasattr(result.records[0], "two_year_average"))

    def test_empty_intermediate_page_still_follows_next(self):
        request = query()
        next_url = request.url(100) + "&offset=100"
        http = ScriptedHTTP(page([], next_url), page([raw_record()]))
        result = self.client(http).fetch(request)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.pages_fetched, 2)

    def test_snapshot_uses_observation_dates_and_retrieval_clock(self):
        http = ScriptedHTTP(page([
            raw_record(period_date="2025-02-28", modified="2099-12-31T00:00:00Z"),
            raw_record(period_date="2025-01-31", modified=None),
        ]))
        result = self.client(http).fetch(query())
        snapshot = result.snapshot
        self.assertIsInstance(snapshot, SourceSnapshot)
        self.assertEqual(snapshot.source_id, FEWS_MARKET_SOURCE_ID)
        self.assertEqual(snapshot.record_count, 2)
        self.assertEqual(snapshot.observed_from,
                         datetime(2025, 1, 31, tzinfo=timezone.utc))
        self.assertEqual(snapshot.observed_to,
                         datetime(2025, 2, 28, tzinfo=timezone.utc))
        self.assertEqual(snapshot.retrieved_at, RETRIEVED_AT)
        self.assertEqual(snapshot.refreshed_at, RETRIEVED_AT)
        self.assertEqual(result.retrieved_at, RETRIEVED_AT)
        self.assertTrue(snapshot.dataset_version.strip())
        self.assertEqual(result.records[0].source_modified_at.year, 2099)
        self.assertIsNone(result.records[1].source_modified_at)

    def test_retrieval_clock_is_sampled_after_final_page_and_normalized_to_utc(self):
        events = []
        local_time = datetime(2026, 10, 9, 15, 30,
                              tzinfo=timezone(timedelta(hours=-5)))

        def get_json(url, **kwargs):
            events.append("http")
            return page([raw_record()])

        def clock():
            events.append("clock")
            return local_time

        result = FewsMarketPriceClient(get_json=get_json, clock=clock).fetch(query())
        self.assertEqual(events[-1], "clock")
        self.assertEqual(result.retrieved_at, RETRIEVED_AT)
        self.assertEqual(result.retrieved_at.utcoffset(), timedelta(0))

    def test_empty_dataset_has_no_fabricated_snapshot(self):
        result = self.client(ScriptedHTTP(page([], count=0))).fetch(query())
        self.assertEqual(result.records, ())
        self.assertIsNone(result.snapshot)
        self.assertEqual(result.retrieved_at, RETRIEVED_AT)
        self.assertEqual(result.pages_fetched, 1)
        self.assertEqual(result.requests_made, 1)

    def test_dataset_version_identifies_content_independent_of_retrieval(self):
        request = query()
        records = [raw_record(), raw_record(period_date="2025-02-28")]
        one_page = self.client(ScriptedHTTP(page(records)), page_size=2).fetch(request)
        later_time = RETRIEVED_AT + timedelta(days=1)
        two_pages = FewsMarketPriceClient(
            limits=FewsClientLimits(page_size=1),
            get_json=ScriptedHTTP(
                page(records[:1], request.url(1) + "&offset=17"),
                page(records[1:]),
            ),
            clock=lambda: later_time,
        ).fetch(request)
        changed = self.client(ScriptedHTTP(page([
            records[0], {**records[1], "value": "999.99"},
        ])), page_size=2).fetch(request)
        self.assertNotEqual(one_page.retrieved_at, two_pages.retrieved_at)
        self.assertEqual(one_page.snapshot.dataset_version,
                         two_pages.snapshot.dataset_version)
        self.assertNotEqual(one_page.snapshot.dataset_version,
                            changed.snapshot.dataset_version)

    def test_failure_never_samples_successful_retrieval_clock(self):
        request = query()
        scenarios = (
            ({"results": {}}, FewsResponseError, FewsClientLimits()),
            (FewsHTTPError("failed"), FewsHTTPError, FewsClientLimits()),
            (page([raw_record()], request.url(100) + "&offset=100"),
             FewsLimitError, FewsClientLimits(max_pages=1)),
        )
        for payload, error_type, limits in scenarios:
            with self.subTest(error_type=error_type.__name__):
                clock = MagicMock(return_value=RETRIEVED_AT)
                client = FewsMarketPriceClient(
                    get_json=ScriptedHTTP(payload), clock=clock, limits=limits,
                )
                with self.assertRaises(error_type):
                    client.fetch(request)
                clock.assert_not_called()

    def test_naive_retrieval_clock_is_rejected(self):
        client = FewsMarketPriceClient(
            get_json=ScriptedHTTP(page([raw_record()])),
            clock=lambda: datetime(2026, 10, 9, 20, 30),
        )
        with self.assertRaises(ValueError):
            client.fetch(query())

    def test_exact_limits_are_successful_when_next_is_null(self):
        result = self.client(
            ScriptedHTTP(page([raw_record()])), page_size=1,
            max_pages=1, max_requests=1, max_records=1,
        ).fetch(query())
        self.assertEqual(result.snapshot.record_count, 1)

    def test_page_and_request_budgets_prevent_another_request(self):
        for limit_name in ("max_pages", "max_requests"):
            with self.subTest(limit=limit_name):
                request = query()
                http = ScriptedHTTP(page([raw_record()],
                                         request.url(100) + "&offset=100"))
                with self.assertRaises(FewsLimitError):
                    self.client(http, **{limit_name: 1}).fetch(request)
                self.assertEqual(len(http.calls), 1)

    def test_record_limit_rejects_oversized_page_without_partial_result(self):
        http = ScriptedHTTP(page([raw_record(), raw_record(dataseries=15313)]))
        with self.assertRaises(FewsLimitError):
            self.client(http, max_records=1).fetch(query())
        self.assertEqual(len(http.calls), 1)

    def test_record_limit_at_nonterminal_boundary_prevents_next_request(self):
        request = query()
        http = ScriptedHTTP(page([raw_record()], request.url(100) + "&offset=100"))
        with self.assertRaises(FewsLimitError):
            self.client(http, max_records=1).fetch(request)
        self.assertEqual(len(http.calls), 1)

    def test_record_limit_applies_across_pages(self):
        request = query()
        http = ScriptedHTTP(
            page([raw_record()], request.url(100) + "&offset=100"),
            page([raw_record(), raw_record(dataseries=15313)]),
        )
        with self.assertRaises(FewsLimitError):
            self.client(http, max_records=2).fetch(request)
        self.assertEqual(len(http.calls), 2)

    def test_timeout_and_byte_limits_reach_every_transport_call(self):
        request = query()
        http = ScriptedHTTP(page([], request.url(100) + "&offset=100"), page([]))
        self.client(http, timeout_seconds=7.5, max_response_bytes=2048).fetch(request)
        self.assertEqual([call[1:] for call in http.calls], [(7.5, 2048)] * 2)

    def test_loop_is_rejected_before_repeating_request(self):
        request = query()
        initial = request.url(100)
        second = initial + "&offset=100"
        http = ScriptedHTTP(page([], second), page([], initial))
        with self.assertRaises(FewsResponseError):
            self.client(http).fetch(request)
        self.assertEqual([call[0] for call in http.calls], [initial, second])

    def test_unsafe_next_urls_are_never_requested(self):
        initial = query().url(100)
        candidates = (
            initial.replace("https:", "http:", 1),
            initial.replace("fdw.fews.net", "example.invalid", 1),
            initial.replace("fdw.fews.net", "user:password@fdw.fews.net", 1),
            initial.replace("fdw.fews.net", "fdw.fews.net:444", 1),
            initial.replace("marketpricefacts.json", "other.json", 1),
            initial + "#fragment",
            " " + initial,
            initial + "\n",
            initial.replace("https://fdw.fews.net", "", 1),
        )
        for candidate in candidates:
            with self.subTest(next_url=candidate):
                http = ScriptedHTTP(page([], candidate))
                with self.assertRaises(FewsResponseError):
                    self.client(http).fetch(query())
                self.assertEqual(len(http.calls), 1)

    def test_next_scope_cannot_change(self):
        initial = query().url(100)
        missing_cpc = initial.split("?", 1)[0] + "?" + "&".join(
            parameter for parameter in initial.split("?", 1)[1].split("&")
            if not parameter.startswith("cpcv2=")
        )
        candidates = (
            initial.replace("country_code=NG", "country_code=KE"),
            initial.replace("schedule=Monthly", "schedule=Weekly"),
            initial.replace("cpcv2=R01122", "cpcv2=R01121"),
            initial.replace("price_type=Retail", "price_type=Wholesale"),
            initial.replace("start_date=2025-01-01", "start_date=2024-01-01"),
            initial.replace("end_date=2025-02-28", "end_date=2025-12-31"),
            missing_cpc,
            initial + "&country_code=KE",
        )
        for candidate in candidates:
            with self.subTest(next_url=candidate):
                http = ScriptedHTTP(page([], candidate))
                with self.assertRaises(FewsResponseError):
                    self.client(http).fetch(query())
                self.assertEqual(len(http.calls), 1)

    def test_supported_trailing_slash_endpoint_preserves_url(self):
        request = query()
        next_url = request.url(100).replace("marketpricefacts.json",
                                            "marketpricefacts/") + "&offset=100"
        http = ScriptedHTTP(page([], next_url), page([raw_record()]))
        self.client(http).fetch(request)
        self.assertEqual(http.calls[1][0], next_url)

    def test_malformed_payloads_fail_closed(self):
        candidates = (
            [], None, "not an object", {}, {"next": None},
            {"results": {}, "next": None},
            {"results": [], "next": 0},
            {"results": [], "next": ""},
            {"results": [None], "next": None},
            {"results": ["not a record"], "next": None},
            {"results": []},
        )
        for payload in candidates:
            with self.subTest(payload=payload), self.assertRaises(FewsResponseError):
                self.client(ScriptedHTTP(payload)).fetch(query())

    def test_invalid_or_out_of_scope_records_fail_closed(self):
        invalid = (
            {"value": None}, {"value": "bad number"}, {"value": "NaN"},
            {"value": "Infinity"}, {"value": "-1"},
            {"period_date": "invalid"}, {"country_code": "KE"},
            {"cpcv2": "R01121"}, {"price_type": "Wholesale"},
            {"period_date": "2024-12-31"}, {"period_date": "2025-03-31"},
            {"market": {}}, {"source_organization": []},
            {"dataseries": 1.5}, {"dataseries": True},
            {"market_id": "Infinity"}, {"value": {}}, {"latitude": []},
            {"longitude": "NaN"}, {"latitude": "Infinity"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(FewsResponseError):
                self.client(ScriptedHTTP(page([raw_record(**changes)]))).fetch(query())

    def test_failure_on_later_page_does_not_return_first_page(self):
        request = query()
        http = ScriptedHTTP(
            page([raw_record()], request.url(100) + "&offset=100"),
            page([raw_record(value=None)]),
        )
        with self.assertRaises(FewsResponseError):
            self.client(http).fetch(request)
        self.assertEqual(len(http.calls), 2)


class TransportTests(unittest.TestCase):
    def run_response(self, body, status=200, *, max_response_bytes=4096):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = status
        if isinstance(body, Exception):
            response.read.side_effect = body
        else:
            response.read.return_value = body
        opener = MagicMock()
        opener.open.return_value = response
        with patch("packages.data_sources.providers.fews_http_client.build_opener",
                   return_value=opener):
            result = FewsMarketPriceClient(
                limits=FewsClientLimits(timeout_seconds=7.5,
                                        max_response_bytes=max_response_bytes),
                clock=lambda: RETRIEVED_AT,
            ).fetch(query())
        return result, opener, response

    def test_native_transport_uses_timeout_and_bounded_read(self):
        result, opener, response = self.run_response(json.dumps(
            page([raw_record()])
        ).encode("utf-8"))
        self.assertEqual(result.snapshot.record_count, 1)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 7.5)
        response.read.assert_called_once_with(4097)
        response.__exit__.assert_called_once()

    def test_oversized_response_is_rejected(self):
        with self.assertRaises(FewsLimitError):
            self.run_response(b"x" * 65, max_response_bytes=64)

    def test_native_json_number_preserves_decimal_precision(self):
        number = "998.12345678901234567890123456789"
        body = json.dumps(page([raw_record(value=number)]))
        body = body.replace('"' + number + '"', number)
        result, _, _ = self.run_response(body.encode("utf-8"))
        self.assertEqual(result.records[0].value, Decimal(number))

    def test_installed_redirect_handler_refuses_followup_request(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = json.dumps(page([])).encode("utf-8")
        opener = MagicMock()
        opener.open.return_value = response
        with patch("packages.data_sources.providers.fews_http_client.build_opener",
                   return_value=opener) as build_opener:
            FewsMarketPriceClient(clock=lambda: RETRIEVED_AT).fetch(query())
        handlers = [handler for handler in build_opener.call_args.args
                    if isinstance(handler, HTTPRedirectHandler)]
        self.assertEqual(len(handlers), 1)
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                redirected = handlers[0].redirect_request(
                    None, None, code, "Redirect", {},
                    "https://example.invalid/unbounded-redirect",
                )
                self.assertIsNone(redirected)
        opener.open.assert_called_once()

    def test_incomplete_or_malformed_http_response_is_wrapped(self):
        for error in (IncompleteRead(b"partial", 100), HTTPException("bad response")):
            with self.subTest(error=type(error).__name__), self.assertRaises(FewsHTTPError):
                self.run_response(error)

    def test_invalid_json_or_encoding_is_rejected(self):
        for body in (b"not json", b"\xff", b"[]"):
            with self.subTest(body=body), self.assertRaises(FewsResponseError):
                self.run_response(body)

    def test_unsuccessful_status_is_rejected(self):
        for status in (301, 429, 500):
            with self.subTest(status=status), self.assertRaises(FewsHTTPError):
                self.run_response(b"{}", status)

    def test_network_failures_are_wrapped_without_retry(self):
        errors = (
            URLError("unavailable"), TimeoutError("timed out"),
            HTTPError(query().url(100), 503, "unavailable", {}, None),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                opener = MagicMock()
                opener.open.side_effect = error
                with patch(
                    "packages.data_sources.providers.fews_http_client.build_opener",
                    return_value=opener,
                ), self.assertRaises(FewsHTTPError):
                    FewsMarketPriceClient().fetch(query())
                opener.open.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
