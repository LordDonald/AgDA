# AgDA Environment Contract

This document describes configuration behavior and deployment requirements.
The [Phase 29 closure record](phase29_closure.md) records the actual configuration,
deployment revisions, and validation results. A setting listed here does not
establish that its service has been provisioned or its validation has passed.

See the [architecture guide](architecture.md) for component and storage
responsibilities, the [deployment guide](deployment.md) for the last recorded
hosted topology and manual promotion process, and the
[hosted-data preservation record](hosted_data_preservation.md) for capture scope
and recovery limitations. For local configuration, use the
[local-development guide](local_development.md).

## Backend settings

| Variable | Runtime default | Meaning and deployment requirement |
| --- | --- | --- |
| `AGDA_ENV` | `development` | One of `development`, `test`, `staging`, or `production`. Set the actual environment explicitly. |
| `AGDA_LOG_LEVEL` | `WARNING` in production; `INFO` otherwise | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. Structured product and external-refresh events have their own logging configuration. |
| `AGDA_MAX_CONVERSATIONS` | `500` | Positive conversation-store capacity limit. |
| `AGDA_MAX_REQUEST_BYTES` | `16384` | Positive maximum HTTP request-body size in bytes. |
| `AGDA_DOCS_ENABLED` | `false` in production; `true` otherwise | Controls Swagger, ReDoc, and OpenAPI routes. Keep `false` in production. |
| `AGDA_ALLOWED_HOSTS` | `*` in development/test; `localhost,127.0.0.1` in staging/production | Comma-separated accepted Host values. Configure the actual service hostnames in hosted environments; never assume the default permits Railway traffic. |
| `AGDA_SERVICE_NAME` | `AgDA API` | Service metadata. |
| `AGDA_SERVICE_VERSION` | `0.1.0` | Service metadata; this value is not proof of the deployed Git revision. |
| `AGDA_CONVERSATION_BACKEND` | `memory` | One of `memory` or `redis`. Selecting `redis` requires a nonblank `AGDA_REDIS_URL`. |
| `AGDA_CONVERSATION_TTL_SECONDS` | `86400` | Positive retention period used by the Redis conversation store. |
| `AGDA_REDIS_URL` | Unset | Secret connection URL for the selected environment's Redis service. Unused by the memory backend. |
| `AGDA_ANALYTICS_DATABASE_URL` | Unset | Secret PostgreSQL connection URL. Unset/blank disables analytics persistence. The database must have the application's analytics schema. |
| `AGDA_INTERNAL_ANALYTICS_TOKEN` | Unset | Secret for reading internal analytics. Both this token and the analytics database URL must be configured; otherwise internal analytics returns 503. Missing or incorrect caller tokens return 401 when configured. |
| `AGDA_OPERATIONS_TOKEN` | Unset | Secret for internal external-source refresh/reload operations. Unset/blank disables these endpoints with 503; missing or incorrect caller tokens return 401 when configured. |

The example environment file contains explicit development values. Copying it
does not apply the production defaults above; review every hosted setting.
Real environment files and credential values must never be committed.

The API runtime sets the Redis prefix to `agda:{environment}:conversation`,
using `AGDA_ENV`. Production keys therefore begin with
`agda:production:conversation:` and staging keys with
`agda:staging:conversation:`; each namespace has its own `index` key. This
overrides the store constructor's unqualified default prefix. The Redis store
connects and pings during startup, so selecting Redis creates a runtime availability
dependency. Validate connectivity, conversation continuity after restart, TTL,
and environment isolation before accepting the restoration. The memory backend
loses conversations on restart and does not share them across instances.

Analytics persistence is optional and fails open: database failures are logged
without connection details and must not break question responses. Analytics
tables do not partition records by environment. **Staging and production must
use separate analytics databases**, even when their schemas are identical.
Restoring staging persistence must not point staging at production records.

## Frontend settings and server boundary

| Variable | Default | Meaning and deployment requirement |
| --- | --- | --- |
| `AGDA_API_URL` | `http://127.0.0.1:8000` outside `NODE_ENV=production`; required in production mode | Absolute HTTP(S) FastAPI base URL used by the Next.js server. Hosted staging also runs the production frontend build and must configure this value. |
| `AGDA_INTERNAL_ANALYTICS_TOKEN` | Unset | Server-side token forwarded to the API analytics route. It must match the API token in the same environment. A valid dashboard request receives 503 if this server token is missing. |
| `AGDA_INTERNAL_DASHBOARD_TOKEN` | Unset | Secret used to authenticate an operator to the web analytics proxy. Unset, missing, or incorrect tokens return 401. Use a different value from the backend analytics and operations tokens. |

Browser -> Next.js `/api/*` -> FastAPI.

