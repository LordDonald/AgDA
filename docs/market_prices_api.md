# Phase 26B.5 — Read-only market-price API

`GET /v1/market-prices` returns canonical observations from the validated FEWS
snapshot loaded at API startup. Requests read the in-memory snapshot and perform
no filesystem reads, writes, or provider HTTP requests. Configure and populate
the local store as described in [snapshot persistence](fews_snapshot_persistence.md).
This remains a local market-price pilot; it does not add question routing or a
public web interface.

## Inspect the pilot

With the API running on port 8000:

```powershell
$page = Invoke-RestMethod 'http://127.0.0.1:8000/v1/market-prices?limit=5'
$page | ConvertTo-Json -Depth 8
Invoke-RestMethod 'http://127.0.0.1:8000/v1/market-prices?market=Aba&start_date=2025-01-01&end_date=2025-01-31'
```

Restart the API after installing this route. After a separate ingestion process
saves newer data, restart the API or call the existing local runtime reload method
to make that data visible. There is no public refresh or ingestion route.

## Request and response contract

| Parameter | Meaning |
| --- | --- |
| `limit` | Page size, default 50, minimum 1, maximum 200. |
| `offset` | Position in the filtered saved records, default 0, minimum 0. |
| `snapshot_id` | Optional 64-character lowercase hexadecimal ID from an earlier page. A different active snapshot returns 409. |
| `admin_1`, `market`, `cpcv2` | Exact matches ignoring case and surrounding whitespace. CPCv2 here is an exact code, even when ingestion used a code prefix. |
| `start_date`, `end_date` | Inclusive observation dates in `YYYY-MM-DD` format. Either bound can be omitted. |

Blank text filters, invalid dates, reversed date bounds, invalid snapshot IDs,
and out-of-range pagination parameters return 422. Filters narrow saved data;
they never trigger a broader retrieval. A valid query with no matches returns
200 with an empty `records` list.

The response contains:

- `snapshot_id`: the identity of this complete persisted retrieval, including its
  retrieval time. Re-fetching identical content can change this ID while retaining
  `source.dataset_version`.
- `source`: the existing Phase 26A source manifest plus the effective ingestion
  `query`. It includes attribution, coverage notes, freshness, observation bounds,
  retrieval time, and the full snapshot's `record_count`.
- `snapshot_restore_status`: `loaded`, or `missing`/`error` if serving a previously
  accepted snapshot after a failed reload.
- `filters`: the supplied filters with whitespace trimmed and dates in ISO format.
- `total`: the number of records matching these filters, before pagination.
- `limit`, `offset`, `returned_count`, `next_offset`: the page boundaries and next
  local offset, or null when pagination is complete.
- `records`: canonical `MarketPriceRecord` fields. Prices and coordinates are
  decimal strings, optional values remain null, and dates/timestamps use ISO format.

Records retain their order within the saved snapshot. For subsequent pages,
reuse the returned `snapshot_id`, `next_offset`, and the same filters and limit:

```powershell
if ($null -ne $page.next_offset) {
    $nextUri = 'http://127.0.0.1:8000/v1/market-prices?limit=5&offset={0}&snapshot_id={1}' -f $page.next_offset, $page.snapshot_id
    $page = Invoke-RestMethod $nextUri
}
```

If the active snapshot changes, a pinned request returns 409 and the client must
restart pagination at offset 0 without the old ID. This route serves only the
active snapshot, not historical snapshots. Local offsets paginate an immutable
saved tuple; the FEWS HTTP client still follows provider `next` URLs verbatim.

## Coverage and availability

The default pilot covers Nigeria white-maize retail observations for January
2025. `source.query` states the actual saved coverage. A fresh retrieval of that
data remains historical data: `source.freshness` measures AgDA retrieval age, and
`period_date` describes the economic observation. FEWS `source_modified_at` stays
separate and retains its original timezone information, including no timezone.
The endpoint does not combine prices across currencies, units, markets, or dates.

Stale snapshots remain available with an explicit stale flag. Disabled, missing,
or corrupt storage with no previously accepted snapshot returns a sanitized 503
from this endpoint. Failed or older reloads preserve any accepted records and
their matching provenance. A registry snapshot that no longer matches the cached
records also makes this endpoint unavailable rather than mislabeling the records.
The existing `/v1/ready` contract and Wave 5 release remain independent of this
external-data availability.

## Verification and remaining roadmap

`tests/integration/test_market_prices_api.py` uses deterministic mocked FEWS
responses and temporary SQLite stores. It checks precision, filters, paging,
reload behavior, error responses, and isolation from request-time I/O. It is
included in the backend regression runner. No live probe is needed for these
checks; the already saved pilot can be inspected with the commands above.

The original AgDA MVP's production launch is recorded in
[production launch](production_launch.md). The agreed Phase 26 expansion proceeds
from this market-price pilot to 26C weather/forecast ingestion, 26D cross-source
metrics and question routing, 26E source/freshness UI, and 26F staging validation,
production rollout, and monitoring. These are milestone groups, not a fixed
count of implementation steps. Shared production storage and refresh operations
remain rollout work.
