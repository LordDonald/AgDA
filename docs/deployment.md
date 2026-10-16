# Deployment and operations guide

This guide explains AgDA's deployment model and the last recorded hosted setup.
It is based on repository configuration, the October 15, 2026 Phase 29 freeze,
and the October 16, 2026 UTC preservation record and Redis follow-up. The dated
Redis inspection does not establish current hosted topology, service
availability, or provider-plan conditions.

Read the [architecture guide](architecture.md) for request and storage flows,
the [environment contract](environment_contract.md) for the complete variable
tables, and [local development](local_development.md) for local setup commands.
The [Phase 29 closure record](phase29_closure.md) and its
[environment freeze](evidence/phase29_environment_freeze.json) are the canonical
deployment, source-verification, and historical validation evidence.

## Services and deployment inputs

AgDA runs a Python FastAPI backend and a separate Next.js web application. The
API loads the immutable Wave5 release from the repository and restores optional
external snapshots from its persistent storage. The Next.js server proxies
browser requests to the API; the browser does not receive storage credentials.
Refresh schedulers call a privileged API endpoint instead of mounting its files.

The API application entry point is `apps.api.app.main:app`. The web application
is under `apps/web/`, with its own dependency lockfile and build/start scripts.
The tracked [CI workflow](../.github/workflows/ci.yml) checks the backend and
builds/lints the frontend. It contains no deployment job. Hosting-platform
service settings are not fully reproduced by tracked infrastructure manifests;
cloning the repository alone does not recreate the hosted environment.

## Last recorded hosted topology

Railway hosts the application services and API volumes in separate staging and
production environments. The providers below combine the Phase 29 freeze with
the later [preservation record](hosted_data_preservation.md), which identifies
production Upstash and both Neon preservation targets.

| Responsibility | Staging | Production |
| --- | --- | --- |
| API service | `api-staging` | `api` |
| Web service | `web` | `web` |
| Private API target for web and schedulers | `api-staging.railway.internal` | `api.railway.internal` |
| Conversation persistence | Dedicated Render Key Value Redis | Upstash Redis |
| Analytics and feedback | Separate staging Neon PostgreSQL database | Production Neon PostgreSQL database |
| FEWS/weather snapshots | Staging API-owned `/data/external` volume | Production API-owned `/data/external` volume |
| Recorded refresh jobs | Weather | Weather and FEWS |

Private targets describe server-to-server routing; they do not establish that
the API has no public endpoint. Each environment needs its own correct API
target, accepted hosts, credentials, and storage destinations.

The API is the sole owner of its environment's external volume. Web and refresh
schedulers do not mount that volume. The captured databases are
`fews_ng_white_maize_2025_01.sqlite3` and `weather_aba_forecast.sqlite3`, kept
outside immutable `data/releases/`. Replacing an API deployment must preserve
its volume and configured snapshot paths.

Staging and production analytics must use separate databases: analytics rows
have no environment discriminator. Conversation storage also requires verified
environment isolation. Do not infer safe isolation from a service name alone.

The freeze records staging Render access over TLS with authentication and an
external allowlist of `0.0.0.0/0`, attributed to Railway's dynamic egress at that
time. This is a recorded staging limitation, not a recommended default. The
Phase 29 persistence proof establishes survival across API replacement; it does
not establish durability through a Redis provider restart.

## Scheduled refresh and snapshot health

| Recorded job | Schedule | Recorded service name |
| --- | --- | --- |
| Production weather | `0 */4 * * *` — every four hours | `agda-weather-refresh-prod` |
| Production FEWS | `30 3 1 * *` — first day of each month at 03:30 UTC | `agda-weather-refresh` |
| Staging weather | `0 */4 * * *` — every four hours | `agda-weather-refresh` |

The production FEWS job retains a historical weather-related service name.
Identify it by its environment, configured source/target, and schedule. No
staging FEWS scheduler is listed in the recorded freeze.

Schedulers use [trigger_external_refresh.py](../tools/trigger_external_refresh.py)
with their own environment's refresh URL and matching operations token. The API
retrieves provider data, persists a completed snapshot, and updates its loaded
source state. This is a write operation with provider network access. Startup
restoration and explicit reload instead read local snapshots without a provider
fetch. See the [environment contract](environment_contract.md) for those settings.

`/v1/ready` reports core readiness; `/v1/sources` reports external availability,
freshness, and restoration state. External degradation does not determine
Wave5 readiness. The freeze recorded core readiness with degraded external
health in both environments, which is consistent with that separation.
Retrieval age, market observation dates, and forecast-valid hours are different
time concepts; a scheduled refresh does not make historical observations recent.

## Configuration and access boundaries

