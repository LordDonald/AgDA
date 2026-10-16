# Phase 26B.4 — FEWS snapshot persistence and registry integration

This is the Phase 26B.4 local persistence design and validation record. Its pilot
commands and phase boundaries predate the hosted refresh workflow. See
[architecture](architecture.md), [deployment](deployment.md) and the
[environment contract](environment_contract.md) for the later integrated system,
and [Phase 29](phase29_closure.md) for hosted validation.

Completed FEWS monthly results can be stored in a local SQLite database and
restored into the existing Phase 26A source registry. SQLite is provided by
Python; no new dependency or Wave 5 database connection is needed. The Phase 26A
contracts, registry, catalog, and core readiness rules are unchanged.

## Save and inspect a pilot retrieval

Run from the AgDA repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe .\tools\ingest_fews_market_prices.py --live
.\.venv\Scripts\python.exe .\tools\ingest_fews_market_prices.py --inspect
```

The default query is Nigeria white-maize retail prices for January 2025,
explicitly monthly. The default database is
`data/external/fews_ng_white_maize_2025_01.sqlite3`. Limits are 3 pages, 3 requests,
and 300 records; the existing client still enforces timeouts and response bounds.
The first command retrieves, validates, and saves; the second reads the saved
snapshot using a new store instance, with no HTTP. Running without an action
prints guidance and performs no I/O. `--help` lists date, code, path, and limit
options. Failure exits with code 2; empty data preserves the previous snapshot.

Every store is pinned to its first successful effective query. To change the
commodity, date range, or price type, choose a different `--database`. This keeps
a narrow query from silently replacing a different scope under the same FEWS
source ID. CPCv2 takes precedence over product text, and page size is not part of
query identity. The stored query is included in inspection output.

Local files under `data/external/` are ignored by Git. Store paths inside
`data/releases/`, including paths resolving there through a symlink, are rejected.

## Load saved provenance into the API

Set these variables in the environment of the API process before starting it:

```powershell
$env:AGDA_FEWS_SNAPSHOT_PATH = (Resolve-Path .\data\external\fews_ng_white_maize_2025_01.sqlite3).Path
$env:AGDA_FEWS_STALE_AFTER_HOURS = "48"
```

Then start or restart the API with the project's normal launch command.
`AGDA_FEWS_SNAPSHOT_PATH` is optional and blank by default. Relative paths resolve
against the process working directory; an absolute path avoids ambiguity.
`AGDA_FEWS_STALE_AFTER_HOURS` defaults to 48: this is an AgDA retrieval-age policy,
not a claim about FEWS publishing frequency or how recent the observations are.
Neither setting schedules a refresh or causes startup to fetch live data.

On startup, the API reads local storage and publishes the saved `SourceSnapshot`.
`/v1/sources` exposes the effective `query` alongside the existing FEWS provenance
fields. It exposes no database path or records. External health reports
`snapshot_restore_status` as `disabled`, `missing`, `loaded`, or `error`.
A configured missing or unreadable store leaves freshness unknown if no good
snapshot is already available. Reload failures preserve any prior good state.

`/v1/ready` and the stable `wave5_v1` release remain independent of stale or failed
external storage. API startup performs no HTTP, and normal requests read the
in-memory registry. After a separate ingestion process saves newer data, restart
the API or explicitly call its local `runtime.reload_fews_snapshot()` method.
Phase 26B.4 added no public refresh endpoint or background polling. Later
operations added authenticated internal refresh/reload endpoints; use the linked
architecture and deployment guides for that workflow.

## Durability and data semantics

The store uses an append-only table with one transaction per complete snapshot.
Each envelope contains a format version, effective query, snapshot metadata,
all canonical records, and request/page counters. Decimal values are stored as
strings; dates and timestamps use ISO notation. FEWS `source_modified_at` retains
its original timezone information, including a missing timezone.

The existing `fews-monthly-v1` content version remains unchanged. A separate
SHA-256 `snapshot_id` covers the whole stored envelope, including retrieval time.
Thus re-fetching unchanged content advances retrieval freshness while retaining
its content version. Replaying an identical retrieval is idempotent. Different
envelopes claiming the same retrieval instant are rejected as conflicts.

Only nonempty completed results can be saved. The store validates scope, record
count, observation bounds, UTC snapshot timestamps, canonical field types, and
the content version. Reads repeat those checks and verify envelope/index
integrity. Default maximum envelope size is 64 MiB. Missing-store reads create
nothing; corrupt storage fails explicitly and is never silently reset.

The registry is updated only after the durable transaction commits. Empty
results, client failures, and failed transactions preserve prior data and
freshness. Older retrievals can remain in history, but latest selection and
registry publication never move backwards in retrieval time. SQLite serializes
writers; registry compare-and-update is protected within this process. Separate
processes each maintain their own registry and must reload to see newer data.

The envelope hash detects accidental corruption; it is not an authenticity
signature against someone who can rewrite the database and its hashes.
History retention and shared production storage were outside this local pilot;
later API-owned volume deployment is recorded in the deployment and Phase 29
guides.

## Verification

```powershell
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\python.exe .\tests\integration\test_fews_snapshot_store.py
.\.venv\Scripts\python.exe .\tests\integration\test_fews_snapshot_runtime.py
.\.venv\Scripts\python.exe .\tests\integration\test_fews_ingestion_command.py
.\.venv\Scripts\python.exe .\tests\integration\run_backend_regression.py
.\.venv\Scripts\python.exe .\tests\qa\run_user_qa.py
```

Tests use temporary databases and deterministic mocked HTTP, including actual
transaction rollback, restart hydration, corrupt storage, monotonic updates,
query isolation, precision, and API readiness. At this checkpoint, the three
new scripts joined the existing 28-script backend suite. Live ingestion remains an explicit manual
action through the command above.
