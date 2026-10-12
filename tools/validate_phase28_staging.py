"""Read-only Phase 28 staging checks using saved snapshots and standard-library HTTP.

Run inside the staging API container, or supply its URL with --base-url.
The first request verifies staging before any analytical POST is permitted.
No credentials, external refreshes, configuration changes or deployments are used.
"""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MARKET_METRIC = "market_price_ngn_per_kg"
TEMPERATURE_METRIC = "forecast_temperature_2m_c"
RAIN_METRIC = "forecast_precipitation_mm"
MARKET_SOURCE = "fews_net_market_prices_ng"
WEATHER_SOURCE = "open_meteo_forecast"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class CheckFailure(Exception):
    """Only controlled, non-sensitive messages may be attached to this error."""


def require(condition, message):
    if not condition:
        raise CheckFailure(message)


def emit(check, status="passed", **fields):
    print(json.dumps({"check": check, "status": status, **fields}, separators=(",", ":")), flush=True)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StagingClient:
    def __init__(self, base_url):
        parsed = urlsplit(base_url)
        require(
            parsed.scheme in ("http", "https") and parsed.hostname
            and parsed.username is None and parsed.password is None
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment,
            "Base URL must be an HTTP(S) origin without credentials or a path.",
        )
        self.base_url = base_url.rstrip("/")
        self.staging_verified = False
        # Redirects must not move analytical POSTs away from the verified origin.
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, *, payload=None, expected_status=200):
        method = "POST" if payload is not None else "GET"
        require(
            self.staging_verified or (method == "GET" and path == "/v1/health"),
            "Only the initial health request is permitted before staging verification.",
        )
        require(
            (method == "GET" and path.split("?", 1)[0] in (
                "/v1/health", "/v1/market-prices", "/v1/weather-forecast",
            )) or (method == "POST" and path in ("/v1/external-queries", "/v1/questions")),
            "The smoke script permits only health, saved-data and analytical endpoints.",
        )
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self.base_url + path, data=data, method=method, headers={
            "Accept": "application/json", "Content-Type": "application/json",
        })
        try:
            with self.opener.open(request, timeout=30) as response:
                status = response.status
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            status = error.code
            error.close()
            require(status == expected_status, f"Unexpected HTTP status {status}; expected {expected_status}.")
            return None
        except (URLError, TimeoutError, OSError):
            raise CheckFailure("HTTP request failed or timed out.") from None
        require(status == expected_status, f"Unexpected HTTP status {status}; expected {expected_status}.")
        require(len(body) <= MAX_RESPONSE_BYTES, "HTTP response exceeded the allowed size.")
        try:
            result = json.loads(body)
        except (UnicodeError, ValueError):
            raise CheckFailure("HTTP response was not valid JSON.") from None
        require(isinstance(result, dict), "Expected a JSON object response.")
        return result

    def health(self, check):
        body = self.request("/v1/health")
        require(body.get("environment") == "staging", "Environment is not exactly staging; analytical POSTs refused.")
        require(body.get("ready") is True and body.get("status") == "ready", "Wave5 core is not ready.")
        require(body.get("data_version") == "wave5_v1", "Wave5 data version changed.")
        require(body.get("release_state") == "stable", "Wave5 release is not stable.")
        require(body.get("metric_version") == "1.0.0", "Wave5 metric version changed.")
        require(body.get("registered_metrics") == 18, "Wave5 metric count changed.")
        require(body.get("external_sources", {}).get("affects_core_readiness") is False,
                "External sources must not affect core readiness.")
        self.staging_verified = True
        emit(check, environment="staging", data_version="wave5_v1", release_state="stable",
             metric_version="1.0.0", registered_metrics=18, ready=True, affects_core_readiness=False)


def snapshot_id(page):
    value = page.get("snapshot_id")
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "Invalid saved snapshot identity.")
    return value


def utc_hour(value):
    require(isinstance(value, str), "Expected ISO forecast time.")
    try:
        instant = datetime.fromisoformat(value)
    except ValueError:
        raise CheckFailure("Invalid ISO forecast time.") from None
    require(instant.utcoffset() == timedelta(0) and not (instant.minute or instant.second or instant.microsecond),
            "Saved forecast time must align to a UTC hour.")
    return instant.astimezone(timezone.utc)


def external(client, metric, operation, pinned, *, selection=None, status="answered", **extra):
    body = client.request("/v1/external-queries", payload={
        "metric_id": metric, "operation": operation, "snapshot_id": pinned,
        "selection": selection or {}, **extra,
    })
    source_id = MARKET_SOURCE if metric == MARKET_METRIC else WEATHER_SOURCE
    require(body.get("domain") == "external" and body.get("affects_core_readiness") is False,
            "External answer domain or core-readiness guardrail changed.")
    require(body.get("status") == status, "Unexpected external execution status.")
    require(body.get("snapshot_id") == pinned and body.get("source_id") == source_id,
            "External answer snapshot or source changed.")
    require(body.get("metric_id") == metric and body.get("operation") == operation,
            "External answer metric or operation changed.")
    require(body.get("source", {}).get("source_id") == source_id and isinstance(body.get("source", {}).get("query"), dict),
            "External answer is missing saved-query provenance.")
    require(isinstance(body.get("rows"), list), "External answer rows are missing.")
    return body


