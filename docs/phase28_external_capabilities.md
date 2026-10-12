# Phase 28 — External capability expansion

## Baseline and boundaries

Implementation starts from `66ee03f` (Phase 27, PR #15), in a separate checkout.
The source checkout was clean. The October 12 Phase 27 closure evidence records
successful FEWS refresh, matching persisted/runtime/store snapshots, and the
`agda_external_refresh_success` event. Fresh read-only health checks confirm
staging and production still report `wave5_v1`, `stable`, metric version `1.0.0`,
18 core metrics, readiness true, and two fresh external sources.

Wave5 release artifacts, its registry and contracts remain unchanged. External
failure never determines core readiness. External data is never joined to Wave5,
and forecast weather is never relabeled as observed weather. Production remains
manual-only: API/web repository sources stay blank, only the API mounts
`/data/external`, weather cron remains `0 */4 * * *`, and FEWS cron remains
`30 3 1 * *`. Staging memory conversations and absent analytics persistence remain
separate Phase 29 follow-ups.

## Scope and acceptance criteria

1. Add `POST /v1/external-queries` for explicit queries over accepted snapshots.
   Market selectors are exact market, state, CPCv2, and observation date;
   weather selectors are inclusive UTC forecast hours and requested coordinates.
   A single hour uses equal `valid_from` and `valid_to`. No query fetches providers
   or writes a snapshot. Unknown fields and unsupported operations return 422.
2. Each external result carries snapshot identity, source attribution, effective
   ingestion query, retrieval freshness, requested selection, and time semantics.
   Optional snapshot pinning returns 409 after replacement. External responses
   never claim the Wave5 version or contribute core metrics.
3. Market rankings compare only compatible observations with one period,
   commodity, currency, unit, price type, and product origin. The existing metric
   is restricted to Nigerian white-maize retail prices in NGN/kg. Ambiguous
   selections clarify; empty selections report no available matching data.
4. Forecast answers expose expected, available and missing hours and exact valid
   bounds. Precipitation includes preceding-hour interval bounds. Partial sums
   are explicitly partial; missing values cannot prove that no rain is expected.
   Requests beyond saved time/location coverage are not silently truncated.
5. Existing natural-language questions remain bounded to their saved scope.
   Unsupported qualifiers reframe with precise-query guidance. Wave5 price-change
   and community climate questions keep core routing. Mixed-source questions
   request a reframe instead of silently combining evidence.
6. Deterministic tests cover all selectors, incorrect/ambiguous scopes, missing
   data, provenance, snapshot changes and core isolation. The complete backend
   regression and existing QA checks pass before deploying the API to staging.
   Staging API and web checks must pass; production guardrails are compared
   before and after. Production promotion is a separate manual decision.

No additional provider, automatic geographic expansion, new scheduler, frontend
redesign, production rollout, or Wave5 release change belongs to this increment.

## Explicit external query contract

The request accepts `metric_id`, `operation`, optional `selection`, optional
`snapshot_id`, and `max_items` (1–20, only for rankings; default 5). Unknown keys
are rejected. It does not accept a Wave5 metric or a second source. Operations:

| Metric | Supported operations |
| --- | --- |
| `market_price_ngn_per_kg` | `value`, `rank` |
| `forecast_temperature_2m_c` | `value`, `range` |
| `forecast_relative_humidity_2m_pct` | `value`, `range` |
| `forecast_precipitation_mm` | `value` (rain occurrence), `sum` |

For example, select an observed market price:

```json
{
  "metric_id": "market_price_ngn_per_kg",
  "operation": "value",
  "selection": {
    "market": "Aba",
    "admin_1": "Abia",
    "cpcv2": "R01122AC",
    "period_date": "2025-01-31"
  }
}
```

The date is the exact `period_date` in saved observations, not the retrieval
date. Discover current market coverage using `GET /v1/market-prices`. An exact
query never retrieves additional months or markets. Set `descending: false`
inside `selection` for lowest-first rankings; this field is only accepted for
`rank`. No implicit average across duplicate market observations is calculated.

Discover available forecast hours and requested coordinates using
`GET /v1/weather-forecast`. Supply an available hour, for example:

```json
{
  "metric_id": "forecast_temperature_2m_c",
  "operation": "value",
  "selection": {
    "valid_from": "2026-10-12T12:00:00Z",
    "valid_to": "2026-10-12T12:00:00Z",
    "latitude": "5.10719",
    "longitude": "7.37063"
  }
}
```

This example hour is illustrative, not a promise of current coverage. Timezone
offsets are normalized to UTC and must align to a UTC hour. Omitted bounds use
the saved forecast's bounds. Coordinates must be supplied together and match the
saved *requested* point, not the returned model grid point. No geocoding occurs.
Each precipitation record covers the hour preceding its valid timestamp; a
00:00–23:00 selection therefore covers precipitation intervals starting at 23:00
on the previous day. Both interval bounds are returned explicitly.

Responses have `domain: external`, `affects_core_readiness: false`, one
`snapshot_id`, source metadata, normalized requested selection, result rows,
time semantics, caution, and human-readable answer text. `source.record_count`
describes the full snapshot, while weather row coverage describes the selection.
`source.freshness` measures retrieval age, not observation recency or forecast
skill. A stale accepted snapshot remains queryable with its stale flag.

HTTP 200 uses `answered`, `needs_clarification`, or `unavailable`; the last two
include a reason and no fabricated result rows. Missing/disabled/corrupt storage
without an accepted snapshot returns sanitized 503. Invalid requests return
422; a supplied snapshot ID that no longer matches returns 409. Re-read coverage
before retrying with the new ID. Read-only queries never call refresh or reload.

Weather rows return `expected_hours`, `hours_with_values`, `missing_hours`, and
`data_quality`. A partial precipitation `total` is only the sum of available
hours, explicitly labeled as partial in the answer. `rain_expected` is null when
available values are all zero but missing hours prevent a complete conclusion.
If every selected value is missing, the result is unavailable.

## Incremental validation

- Baseline: inspect repository, prior closure evidence and live health.
- Implementation: deterministic selection/execution, routing guards, API contract.
- Local gate: full backend regression, trusted-host regression, manual QA and
  user-question QA. Review the diff for release/deployment configuration changes.
- Staging gate: deploy only the staging API; check core health, market selection,
  hourly forecast selection, partial/unsupported responses, source attribution,
  Wave5 overlap questions, mixed-source refusal and the web proxy.
- Closure: record exact checks and deployment evidence below. Do not mark a
  staging gate passed from local tests alone.

## Validation record

- Local final gate, October 12, 2026: all 47 backend regression scripts passed,
  including 40 executor tests, 16 router tests and 18 new API tests. The API tests
  include numeric-string/invalid/overflow timestamps, snapshot replacement during
  both query routes, disabled/corrupt/stale snapshots, and no request-time
  provider or snapshot-store access.
- Trusted-host regression passed; all five manual QA journeys passed; user QA
  passed 23/23. `git diff --check` passed.
- No changes to release data, Wave5 contracts/registry/loader, runtime readiness,
  provider clients, persistence, refresh operations, workflows or environment
  configuration. Frontend files are unchanged.
- `tools/validate_phase28_staging.py` supplies a repeatable staging proof. It
  rejects non-staging environments before any analytical POST, disables HTTP
  redirects, uses live snapshot pins, independently calculates expected results
  from saved records, and rechecks core health after its analytical checks.
- Staging deployment and live validation are pending. Production is not promoted.
