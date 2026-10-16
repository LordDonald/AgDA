# AgDA Production Launch Record

> Historical MVP launch record, committed September 16, 2026. The launch result,
> URLs, versions and private-only API description below record that milestone;
> they do not establish current availability or current endpoint exposure.
>
> Later release and persistence validation is recorded in
> [Phase 29](phase29_closure.md). Use the [deployment guide](deployment.md) for the
> last recorded hosted topology, the [architecture](architecture.md) for current
> storage behavior and the [environment contract](environment_contract.md) for
> configuration requirements.

## Original launch status

**PRODUCTION LAUNCH: PASSED**

AgDA has completed production deployment and end-to-end launch validation.

---

## Recorded Production Architecture

Browser -> Railway Web -> Railway Private Network -> FastAPI -> wave5_v1

The FastAPI service is private and is not directly exposed to the public
internet.

The public application is served through the Next.js web service.

---

## Recorded Production URL

`https://web-production-ba3f9.up.railway.app`

---

## Validated Release

- Data version: `wave5_v1`
- Release state: `stable`
- Metric version: `1.0.0`
- Registered metrics: `18`

---

## Production Runtime

### Backend

- Python 3.12
- FastAPI
- Uvicorn
- DuckDB
- Pandas
- PyArrow
- Pydantic

### Frontend

- Next.js 16.3.4
- React 19.2.8
- TypeScript

---

## Launch-Time Deployment Controls

- Production API is private-only.
- Production web service is publicly accessible.
- API documentation is disabled outside development.
- Trusted host validation is enabled.
- API request-size limits are enabled.
- Request IDs and safe server-error handling are enabled.
- Stable release artifacts are checksum validated at API startup.
- `data/releases/**` is preserved byte-for-byte through `.gitattributes`.
- Production dependencies are pinned.
- Production and staging environments are isolated.

---

## Launch Validation

The following production checks passed:

- public homepage returned HTTP 200;
- API health returned `ready`;
- environment reported `production`;
- stable `wave5_v1` release loaded;
- all 18 registered metrics loaded;
- production analytical question returned expected results;
- conversation context persisted across follow-up questions;
- production browser UI rendered successfully;
- persistent bottom conversation composer operated correctly;
- complete answer content remained accessible;
- unsupported profitability question was rejected safely;
- staging remained healthy after production launch.

---

## Analytical Smoke Test

Question:

`What are farmers mostly growing in Kaduna?`

Validated result included:

- MAIZE: approximately 74.2%
- RICE: approximately 31.5%
- SOYA BEANS: approximately 25.5%

Follow-up:

`What about rice?`

AgDA correctly retained:

- State: Kaduna
- Crop: RICE

and returned approximately 31.5%.

---

## Safety Smoke Test

Question:

`Does that mean rice is more profitable there?`

Result:

`unsupported`

AgDA correctly stated that profitability cannot be calculated reliably because
complete production-cost and margin data are unavailable.

No unsupported profitability estimate was generated.

---

## Staging Environment at Launch

Staging remains available separately for future release validation.

Staging URL:

`https://web-staging-4660.up.railway.app`

Staging health remained:

- status: `ready`
- environment: `staging`
- data version: `wave5_v1`
- release state: `stable`

---

## Original MVP Limitation

At launch, conversation context was process-scoped.

Later releases added Redis persistence, with dated API-redeployment evidence in
[Phase 29](phase29_closure.md#staging-persistence-live-proof-completed). The limitations
below apply to the original memory-backed runtime.

Therefore:

- conversations are lost when the API process restarts;
- multiple API replicas do not share conversation state;
- production should remain single-replica until shared conversation persistence
  is introduced.

This limitation does not block the initial MVP launch.

---

## Original Launch Decision

**GO**

AgDA is operational in production and has passed the required application,
analytics, safety, deployment, responsive-UI, and production smoke-test gates.
