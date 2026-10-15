# Phase 29 release and closure record

Status on October 15, 2026: **release promoted; runtime closure gates passed; final closure PR validation remains**.
The reviewed Phase 28 implementation remains the deployed runtime in staging and
production. Dedicated staging Redis and PostgreSQL analytics persistence have now
been restored and proven across API redeployment. Authenticated web analytics and
four clicked browser-rendering QA journeys also passed. No production runtime was
changed during this persistence/visual closure work.

## Scope and acceptance

| Gate | Acceptance | Evidence / state |
| --- | --- | --- |
| 29A review | Exact reviewed PR head, clean mergeability, two green CI checks | Passed for PR #16 at `7a826be1f3a71e19d69e95ab127a4543dfb5be89` |
| 29B merge | Guarded merge; exact merge SHA recorded; local and remote main aligned | Passed; merge `722e6d5b00b6f97d798d64cb568651bcbc35052e` |
| Staging release | Merged API and web source verified; core and external behavior pass | Passed; deployments and checks below |
| Production release | Manually promote the same clean revision after staging; verify source and behavior | Passed for API and web |
| Staging persistence | Dedicated resources; schema verified; Redis context and analytics survive redeployment | Passed; dedicated staging Redis and PostgreSQL survived the before/redeploy/after proof |
| Secrets and config | Separate environment/role secrets, correct private targets, no public credentials, manual production guardrails | Passed for the checks described below |
| Regression and CI | Backend regression, trusted hosts, user/manual QA, frontend lint/build | Release main CI passed; previous closure-head CI passed; final updated closure head still requires CI |
| Browser rendering QA | Clicked staging journeys, keyboard path, analytics dashboard, zoom/responsive behavior | Passed 4/4 on the deployed staging web UI |
| Environment freeze | Record exact deployments, sources, volumes, schedules, readiness and open items | Renewed after live persistence/browser QA; all sanitized configuration checks passed |

No runtime code, Wave5 release data, provider clients, source contracts, refresh
logic or deployment workflow changes are part of this closure increment.
It adds documentation, optional-setting examples, operational validation tools
and their regression coverage.

## Exact release and merge provenance

