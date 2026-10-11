# Phase 26B.3 — bounded FEWS monthly client

`packages.data_sources.providers.fews_http_client` retrieves public Nigeria
market prices using the existing 26B.2 normalizer and Phase 26A `SourceSnapshot`.
It has no persistence or runtime registration side effects. Importing the module
does not make network requests. Wave 5 release loading and core readiness are
unchanged.

## Query and pagination

Every initial request includes `country_code=NG`, `schedule=Monthly`, a start
date, price type, page size, and an explicit allowlist of canonical source fields.
An end date is optional. Supply one `cpcv2` leaf code or hierarchical prefix.
CPCv2 takes precedence when `product` is also supplied; text fallback is used
only when explicitly supplied without CPCv2. Multiple-code encoding is not
assumed. The Nigeria restriction matches the existing adapter's source ID.

The client passes each server-provided `next` string unchanged to its HTTP
transport. It never calculates offsets and never treats `count`, a short page,
or an empty intermediate page as completion. Only `next: null` ends traversal.
Before each request it checks for cycles, the HTTPS FEWS market-price endpoint,
and unchanged monthly/date/commodity/country/price-type scope. Unsafe or changed
links fail rather than being rewritten. Both JSON endpoint spellings are allowed.

FEWS documents CPCv2 prefix matching, field selection, dates, and pagination in
the [API guide](https://help.fews.net/fdw/fews-net-api). The exact `schedule=Monthly`
value appears in [official release notes](https://help.fews.net/fdp/release-notes-for-data-sprint-21-09).

## Bounds and failure behavior

Defaults are 100 requested rows per page, 10 pages, 10 HTTP requests, 5,000
actual returned records, a 30-second socket timeout, and 5 MiB per response.
All limits must be positive; timeouts must also be finite. The socket timeout
is not a total traversal deadline. Page and request budgets are independent.
The transport performs no retries or automatic redirects, so each attempted
HTTP operation consumes one request. Redirects and non-200 statuses fail.

Page/request budgets are checked before another HTTP call. Returned row counts
are checked before normalization. Reaching a record limit with `next` still
present aborts without another call; a terminal page exactly at any limit
succeeds. Oversized responses, malformed JSON/envelopes/rows, out-of-scope rows,
non-finite numbers, HTTP failures, and pagination faults also abort. Errors are
typed as `FewsLimitError`, `FewsResponseError`, or `FewsHTTPError`, all under
`FewsClientError`. Invalid caller configuration raises `ValueError`.

No failed or truncated fetch returns partial records or a success snapshot.
The caller can explicitly narrow its query or choose different bounds for a
new fetch. A complete but empty traversal returns `records=()` and
`snapshot=None`: Phase 26A cannot express an unknown observation date range.

## Snapshot semantics

After a complete traversal and successful normalization, an injectable clock
supplies `retrieved_at`, normalized to UTC. `refreshed_at` is the same instant:
it means AgDA's successful local retrieval, not a provider publication time.
Observation bounds come from the earliest/latest actual `period_date`, at UTC
midnight. FEWS `modified` stays exclusively in each record's
`source_modified_at`, preserving the adapter's treatment of missing timezones.

`record_count` counts normalized records, not FEWS `count`. `dataset_version`
is `fews-monthly-v1:` plus a SHA-256 of the normalized ordered records and query
scope; it is independent of retrieval time and requested page size. It identifies
this query result, not an upstream FEWS release. Derived FEWS statistics are
neither requested nor included in canonical records or the content hash.

```python
from datetime import date
from packages.data_sources.providers.fews_http_client import (
    FewsMarketPriceClient, FewsMarketPriceQuery,
)

result = FewsMarketPriceClient().fetch(FewsMarketPriceQuery(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
    cpcv2="R01122AC",
))
```

## Deterministic checks and optional live probe

Run from the AgDA repository root in PowerShell:

```powershell
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\python.exe .\tests\integration\test_fews_market_price_client.py
.\.venv\Scripts\python.exe .\tests\integration\run_backend_regression.py
.\.venv\Scripts\python.exe .\tests\qa\run_user_qa.py
```

The backend suite now includes both 26B.2 adapter and 26B.3 client scripts (28
scripts total). Client tests inject responses and time; transport tests mock the
HTTP opener. They never depend on live FEWS availability.

The separate manual probe makes no network request unless `--live` is present:

```powershell
.\.venv\Scripts\python.exe .\tools\probe_fews_market_prices.py --live
```

It requests January 2025 white-maize retail prices, explicitly monthly, with at
most 3 pages, 3 requests, and 300 records. It prints a summary, snapshot, and one
record; it writes nothing. `--help` lists date, CPCv2, and bound overrides. Exit
code 2 means failure or a safety limit, not a successful partial ingestion. Live
provider availability is intentionally excluded from the automated regression.

## Phase 26B.3 validation checkpoint

Automated checks passed: 34 deterministic client tests, all 28 backend regression
scripts, and all 23 user QA cases. The backend suite was run with UTF-8 output
enabled because an existing test prints a character unsupported by Windows'
default output encoding. SHA-256 checks confirmed that all 50 protected Wave 5
and existing Phase 26A/26B.2 files retained their original contents.

The project owner reported a successful manual live probe retrieved at
`2026-10-10T01:43:41.208041+00:00`: one request, one page, and 16 monthly records
for January 2025 white-maize retail prices (`R01122AC`). The observed range was
`2025-01-31` to `2025-01-31`; both snapshot refresh and retrieval timestamps used
the actual retrieval time. The first record retained FEWS modification metadata
`2026-07-21T23:02:24` separately. The source-document title contains
`Price (weekly)`; it remains attribution metadata and does not override the
explicit `schedule=Monthly` query.

The reported dataset version was
`fews-monthly-v1:5143e47369d25bdfea54bcc2ce7188943f92aac4e94a8b4e24ac3efad7ff2946`.
This live result validates the provider connection for that query and time;
pagination and failure paths are covered by the deterministic tests.
