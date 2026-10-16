# AgDA documentation

Start with the [repository overview and local quick start](../README.md), then
use the guides below. Configuration requirements, dated verification results
and historical milestone records serve different purposes. A recorded successful
deployment or preservation run does not establish current hosted availability.

## Start here

| Document | Use it for |
| --- | --- |
| [Agriculture evaluation guide](agriculture_evaluation.md) and [PDF](agriculture_evaluation.pdf) | Expert briefing on aims, capabilities and limits, with guided questions and a feedback worksheet |
| [Local development](local_development.md) | Reproducible local setup, default behavior, backend/frontend checks and troubleshooting |
| [Architecture](architecture.md) | Components, deterministic question flow, storage responsibilities, source provenance and failure boundaries |
| [Deployment model](deployment.md) | Last recorded staging/production topology, manual promotion, refresh operations and verification boundaries |
| [Environment contract](environment_contract.md) | Configuration behavior, secrets, persistence isolation, optional external snapshots and manual production deployment safeguards |
| [Phase 29 release and closure](phase29_closure.md) | Completed release and closure evidence, final merge/CI, runtime source provenance, deployment records, staging persistence and browser validation |
| [Hosted-data preservation](hosted_data_preservation.md) | The recorded six-set preservation result, local master location and hashes, export formats, historical Redis coverage limits, dated reconciliation, excluded attempt and recovery limitations |

The environment contract describes requirements; it does not prove that a
service is provisioned. Phase 29 records the last source-verified runtime
separately from the closure merge. The preservation record documents capture-time
results and later Redis reconciliation. Its dated empty production namespace
observation does not prove coverage at the original capture time or establish
an end-to-end restore drill.

## External-source and query references

These documents combine useful contracts with their original implementation
milestones. Their validation counts and rollout notes retain that historical
scope.

| Document | Scope |
| --- | --- |
| [Phase 28 external capabilities](phase28_external_capabilities.md) | Explicit external-query selectors, supported operations, saved-snapshot provenance and guardrails, with implementation/staging evidence |
| [FEWS monthly client](fews_market_price_client.md) | Phase 26B.3 bounded retrieval, pagination, normalization and original client verification |
| [FEWS snapshot persistence](fews_snapshot_persistence.md) | Phase 26B.4 SQLite persistence and runtime restoration design, with the original pilot boundaries |
| [Market-price API](market_prices_api.md) | Phase 26B.5 read-only market-price API contract and pilot evidence |
| [Weather forecast pilot](weather_forecast_pilot.md) | Phase 26C.1 forecast retrieval contract, location/time bounds, weather semantics and original verification |

The Phase 26 documents predate later persistence, question routing, refresh and
production rollout. Read their "next step" and "remaining roadmap" statements as
milestone history. Phase 28's pending promotion and staging-persistence statements
also predate the subsequent completion recorded in Phase 29. Use the environment
contract and Phase 29 record for later configuration and hosted validation.

## Evidence and schema

| Artifact | What it records |
| --- | --- |
| [Phase 29 environment freeze](evidence/phase29_environment_freeze.json) | Sanitized configuration/deployment checks and runtime observations captured on October 15, 2026 |
| [Phase 29 persistence and browser QA](evidence/phase29_live_persistence_and_browser_qa.json) | Staging continuity across API redeployment and browser acceptance checks captured on October 15, 2026 |
| [Redis preservation reconciliation](evidence/redis_preservation_reconciliation_20261016.json) | Sanitized local artifact checks and the October 16, 2026 production namespace inspection; historical coverage and restore limits remain explicit |
| [Staging analytics schema](sql/staging_analytics_schema.sql) | Guarded bootstrap for a verified dedicated staging database; this is not a general migration or production restore script |

Evidence files preserve their original observation times and deployment IDs.
Reading the schema is separate from executing it against a database. Raw hosted
preservation artifacts remain outside Git; their custody and integrity references
are in the preservation record.

## Historical delivery records

| Document | Original milestone |
| --- | --- |
| [Step 20 release readiness](step20_release_readiness.md) | Analytical, conversational and persona QA for the original core release |
| [Deployment readiness](deployment_readiness.md) | Original MVP deployment preparation and artifact checklist |
| [Staging readiness](staging_readiness.md) | Step 22 staging validation |
| [Production launch](production_launch.md) | Original MVP production launch and its acceptance evidence |
| [Deployment guardrail verification](deployment_guardrail_verification.md) | Temporary documentation artifact used to exercise branch, CI and staging workflow safeguards |

Memory-only conversation limitations, deferred interface work, and pending launch
steps in these records describe their original milestones. They should not be
used as current feature or deployment instructions. The guardrail artifact alone
does not prove current branch-protection settings.

## Code and release references

- [Stable release pointer](../data/releases/stable_release.json) and
  [Wave 5 release manifest](../data/releases/wave5_v1/release_manifest.json)
  identify the bundled analytical release.
- [Web application guide](../apps/web/README.md) explains the Next.js proxy,
  dashboard token roles and local production-mode preview.
- [CI workflow](../.github/workflows/ci.yml) defines dependency installation and
  backend/frontend validation commands.
- [Backend environment examples](../.env.example) and
  [web environment examples](../apps/web/.env.example) accompany the environment
  contract. Real credentials belong outside repository documentation.
- [User-question QA bank](../tests/qa/user_question_bank.py) supplies concrete
  supported questions and expected clarification or refusal behavior.