Use the environment contract as the authoritative configuration reference.
Hosted API documentation was disabled in the freeze. Accepted Host values must
match the intended environment, and the supported browser route is through the
Next.js proxy rather than direct cross-origin browser calls to FastAPI.

API services hold Redis/database connection secrets and API role tokens. Web
holds its API target, backend analytics token, and separate dashboard token.
Schedulers hold their API refresh URL and operations token. Web and schedulers
do not need each other's storage credentials. Backend analytics and operations
tokens must match their intended callers within one environment; equivalent
roles must differ across environments. Dashboard authentication uses its own
token. Keep secrets out of public frontend settings, source, and evidence.

## Source identity and manual production promotion

The last independently source-verified staging and production runtime is
`722e6d5b00b6f97d798d64cb568651bcbc35052e`. The later closure merge is
`b8e21b75d7e8604ac3f7c54fbdcabe335d7a7a03`; it records documentation,
configuration examples, operational tools, and tests. A passing CI run on that
closure merge does not establish that it replaced the hosted runtime.

The freeze records blank repository sources for production API, web, and both
schedulers. Staging API and weather scheduler also had blank sources; staging
web retained a `LordDonald/AgDA` repository connection. Therefore, the absence
of deployment jobs in CI does not prove that every hosting service has
repository-driven deployment disabled. Production manual-promotion safeguards
must be checked separately from CI and staging settings.

A future release should follow the established sequence:

1. Review and merge the intended revision; confirm its CI checks and exact SHA.
2. Prepare a clean checkout at that SHA. Keep generated release probes and
   uncommitted local changes out of the runtime upload.
3. Validate API and web in staging, including source identity, core invariants,
   external provenance, browser behavior, and relevant persistence contracts.
4. Promote the same verified revision manually to production. Keep production
   repository sources blank and preserve existing schedules and volume ownership.
5. Recheck source identity, environment targets, secrets by role, core readiness,
   and source provenance. Record deployment IDs and bounded evidence in the
   release record without recording credential values.

Core invariants are `wave5_v1`, release state `stable`, metric version `1.0.0`,
and 18 registered metrics. Deployment messages and the API service-version
setting alone are not source proof. The Phase 29 probes matched tracked source
and release-data bytes; they did not attest generated web build assets or all
extra files. A retained-source staging redeploy failed source verification during
closure, so the source probe remains necessary even for a same-release redeploy.

## Operational evidence and recovery boundaries

Operational tools have different effects. Review their scope before any future
run; a tool named validation or proof is not necessarily read-only:

| Tool or activity | Relevant effects and limits |
| --- | --- |
| [Release probe builder](../tools/build_release_probe.py) | Requires exact clean source and writes generated probes outside the checkout; probes inspect deployed files, not full platform state. |
| Readiness and health (`/v1/ready`, `/v1/health`) | With Redis conversations configured, counting conversations can prune expired index members. These endpoints are not strictly read-only Redis inventory checks. |
| [Release validator](../tools/validate_phase29_release.py) | Checks an explicit environment before analytical POSTs; questions can write conversation/analytics records even though it avoids provider refreshes. |
| [Staging persistence proof](../tools/validate_phase29_persistence.py) | Creates synthetic questions/feedback through application routes; direct store access is read-only. It neither performs the redeploy nor bootstraps schemas. |
| Refresh, reload, or schema initialization | Refresh can fetch providers and write snapshots; reload changes in-memory state; schema initialization changes a database. |

The [preservation record](hosted_data_preservation.md) reports six sets captured
on October 16, 2026 UTC that passed the capture's artifact checks. It excludes
the incomplete Upstash attempt.
It preserves two named SQLite databases per environment, logical PostgreSQL
exports rather than native `pg_dump` archives, and per-key Redis exports rather
than RDB images. It is not a simultaneous snapshot of all services.

The production capture selected `agda:conversation:*`; the source-verified
runtime uses `agda:production:conversation:*`. A read-only follow-up on October
16, 2026, at 04:00:38-04:00:43 UTC found no matching runtime keys on two complete
scans and no index. This later observation does not establish coverage at the
original capture time or prove data loss. Staging's native export included two
runtime-prefixed string keys and their index despite its classifier reporting
zero conversations. See the preservation record and its sanitized evidence for
these findings and their limits.

Preservation verification is separate from an end-to-end restore drill. Future
recovery needs an isolated destination, artifact-integrity checks, environment
separation, and an explicit treatment of captured Redis TTLs. A runtime rollback
also does not automatically roll back database contents or external snapshots.
Keep the source preservation files unchanged and outside Git. This guide contains
no deployment, configuration mutation, resource deletion, or restore procedure.
