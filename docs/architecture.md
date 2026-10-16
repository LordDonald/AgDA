# Architecture

AgDA combines a deterministic agricultural analytics core with separately
attributed external snapshots. A Next.js application provides the interface and
server-side proxy; FastAPI owns routing, analytical execution and persistence.
The current request path has no integrated LLM runtime or LLM service dependency.

Use the [local-development guide](local_development.md) to run the application,
the [deployment guide](deployment.md) for service topology and operations, and
the [environment contract](environment_contract.md) for configuration defaults
and requirements. The [Phase 29 record](phase29_closure.md) contains dated hosted
validation evidence; this architecture description does not assert live health.

## Components and responsibilities

| Component | Responsibility |
| --- | --- |
| [Next.js web](../apps/web/src/app) | Question interface, answer rendering, feedback controls and internal dashboard |
| [Web server routes](../apps/web/src/app/api) | Same-origin browser requests forwarded to the configured FastAPI service |
| [FastAPI application](../apps/api/app/main.py) | Startup/shutdown, public and internal routes, request limits and host validation |
| [Application runtime](../apps/api/app/core/runtime.py) | Process-scoped release connection, routers, executors, conversation store and accepted external snapshots |
| [Question routing](../packages/question_router) | Deterministic interpretation, supported metric/selection resolution and contextual follow-ups |
| [Analytics](../packages/analytics) | Registered core metrics and execution of approved question specifications |
| [Answering](../packages/answering) | Answer composition, evidence, cautions, visual recommendations and conversation storage |
| [Data release](../packages/data_release) | Resolve and validate the stable release; expose its Parquet artifacts through DuckDB |
| [External sources](../packages/data_sources) | Provider contracts, ingestion, snapshot storage, provenance and separate external query execution |
| [Contracts](../packages/contracts) | Structured core question, answer, feedback and internal analytics models |

## Question and answer flow

1. The browser sends a question to Next.js `POST /api/questions`. The server
   forwards it to FastAPI `POST /v1/questions`; backend addresses and credentials
   stay in server configuration. See the [web README](../apps/web/README.md) for
   proxy routes and dashboard authentication.
2. The API requires a ready runtime, obtains or creates a conversation ID, and
   reads any saved analytical context. The separate external router then checks
   whether the question belongs to a supported external measure. Mixed or
   ambiguous external requests can require reframing.
3. A routed external question runs against the accepted FEWS or weather snapshot
   already held by the process. Other questions enter the core pipeline, where
   the contextual resolver can use the last successful analytical interpretation
   before ordinary routing produces a question specification.
4. Only an interpreted core specification executes. Unsupported or ambiguous
   requests return an explanatory status instead of an invented calculation.
   Approved specifications use the metric registry and DuckDB-backed executor.
5. The answer service constructs core answer text, structured results, evidence,
   cautions and any recommended visualization. Core answers carry data and metric
   versions. External answers carry their own source/snapshot provenance and do
   not claim the core release's metric version.
6. Successful core interpretations update conversation context. Question-event
   telemetry is logged, and optional PostgreSQL persistence runs as a background
   task. The browser receives the answer and conversation ID for later follow-ups.

The [question route](../apps/api/app/routes/questions.py),
[pipeline](../packages/answering/pipeline.py) and
[answer service](../packages/answering/service.py) define this behavior. External
answers do not update the stored core analytical interpretation; conversation
storage is not a general transcript or an external-source reasoning memory.

## Core analytical release

The stable pointer selects `wave5_v1`, with metric version `1.0.0` and 18 core
metrics. The [release manifest](../data/releases/wave5_v1/release_manifest.json)
describes its artifacts; [Phase 29](phase29_closure.md) records the metric count
and validation results. The release covers registered Nigerian Wave 5 survey
metrics, including crop prevalence, observed yields, commercialization, food
security and community climate-risk perceptions.

At startup, the [loader](../packages/data_release/loader.py) resolves the stable
pointer and validates the manifest, artifact sizes and SHA-256 checksums. It
opens an in-memory DuckDB connection and registers views over the bundled
Parquet files. The release files remain the analytical source; Redis and
PostgreSQL do not supply the core survey tables. A missing or invalid release
prevents successful startup.

## External snapshots and refresh

FEWS market observations and Open-Meteo forecasts have separate source and metric
registries. They are not joined into Wave 5 or counted among its core metrics.
FEWS queries are bounded to saved Nigerian white-maize retail observations in
NGN/kg. Weather queries are bounded to saved hourly temperature, relative
humidity and precipitation forecasts at the captured requested coordinates.

Configured SQLite stores persist validated external snapshots. Startup restores
accepted snapshots into process memory without contacting providers. Public
question, coverage and explicit-query routes read those accepted objects without
fetching providers or reading/writing the snapshot store during the query.