None of these settings belongs in `NEXT_PUBLIC_*` or a Next.js `env` export.
The configured analytics backend token stays in the server route. The operator
enters the separate dashboard token in the dashboard; the page sends it in the
dashboard header and holds it in component state, not local storage. Proxied
analytics responses use `Cache-Control: no-store`.

FastAPI uses `TrustedHostMiddleware`. Configure explicit accepted hostnames for
staging and production and avoid `*`. CORS is intentionally not enabled because
the supported browser path uses the Next.js proxy. Use the deployment platform's
protected network paths and HTTPS entry point for hosted access.

## Secrets and environment isolation

Redis and analytics URLs may contain credentials. Operations, backend analytics,
and dashboard tokens are secrets. FEWS and Open-Meteo currently require no
provider API keys, which does not make the application secret-free.

- Store real values in the deployment platform's environment-specific secret
  configuration. Commit only blank examples and nonsecret defaults.
- Use dedicated staging Redis resources and a separate staging analytics
  database. Do not reuse production credential references to restore staging.
- Keep tokens distinct between staging and production and between their roles.
  Within one environment, the API and its refresh schedulers must share the
  operations token; the API and web must share the backend analytics token.
  The dashboard token remains a separate credential.
- Give API services only the credentials they use. Web needs its API base URL
  and analytics/dashboard tokens; it does not need Redis, database, or
  operations credentials. Refresh schedulers need their own environment's
  operations token and refresh URL, not analytics or Redis credentials.
- Never print credential values, request authentication headers, or credential
  URLs in logs, validation output, screenshots, or closure evidence. Record
  presence, role, environment ownership, and equality checks instead.
- Rotate affected credentials if exposure is confirmed; a repository pattern
  scan cannot prove that a credential has never been exposed elsewhere.

## Optional external snapshot restoration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AGDA_FEWS_SNAPSHOT_PATH` | Unset | Loads a completed FEWS market-price snapshot at startup. Use an absolute persistent path outside `data/releases/`. |
| `AGDA_FEWS_STALE_AFTER_HOURS` | `48` | Positive local retrieval-age threshold; independent of observation dates and FEWS publication cadence. |
| `AGDA_WEATHER_SNAPSHOT_PATH` | Unset | Loads a completed Open-Meteo weather snapshot at startup. Use an absolute persistent path outside `data/releases/`. |
| `AGDA_WEATHER_STALE_AFTER_HOURS` | `6` | Positive local retrieval-age threshold; independent of forecast-valid time, accuracy, and model issue age. |

Blank paths disable restoration for that source. Startup and explicit reload
read local storage only; neither fetches provider data. Missing, unreadable, or
stale external snapshots are reported through source health and do not determine
core Wave5 readiness. `/v1/ready` remains authoritative for the core analytical
service; `/v1/sources` reports availability, freshness, and restoration state.

External storage must survive API restarts and redeployments. Preserve the
API-only `/data/external` mount; web and refresh schedulers do not mount it.
Keep the stores outside immutable `data/releases/`. External results retain
their own source, snapshot, query, and time provenance and are never silently
joined to or labeled as `wave5_v1` data.

See [FEWS snapshot persistence](fews_snapshot_persistence.md) for ingestion and
restoration commands. The Phase 29 record supplies hosted verification evidence.

## Operational tooling settings

These settings are consumed by operational commands, not the API settings
loader. They do not cause automatic refresh on application startup.

| Variable | Default | Meaning |
| --- | --- | --- |
| `AGDA_OPERATIONS_REFRESH_URL` | Unset | Full absolute HTTP(S) refresh endpoint for `tools/trigger_external_refresh.py`; `--refresh-url` overrides it. Required when that command is used without the argument. |
| `AGDA_OPERATIONS_RELOAD_URL` | Unset | Full absolute HTTP(S) reload endpoint for `tools/refresh_and_reload_external_source.py`; `--reload-url` overrides it. Required when that command is used without the argument. |

Both commands require a nonblank `AGDA_OPERATIONS_TOKEN`. Point every command at
the API in its own environment. Production scheduled refresh keeps the existing
weather schedule `0 */4 * * *` and FEWS schedule `30 3 1 * *`.

## Manual production deployment safeguards

Production API and web repository sources must remain blank, keeping GitHub
auto-deployment disabled. No CI workflow may silently promote production.
Validate a merged Git SHA in staging before manually deploying that exact SHA
to production; record the SHA and resulting deployment IDs in the closure record.
Recheck repository sources, schedules, volume ownership, core release identity,
and source provenance after deployment. Preserve `wave5_v1`, stable release
state, metric version `1.0.0`, and the 18 core metrics throughout.