def check_saved_data(client):
    market = client.request("/v1/market-prices?limit=1")
    weather = client.request("/v1/weather-forecast?limit=1")
    market_pin, weather_pin = snapshot_id(market), snapshot_id(weather)
    require(len(market.get("records", [])) == 1 and len(weather.get("records", [])) == 1,
            "Saved market and forecast samples must both exist.")
    sample = market["records"][0]
    selection = {key: sample[key] for key in ("market", "admin_1", "cpcv2", "period_date") if sample.get(key) is not None}
    body = external(client, MARKET_METRIC, "value", market_pin, selection=selection)
    require(len(body["rows"]) == 1, "Market selection must return exactly one observation.")
    row = body["rows"][0]
    require(Decimal(row["value"]) == Decimal(sample["value"]) and row["unit"] == "NGN/kg",
            "Selected market value differs from its saved observation.")
    require(all(row.get(key) == value for key, value in selection.items()), "Selected market dimensions differ.")
    emit("exact_market_observation", snapshot_id=market_pin, rows=1)

    rank_selection = {"period_date": sample["period_date"], "cpcv2": sample["cpcv2"], "descending": True}
    ranked = external(client, MARKET_METRIC, "rank", market_pin, selection=rank_selection, max_items=5)
    rows = ranked["rows"]
    require(1 <= len(rows) <= 5, "Market ranking has an unexpected row count.")
    dimensions = ("period_date", "cpcv2", "product", "unit", "price_type", "product_source", "country_code")
    require(len({tuple(row.get(key) for key in dimensions) for row in rows}) == 1,
            "Market ranking mixed incompatible observations.")
    require(all(row.get("period_date") == sample["period_date"] and row.get("cpcv2") == sample["cpcv2"]
                and row.get("unit") == "NGN/kg" and row.get("price_type", "").casefold() == "retail"
                and row.get("product", "").casefold() == "maize grain (white)" and row.get("country_code") == "NG"
                for row in rows), "Market ranking changed metric scope.")
    require([Decimal(row["value"]) for row in rows] == sorted((Decimal(row["value"]) for row in rows), reverse=True),
            "Market ranking is not descending.")
    require([row.get("rank") for row in rows] == list(range(1, len(rows) + 1)), "Market ranks are not sequential.")
    emit("compatible_market_ranking", rows=len(rows))

    # Fetch the same bounded forecast to independently verify aggregation and coverage.
    full = client.request("/v1/weather-forecast?" + urlencode({"limit": 168, "snapshot_id": weather_pin}))
    require(snapshot_id(full) == weather_pin and full.get("next_offset") is None, "Saved forecast is not one bounded page.")
    records = full.get("records", [])
    require(len(records) == full.get("total") and records, "Saved forecast page is incomplete.")
    usable = next((record for record in records if record.get("temperature_2m_c") is not None), None)
    require(usable is not None, "Saved forecast has no temperature value for the staging proof.")
    hour = utc_hour(usable["valid_at"])
    coordinates = {"latitude": usable["requested_latitude"], "longitude": usable["requested_longitude"]}
    body = external(client, TEMPERATURE_METRIC, "value", weather_pin, selection={
        **coordinates, "valid_from": hour.isoformat(), "valid_to": hour.isoformat(),
    })
    require(len(body["rows"]) == 1, "Forecast hour selection must return one row.")
    row = body["rows"][0]
    require(Decimal(row["value"]) == Decimal(usable["temperature_2m_c"]) and row["unit"] == "°C"
            and utc_hour(row["valid_at"]) == hour, "Selected temperature differs from its saved hour.")
    require(row.get("expected_hours") == 1 and row.get("hours_with_values") == 1 and row.get("missing_hours") == 0,
            "Selected temperature coverage is incorrect.")
    require(all(Decimal(body["source"]["query"][key]) == Decimal(value) for key, value in coordinates.items()),
            "Forecast provenance does not retain requested coordinates.")
    emit("exact_forecast_temperature", snapshot_id=weather_pin, expected_hours=1)

    start, end = utc_hour(full["source"]["observed_from"]), utc_hour(full["source"]["observed_to"])
    expected_hours = int((end - start).total_seconds() // 3600) + 1
    values = [Decimal(record["precipitation_mm"]) for record in records if record.get("precipitation_mm") is not None]
    require(values, "Saved forecast has no precipitation values for the staging proof.")
    body = external(client, RAIN_METRIC, "sum", weather_pin, selection={
        **coordinates, "valid_from": start.isoformat(), "valid_to": end.isoformat(),
    })
    require(len(body["rows"]) == 1, "Forecast sum must return one aggregate row.")
    row = body["rows"][0]
    missing = expected_hours - len(values)
    require(Decimal(row["total"]) == sum(values, Decimal("0")) and row.get("unit") == "mm",
            "Precipitation total differs from saved hourly values.")
    require((row.get("expected_hours"), row.get("hours_with_values"), row.get("missing_hours"))
            == (expected_hours, len(values), missing), "Precipitation coverage differs from saved hourly values.")
    require(row.get("data_quality") == ("partial" if missing else "complete"), "Precipitation quality label is incorrect.")
    require(utc_hour(row["interval_start"]) == start - timedelta(hours=1) and utc_hour(row["interval_end"]) == end,
            "Precipitation interval does not cover the preceding hourly periods.")
    emit("forecast_total_and_coverage", expected_hours=expected_hours, hours_with_values=len(values), missing_hours=missing)

    unavailable = external(client, TEMPERATURE_METRIC, "range", weather_pin, status="unavailable", selection={
        "valid_from": start.isoformat(), "valid_to": (end + timedelta(hours=1)).isoformat(),
    })
    require(not unavailable["rows"] and bool(unavailable.get("reason")), "Out-of-coverage request was silently truncated.")
    emit("out_of_coverage_unavailable")

    for check, payload in (
        ("wrong_operation_rejected", {"metric_id": MARKET_METRIC, "operation": "sum"}),
        ("wrong_source_selector_rejected", {"metric_id": TEMPERATURE_METRIC, "operation": "value", "selection": {"market": sample["market"]}}),
    ):
        client.request("/v1/external-queries", payload=payload, expected_status=422)
        emit(check, http=422)
    bad_pin = ("1" if weather_pin[0] == "0" else "0") + weather_pin[1:]
    client.request("/v1/external-queries", payload={
        "metric_id": TEMPERATURE_METRIC, "operation": "range", "snapshot_id": bad_pin,
    }, expected_status=409)
    emit("wrong_snapshot_pin_rejected", http=409)


def check_questions(client):
    for check, question, metric in (
        ("wave5_yield", "Which states have the lowest maize yields?", "median_completed_yield"),
        ("wave5_price_change", "What is the median maize price change?", "median_same_basis_price_change"),
        ("wave5_climate_expectations", "How worried are communities in the North West about flooding?", "climate_likely_share"),
    ):
        body = client.request("/v1/questions", payload={"question": question})
        require(body.get("status") == "answered", "Wave5 regression question was not answered.")
        require(body.get("data_version") == "wave5_v1" and body.get("metric_version") == "1.0.0",
                "Wave5 regression question changed release contracts.")
        require((body.get("question_specification") or {}).get("metric_id") == metric,
                "Wave5 regression question routed to the wrong metric.")
        emit(check, metric_id=metric, data_version="wave5_v1")

    for check, question in (
        ("mixed_core_external_reframed", "Compare maize yields and market price."),
        ("qualified_location_reframed", "Will it rain in Lagos?"),
    ):
        body = client.request("/v1/questions", payload={"question": question})
        require(body.get("status") == "reframe_required" and body.get("result") is None,
                "Question qualification or source mixing was silently ignored.")
        emit(check)

    body = client.request("/v1/questions", payload={"question": "Which market has the highest maize price?"})
    result = body.get("result") or {}
    require(body.get("status") == "answered" and result.get("source_id") == MARKET_SOURCE
            and result.get("metric_id") == MARKET_METRIC and result.get("rows"),
            "Legacy external ranking failed.")
    require(body.get("data_version", "").startswith("fews-monthly-v1:") and body.get("metric_version") is None,
            "External ranking was presented as a Wave5 answer.")
    emit("legacy_external_ranking", rows=len(result["rows"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Staging HTTP(S) origin; defaults to localhost at PORT (or 8000).")
    args = parser.parse_args(argv)
    try:
        port = os.environ.get("PORT", "8000")
        require(bool(re.fullmatch(r"[0-9]{1,5}", port)) and 1 <= int(port) <= 65535, "PORT must be a valid TCP port.")
        client = StagingClient(args.base_url or f"http://127.0.0.1:{port}")
        client.health("core_before")
        try:
            check_saved_data(client)
            check_questions(client)
        finally:
            client.health("core_after")
    except CheckFailure as error:
        emit("phase28_staging", status="failed", reason=str(error))
        return 1
    except Exception as error:
        # Never echo response bodies, request data, URLs, paths or exception details.
        emit("phase28_staging", status="failed", reason="Unexpected response shape or execution error.", error_type=type(error).__name__)
        return 1
    emit("phase28_staging", environment="staging", result="success")
    return 0


if __name__ == "__main__":
    sys.exit(main())