- [PR #16](https://github.com/LordDonald/AgDA/pull/16) was non-draft, clean and
  mergeable, with both checks successful at the reviewed head. The merge command
  required that exact head; it completed at `2026-10-12T20:51:58Z`.
- Baseline main: `66ee03f7bcba0642aee8b77b3d73c36744381a03`.
- Reviewed head: `7a826be1f3a71e19d69e95ab127a4543dfb5be89`.
- **Merge and deployed release: `722e6d5b00b6f97d798d64cb568651bcbc35052e`.**
- The merge tree equals the reviewed head tree. Both local main checkouts and
  `origin/main` were clean and aligned to that merge before promotion.
- [Main CI run 38306972396](https://github.com/LordDonald/AgDA/actions/runs/38306972396)
  passed backend regression/QA and frontend lint/production build at the merge.
- Production was uploaded manually from a separate clean checkout at this SHA.
  Closure files remained in a separate `phase29/closure` worktree, preventing
  uncommitted operational tooling from entering the release upload.
- CLI deployment messages record the full SHA, but are not used alone as source
  proof. Standalone probes generated from tracked files in the clean release
  checkout matched all **116 API/release-data files** and **27 web source files**
  in both deployed environments. The manifests hash actual checkout bytes,
  including intentional Git newline handling. They do not attest generated web
  build assets or unrelated extra files.

## Deployment record

Railway project: `0660f957-e4ad-4369-abca-984316363c2d`.

| Environment | Service | Successful deployment |
| --- | --- | --- |
| staging | api-staging | `bb9dd0e4-3ed9-4f42-8f18-81c6e37baeee` |
| staging | web | `c25633ed-dc6b-4502-8536-f956cad732c6` |
| production | api | `e5786547-ca07-4e8c-8729-e18d89ff51e0` |
| production | web | `ca0e5c79-7a1e-4c02-b85a-dd47e34ccff2` |

All four are tied to release `722e6d5b00b6f97d798d64cb568651bcbc35052e`
by the source probes. Staging API behavior and source identity passed before
production API promotion; staging web health and source identity passed before
production web promotion.

Both API release probes passed exact FEWS observation, compatible market ranking,
exact forecast temperature hour, independently calculated precipitation sum and
72/72-hour coverage, out-of-coverage refusal, invalid operation/source selection
(422), stale snapshot pin rejection (409), Wave5 yield/price-change/climate
answers, mixed-source and qualified-location reframing, and legacy external
ranking. Core health passed before and after each run:
`wave5_v1`, `stable`, metric `1.0.0`, 18 metrics, `ready=true`, and
`external_sources.affects_core_readiness=false`.

Snapshots used in the exact release probes:

| Environment | Source | Snapshot |
| --- | --- | --- |
| staging | FEWS | `555beb1480ab9482df703803e24e3a83b97852f8af60ba379dfe38d2103db501` |
| staging | weather | `20c71654c069139b402886424da1788f79a55dbc15fd5e756229d09051ced169` |
| production | FEWS | `e04b839dc52e78e5fcdba201e36c0e5cf5d9f1fe29f0172045f3218f75d69008` |
| production | weather | `acd574ab7151601c189d4bc29e072033aceb990ee7d69aa6afcbff3722dc7dad` |

These are proof-time snapshot identities, not promises that scheduled weather
refreshes will keep the same snapshot indefinitely. Retrieval freshness is
distinct from observation age and forecast-valid time.

Deployed web HTTP QA passed in both environments: home document and all seven
delivered JavaScript assets returned 200; health selected the correct environment;
Wave5, FEWS and weather questions returned their appropriate provenance; mixed
source and unsupported-location questions required reframing. Served assets
contain the external-data, forecast, historical-observation and saved-query-scope
labels.

The previous browser-rendering gap is now resolved on staging. Four clicked
browser checks passed: initial rendering plus Enter-key question submission;
same-conversation contextual follow-up; authenticated internal analytics dashboard
rendering/refresh; and approximately 200% browser zoom followed by New conversation
reset. No overlap, clipping, broken horizontal layout or visible application error
was observed in those checks.

## Staging persistence: live proof completed

Railway's free-plan resource limit prevented additional native persistence
resources, so independently provisioned resources were used instead. Both were
verified as distinct from production before configuration:

- Conversation persistence uses the dedicated staging Render Key Value endpoint
  `oregon-keyvalue.render.com:6379` over `rediss`.
- Analytics persistence uses the dedicated staging Neon PostgreSQL endpoint
  `ep-noisy-truth-arwkfcsa.c-4.us-west-2.aws.neon.tech`, database `neondb`.
- Neither production Redis nor the production analytics destination was reused.
- Credentials remain environment secrets and are not recorded in this repository.

The PostgreSQL target was inspected before mutation and contained no public
tables/views. The guarded staging bootstrap was executed twice in the same
verified staging session. The second execution passed idempotently with both
tables, all five views and all five current analytics result contracts present;
`product_events` and `product_feedback` were empty before the synthetic proof.

Staging was then configured with `AGDA_CONVERSATION_BACKEND=redis` plus the
dedicated Redis and analytics URLs. A Railway retained-source redeploy was
explicitly rejected after the exact source probe detected 16 mismatched
API/release-data files. No persistence result from that deployment was accepted.
The API was manually uploaded again from the clean exact release
`722e6d5b00b6f97d798d64cb568651bcbc35052e`; the standalone source probe then
passed all 116 API/release-data files with no mismatch.

The successful persistence sequence used synthetic proof identifier
`p29_17902f6b05384672b5ba2144c91731b0`:

- Before deployment `3e853487-3f44-449b-8814-7c4148135ef0`: Redis schema version
  1 and positive TTL passed; one synthetic question event and one feedback row
  were durable; all five analytics SQL/API contracts passed; core remained
  `wave5_v1`, `stable`, metric `1.0.0`, 18 metrics and ready.
- After replacement, current deployment
  `bb9dd0e4-3ed9-4f42-8f18-81c6e37baeee` was independently source-verified at
  116/116 files and passed readiness before the after proof.
- The after proof first confirmed that the original Redis conversation, question
  event and feedback record survived the API replacement. It then resolved
  `What about Kaduna?` using the persisted RICE grower-share context, created the
  second durable question event and updated the existing feedback record.
- All five analytics contracts passed after restart; the post-update view row
  counts were `[1, 2, 1, 1, 0]`. Core readiness and release invariants remained
  unchanged.
- The unauthenticated staging web analytics proxy correctly returned 401.
  Authenticated access returned 200 with `total_questions=2` and
  `feedback_count=1` at the proof-time check.

Direct storage access in the proof was read-only; synthetic records were created
only through the application's normal question and feedback routes. The free
Render staging resource does not provide the same provider-level durability
guarantees as production storage; this closure proves survival across AgDA API
redeployment, which is the Phase 29 persistence acceptance condition.

## Secrets/config audit and freeze

The sanitized [environment freeze](evidence/phase29_environment_freeze.json)
records check booleans and deployment metadata only. Secret values were compared
in process memory and were not logged or committed.

- API/web analytics tokens match within each environment. Operations, analytics
  and dashboard roles use distinct tokens; equivalent roles differ across
  environments. Scheduler tokens match the intended API.
- Staging web/scheduler target `api-staging.railway.internal`; production
  web/schedulers target `api.railway.internal`. No web database/Redis/operations
  credentials or public-prefixed secret variables were configured.
- The external free-tier staging Redis endpoint uses TLS and authentication.
  Railway Free has dynamic egress, so its Render external allowlist is
  `0.0.0.0/0`; this is a staging-only limitation. Provider-restart durability is
  not claimed by the Phase 29 API-redeployment persistence proof.
- Hosted API documentation is disabled. Frontend credentials remain server-side.
  A targeted scan of 220 tracked files and the three Phase 28 commits found no
  private-key, provider-key, credential-URL or inline-secret candidates. This was
  a targeted audit, not an exhaustive credential-history or dependency-advisory scan.
- A bounded API log audit returned 73 staging and 91 production lines. Neither
  sample contained configured secret values, credential URL patterns or the
  checked authentication-header patterns. Raw log contents were not retained.
- Production API and web repository sources are blank. Manual CLI promotion did
  not reconnect them to GitHub. Both production schedulers also retain blank sources.
- Production weather remains `0 */4 * * *`; FEWS remains `30 3 1 * *`.
  Their successful deployments remain `0f31ce2a-4746-4707-b411-e7fc272e4a33`
  and `390bcfbb-dd3c-4a5a-ad45-6e0c7409e2bc`, respectively.
- The production API is the sole owner of `/data/external`; production web and
  both schedulers have no attached volume. Staging API retains its separate
  `/data/external` volume and its weather scheduler retains the four-hour schedule.
- Production conversations remain on Redis and analytics remain configured;
  neither storage destination nor credential was changed.

## Regression and closure tools

The final local backend regression passed **50/50 scripts**, including the new explicit
environment release verifier, source-identity builder and staging persistence
proof tests. Independent local checks passed user QA 23/23, all five manual QA
journeys, trusted-host allow=200/block=400 and dependency consistency. The source
probe safety suite passed 8 tests, the environment smoke safety suite 12, and
persistence proof safety suite 12. `git diff --check` passed. Closure CI evidence
belongs to the closure PR; the deployed runtime remains the exact merge SHA
recorded above.

`tools/validate_phase29_release.py` requires an explicit staging or production
selection, verifies stable core/environment health before analytical POSTs,
disables redirects and avoids provider refreshes. The original staging-only
validator remains unchanged.

`tools/build_release_probe.py` requires an exact clean Git HEAD, rejects index
flags that can hide tracked-file changes, and writes outside the release checkout.
Its Python or Node probes require the selected environment, constrain manifest
paths, and report only revision, file count and mismatched relative paths.

The runtime persistence, visual QA and renewed environment-freeze closure gates
are now satisfied. Phase 29 remains open only for final closure-head
validation/CI, review of the resulting documentation-only diff and guarded merge
of PR #17.
