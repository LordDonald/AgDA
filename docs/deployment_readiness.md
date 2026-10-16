# AgDA Deployment Readiness

> Historical MVP preparation record, first committed September 15, 2026; later
> external-snapshot rollout notes are retained below. The versions, smoke-test
> results, memory-only limitation and remaining launch work describe those
> milestones. They are not a current deployment checklist.
>
> Use [local development](local_development.md) for setup, the
> [environment contract](environment_contract.md) for configuration and the
> [deployment guide](deployment.md) for the last recorded hosted topology and
> operational boundaries. Later release and persistence validation is recorded in
> [Phase 29](phase29_closure.md); these records do not establish live availability.

## Original preparation status

AgDA has completed local production-environment preparation and production-mode
smoke testing.

This document defines the application artifacts required for deployment before
a hosting platform is selected.

---

## 1. Backend Runtime

Tested runtime:

- Python 3.12.7
- FastAPI 0.141.1
- Uvicorn 0.52.4
- DuckDB 1.5.5
- Pandas 2.2.2
- Pydantic 2.11.7
- PyArrow 16.1.0

Production dependency lock:

`requirements-production.txt`

The project also retains `pyproject.toml` as its Python package definition.

---

## 2. Frontend Runtime

Frontend:

- Next.js 16.3.4
- React 19.2.8
- React DOM 19.2.8
- TypeScript
- npm dependency lock via `apps/web/package-lock.json`

Production build command:

`npm run build`

Production start command:

`npm run start`

---

## 3. Runtime Data Release

The production application reads from:

`data/releases/`

The stable release recorded for this milestone was:

- Data version: `wave5_v1`
- Release state: `stable`
- Metric version: `1.0.0`
- Registered metrics: `18`

Recorded runtime release footprint:

- 43 files
- approximately 3.72 MB

The runtime loader resolves the stable release through:

`data/releases/stable_release.json`

and validates the release manifest and checksums during startup.

---

## 4. Development Data Exclusion

The `03_data/` directory contains development, inventory, QA, and release-building
artifacts.

It is not required by the normal application runtime.

Production deployment should package the validated `data/releases/` artifacts
rather than the full `03_data/` workspace.

Release-building utilities may still depend on `03_data/`, but those utilities
are not part of the normal production request path.

---

## 5. Backend Environment

Recommended production values:

- `AGDA_ENV=production`
- `AGDA_LOG_LEVEL=WARNING`
- `AGDA_DOCS_ENABLED=false`
- `AGDA_MAX_REQUEST_BYTES=16384`
- `AGDA_ALLOWED_HOSTS=<deployment hostname>`
- `AGDA_SERVICE_NAME=AgDA API`
- `AGDA_SERVICE_VERSION=0.1.0`

Optional external-data runtime values when those sources are enabled:

- `AGDA_FEWS_SNAPSHOT_PATH=<persistent absolute path>`
- `AGDA_FEWS_STALE_AFTER_HOURS=48`
- `AGDA_WEATHER_SNAPSHOT_PATH=<persistent absolute path>`
- `AGDA_WEATHER_STALE_AFTER_HOURS=6`

Real environment files and secrets must not be committed.

---

## 6. Frontend Environment

Required in production:

`AGDA_API_URL=<FastAPI service URL>`

`AGDA_API_URL` remains server-side.

The browser communicates with the Next.js application, and Next.js proxies
requests to FastAPI.

Architecture:

Browser -> Next.js `/api/*` -> FastAPI

---

## 7. API Security Boundary

FastAPI uses TrustedHostMiddleware.

Production hosts must be explicitly configured using `AGDA_ALLOWED_HOSTS`.

Interactive API documentation and OpenAPI output are disabled in production.

CORS is not enabled because the browser does not directly communicate with
FastAPI in the current architecture.

---

## 8. Production Startup

Backend development-equivalent production command:

`python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000`

The final port and process command may be adapted to the selected hosting
platform.

Frontend:

`npm run build`

then:

`npm run start`

The final deployment platform may supply its own port automatically.

---

## 9. Local Production Smoke Test

The following behavior has been validated:

- FastAPI production startup
- `/v1/live` returned HTTP 200
- environment reported `production`
- `/docs` returned HTTP 404
- `/openapi.json` returned HTTP 404
- Next.js `/api/health` successfully reached FastAPI
- runtime loaded `wave5_v1`
- release state reported `stable`
- all 18 registered metrics loaded
- question submission through Next.js succeeded
- browser question submission succeeded
- conversational follow-up succeeded

Example production smoke question:

`What are farmers mostly growing in Kaduna?`

The system returned the validated Kaduna crop-grower ranking.

---

## 10. Original Runtime State Limitation

At this milestone, conversation context was stored in process memory.

Later releases added Redis persistence; see the current
[architecture](architecture.md#state-and-persistence) and dated
[Phase 29 persistence proof](phase29_closure.md#staging-persistence-live-proof-completed).
The limitations below describe the original memory-backed deployment.

Consequences:

- conversation state is lost when the backend process restarts;
- multiple backend instances would not automatically share conversation state;
- horizontal scaling requires shared conversation persistence in a future
  architecture.

For the initial single-instance MVP deployment, this is an accepted limitation.

---

## 11. Deployment Package

Required:

- `apps/api/`
- `apps/web/`
- `packages/`
- `data/releases/`
- `pyproject.toml`
- `requirements-production.txt`
- frontend `package.json`
- frontend `package-lock.json`
- required documentation/configuration

Not required for normal production runtime:

- `03_data/`
- Jupyter checkpoints
- `node_modules/`
- `.next/` source-machine build artifacts
- local `.env` files
- test caches
- virtual environments

---

### Historical external snapshot rollout checklist

FEWS and weather snapshot stores are runtime data, not part of the immutable
Wave 5 release and not normal Git deployment artifacts.

This later checklist records the external-snapshot rollout requirements. It is
retained as milestone context; use the [deployment guide](deployment.md) and
[environment contract](environment_contract.md) for subsequent operational guidance.
The smoke questions below may write normal conversation and analytics records.

When external sources are enabled in staging or production:

1. Provision persistent storage that survives API restarts and redeployments.
2. Place only completed FEWS and/or weather snapshot stores on that storage.
3. Configure the corresponding `AGDA_*_SNAPSHOT_PATH` with an absolute path.
4. Keep snapshot paths outside `data/releases/`.
5. Start the API normally. Startup restoration must use local storage only and
   must not contact FEWS NET or Open-Meteo.
6. Verify `/v1/ready` remains ready for the Wave 5 core service.
7. Verify `/v1/sources` reports the expected external snapshot restoration
   status and freshness.
8. Smoke-test one FEWS question and one weather question through the normal
   `/v1/questions` path.
9. Confirm stale or unavailable external data does not make Wave 5 unready.

External-source freshness is provenance information, not a replacement for the
underlying observation or forecast-valid timestamps.

## 12. Remaining Pre-Launch Work at This Milestone

These were the remaining steps at the preparation milestone. Subsequent
[staging readiness](staging_readiness.md) and [production launch](production_launch.md)
records document the original launch completion; [Phase 29](phase29_closure.md)
records later releases and persistence validation.

Original checklist before final production launch:

1. Select and configure hosting infrastructure.
2. Perform staging deployment and remote smoke testing.
3. Implement the persistent bottom chat composer UX.
4. Perform final responsive/browser QA.
5. Configure real production hostnames and environment variables.
6. Perform final production launch validation.