`GET /v1/sources` reports source metadata and freshness;
`GET /v1/market-prices` and `GET /v1/weather-forecast` expose available records and
coverage. `POST /v1/external-queries` accepts exact selectors and optional
snapshot pinning. Each request captures a snapshot so rows and provenance stay
consistent if a refresh replaces the process's active reference. A mismatched
pin returns 409. See the [external query contract](phase28_external_capabilities.md)
and [route implementation](../apps/api/app/routes/external_queries.py).

The separate [internal operations routes](../apps/api/app/routes/internal_external_sources.py)
require the operations token:

- `POST /v1/internal/external-sources/refresh` uses a bounded provider query,
  validates and persists its result, then attempts adoption by the API runtime.
- `POST /v1/internal/external-sources/reload` adopts already stored snapshots
  without provider calls. It can reload one source or both.

Refresh outcomes distinguish a new/unchanged snapshot, no data, provider/storage
failure and adoption failure. Failed or empty ingestion retains the previous
stored snapshot when one exists. Runtime restore failures retain existing source
state. The [refresh implementation](../packages/data_sources/external_refresh.py)
enforces preservation of the last accepted stored snapshot; deployment scheduling
and service ownership are described in the [deployment guide](deployment.md).

Accepted snapshots and the operations lock are process-scoped. A reload adopts
data in the API process handling it; it is not a broadcast to every replica.
Durable SQLite storage and runtime adoption are separate states to verify.

## State and persistence

| State | Store and lifetime | Boundary |
| --- | --- | --- |
| Core release | Bundled versioned Parquet and manifests; in-memory DuckDB views | Validated at startup; independent of external refreshes |
| Conversation context | Memory by default, or Redis with sliding TTL and capacity pruning | Stores the last interpreted core question; Redis shares it across API processes and survives process restarts |
| External snapshots | Separate FEWS/weather SQLite stores and accepted in-memory objects | Durable storage survives only when its filesystem is preserved; adoption updates each process separately |
| Product events | Structured logs and optional PostgreSQL `product_events` | Background persistence failures do not fail the question response |
| Feedback | PostgreSQL `product_feedback`, linked to a recorded question event | Explicit save operation reports unavailable storage or unknown answers |

The [runtime](../apps/api/app/core/runtime.py) configures the
[conversation store](../packages/answering/conversations.py) with
`agda:{environment}:conversation`, producing separate production and staging
key prefixes. Closing the Redis client does not
clear shared conversations. Memory context is lost on process restart and is
not shared between replicas. Analytics tables do not partition by environment;
staging and production therefore require separate databases.

Question [telemetry](../apps/api/app/core/product_analytics.py) excludes raw
question/answer text, filters, entities and conversation IDs. Its fail-open
behavior means a successful answer does not prove its analytics event was saved.
[Feedback](../apps/api/app/routes/feedback.py) returns 503 if storage is absent or
fails, and 404 when the associated answer event is missing. The authenticated
internal dashboard reads aggregate analytics through the web server proxy.

The [preservation record](hosted_data_preservation.md) inventories six sets with
reported passing artifact checks, the historical production Redis coverage
limitation and a later empty-namespace observation. These artifacts are separate
from the bundled release; artifact checks and later observations do not establish
complete capture-time coverage or a completed restore.

## Readiness and analytical boundaries

`GET /v1/live` reports process liveness. `GET /v1/ready` and its `/v1/health` alias
report runtime readiness, release information and external-source health.
Optional external snapshot availability does not determine core readiness:
missing or corrupt external storage can make an external capability unavailable
while core Wave 5 questions remain usable.

Redis behaves differently when selected as the conversation backend: startup
pings it and fails if it cannot connect. Later conversation operations and the
conversation count used by readiness also access Redis; there is no automatic
fallback to memory. That count can prune expired Redis index members, so
`/v1/ready` and `/v1/health` are not strictly read-only Redis probes.
PostgreSQL analytics is optional and fail-open, so readiness
does not certify feedback/dashboard availability. See the
[runtime](../apps/api/app/core/runtime.py) and
[health routes](../apps/api/app/routes/health.py) for these distinctions.

Answers describe available evidence within supported metrics and selections.
Observed yields do not establish agronomic potential; descriptive comparisons
do not establish causation or complete profitability. Community climate-risk
perceptions, observed market prices and forecast weather have different time
and evidence meanings. Retrieval freshness does not establish recent market
observations or forecast accuracy. Stale accepted external snapshots remain
queryable with their freshness metadata; missing forecast hours are disclosed,
and out-of-coverage requests do not silently expand or truncate saved coverage.
