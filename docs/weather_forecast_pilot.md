# Phase 26C.1 — Forecast contract and bounded retrieval pilot

This is the Phase 26C.1 retrieval contract and original evaluation record. Its
local-only and next-step statements describe that milestone. Later persistence,
API queries, scheduled refresh and hosted rollout are described in
[architecture](architecture.md), [deployment](deployment.md), the
[environment contract](environment_contract.md) and [Phase 29](phase29_closure.md).

The first weather integration was an explicit local Open-Meteo forecast retrieval.
It defines `WeatherForecastRecord`, normalizes the provider response, and creates
the existing Phase 26A `SourceSnapshot` only after validation succeeds. Importing
the modules performs no network or filesystem I/O. The pilot does not register
itself at API startup or change Wave 5, FEWS, question routing, or core readiness.
Weather persistence and a read-only API were the next Phase 26C step; their
later integration is described in the guides linked above.

## Scope and provider choice

The initial query uses the public Aba market coordinates from the FEWS pilot:
latitude 5.10719, longitude 7.37063. It retrieves three UTC calendar days including
today, with hourly temperature at 2 m, relative humidity at 2 m, and precipitation.
These are model forecasts for a grid cell, not measurements at the market or a
farm, and not surveyed community climate expectations.

The request explicitly selects `ecmwf_ifs025`, UTC/GMT, Unix timestamps, Celsius,
millimetres, and the nearest grid cell. `elevation=nan` disables elevation
downscaling. Both requested and returned grid coordinates are retained. This
model choice makes the pilot reproducible; it is not a comparative accuracy
assessment for Nigeria.

Provider references: [forecast documentation](https://open-meteo.com/en/docs),
[ECMWF documentation](https://open-meteo.com/en/docs/ecmwf-api), and
[model configuration](https://raw.githubusercontent.com/open-meteo/open-meteo-website/main/src/routes/en/docs/ecmwf-api/options.ts).
The model's hourly output can be interpolated from coarser forecast steps.
Relative humidity is provider-derived; the pilot does not calculate agronomic
advice or additional weather metrics.

Open-Meteo's [pricing](https://open-meteo.com/en/pricing) permits free evaluation
and prototyping. Commercial rollout requires the appropriate subscribed customer
service; this implementation targets the public evaluation endpoint only. Data
attribution is retained as Open-Meteo / ECMWF, with CC BY 4.0 licensing. There is
no scheduled refresh or production enablement in this original checkpoint.

## Time and missing-data meaning

`valid_at` is an aware UTC hour. Temperature and humidity apply at that instant;
precipitation is the total over the preceding hour. The record's
`precipitation_period_start` property gives that interval's beginning. Thus the
first precipitation interval starts an hour before the first valid timestamp.
The calendar-day window can include hours earlier than the retrieval time; those
values remain forecast-product values, not verified observations.

The standard forecast product combines recent model runs. It does not supply a
single reliable initialization time in this response, so `source_issued_at` is
null. `generationtime_ms` is response-processing duration and is excluded from
both timestamps and content identity. See the provider's
[response writer](https://raw.githubusercontent.com/open-meteo/open-meteo/main/Sources/App/Helper/Writer/JsonWriter.swift)
and [Single Runs documentation](https://open-meteo.com/en/docs/single-runs-api).

`retrieved_at` comes from AgDA's clock after normalization succeeds. The legacy
`SourceSnapshot.observed_from` and `observed_to` fields contain the first and last
forecast-valid hours for this `WEATHER_FORECAST` source. They do not reclassify
forecasts as observations or include the preceding precipitation interval.
`refreshed_at` equals retrieval time. The source's six-hour stale threshold is a
local retrieval-age policy; the pilot metadata
`expected_refresh_hours=None` does not describe the later hosted scheduler.
No provider issue-time freshness or forecast skill is inferred.

Individual null values remain null, and `missing_value_count` counts them across
all three variables. The probe reports `data_quality: partial` when any are
missing. A response with every value missing fails and creates no snapshot.
Prices and weather values are never joined or aggregated in this phase.

## Request bounds and failure behavior

The client performs exactly one request with no retries or automatic redirects.
The query permits one coordinate and one to seven days. Defaults are three days,
168 maximum records, a 20-second socket timeout, and a 1 MiB response limit. The
timeout is a socket timeout, not a total wall-clock deadline. The requested hour
count is checked before HTTP, and the received count before normalization.

The response must contain the expected units, UTC offset and timezone, and four
aligned arrays covering every requested hourly timestamp in order. Short or
extra arrays, duplicate/gapped/out-of-window timestamps, malformed responses,
incorrect units, non-finite values, and invalid humidity or precipitation fail.
A nearest-cell distance over 50 km is rejected for the pinned 0.25-degree model.
This distance is an input-consistency guard, not a forecast accuracy radius.

Every failure raises a typed client error and returns no partial successful
result or snapshot. There are no file writes or registry updates to roll back.
The content version is `open-meteo-hourly-v1:` plus a SHA-256 of the explicit
request and normalized records. It identifies the query result, not an upstream
model release, and is independent of retrieval and processing durations.

## Run the optional probe

From the AgDA repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe .\tools\probe_weather_forecast.py
.\.venv\Scripts\python.exe .\tools\probe_weather_forecast.py --live
```

The first command confirms that live access is disabled. The second makes one
bounded request and prints a summary, provenance, missing-value count, and one
record. Neither command saves data. `--help` lists coordinate, day, and limit
overrides. Invalid arguments or retrieval failures exit with code 2.

## Verification checkpoint

The deterministic integration script is included in the backend runner:

```powershell
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\python.exe .\tests\integration\test_weather_forecast_client.py
.\.venv\Scripts\python.exe .\tests\integration\run_backend_regression.py
```

Contract, query, normalization, transport, clock, provenance, and CLI checks use
mocked HTTP and fixed clocks. They require no live weather service.

One separate live evaluation succeeded at `2026-10-10T12:51:36.345439+00:00`:
one request, 72 records, zero missing values, valid hours from October 10 at
00:00 UTC through October 12 at 23:00 UTC. The returned grid point was 5.0, 7.25.
The content version was
`open-meteo-hourly-v1:78105377c9e9a032b26629e8ba1e0307eb845a72774c52231003e36c660ba401`.
This confirms transport/schema compatibility for that retrieval, not model skill.
