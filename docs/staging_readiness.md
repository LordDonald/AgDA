# AgDA Staging Readiness

> Historical Step 22 staging record, committed September 16, 2026. Validation
> results, versions, private-only API claims and the memory-only limitation below
> describe that milestone; they do not establish current hosted state.
>
> The subsequent [production launch](production_launch.md) records the original
> launch completion. See [Phase 29](phase29_closure.md) for later source-verified
> release and persistence evidence, the [architecture](architecture.md) for
> current storage behavior and the [deployment guide](deployment.md) for the last
> recorded hosted topology and operational boundaries.

## Original Step 22 status

**Step 22: PASSED**

AgDA has been successfully deployed to the Railway staging environment and
validated remotely through the public Next.js application.

## Recorded Staging Architecture

Browser -> Railway Web -> Railway Private Network -> FastAPI -> wave5_v1

The FastAPI service is not publicly exposed.

## Validated Release

- Data version: `wave5_v1`
- Release state: `stable`
- Metric version: `1.0.0`
- Registered metrics: `18`

## Staging Validation Completed

- Railway API deployment successful
- Railway web deployment successful
- API readiness healthcheck passed
- Web public domain returned HTTP 200
- Web-to-API private networking passed
- Stable release checksum validation passed
- Remote analytical question passed
- Remote conversational follow-up passed
- Desktop browser QA passed
- 412px responsive QA passed
- 390px responsive QA passed
- Persistent follow-up composer implemented and validated
- Full answer content remains accessible above the composer
- Production-style dependency packaging validated

## Step 22 Deployment Controls

- API is private-only
- Web is publicly accessible
- API documentation is disabled outside development
- Trusted host validation is enabled
- Runtime uses Python 3.12
- Production dependencies are pinned
- Stable release artifacts are preserved byte-for-byte through `.gitattributes`

## Original MVP Limitation

At this milestone, conversation context was process-scoped and lost if the API
process restarted. Multiple API replicas did not share conversation state.

Later releases added Redis persistence; see the
[architecture](architecture.md#state-and-persistence) and dated
[Phase 29 persistence proof](phase29_closure.md#staging-persistence-live-proof-completed).
The single-replica recommendation below describes the original memory-backed runtime.

The initial MVP should therefore remain single-replica until shared
conversation persistence is introduced.

## Original Step 22 Decision

**Staging readiness: GO**

AgDA is ready to proceed to production-launch preparation.
