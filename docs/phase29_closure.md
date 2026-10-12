# Phase 29 release and closure record

Status on October 12, 2026: **release promoted; final phase remains open**.
The reviewed Phase 28 implementation is running in staging and production.
Dedicated staging Redis and analytics restoration is blocked by Railway's
resource provision limit. Browser rendering QA also remains unverified because
the available browser inventory is empty. These are not recorded as passes.

## Scope and acceptance

| Gate | Acceptance | Evidence / state |
| --- | --- | --- |
| 29A review | Exact reviewed PR head, clean mergeability, two green CI checks | Passed for PR #16 at `7a826be1f3a71e19d69e95ab127a4543dfb5be89` |
| 29B merge | Guarded merge; exact merge SHA recorded; local and remote main aligned | Passed; merge `722e6d5b00b6f97d798d64cb568651bcbc35052e` |
| Staging release | Merged API and web source verified; core and external behavior pass | Passed; deployments and checks below |
| Production release | Manually promote the same clean revision after staging; verify source and behavior | Passed for API and web |
| Staging persistence | Dedicated resources; schema verified; Redis context and analytics survive redeployment | **Blocked** before provisioning; no live persistence proof claimed |
| Secrets and config | Separate environment/role secrets, correct private targets, no public credentials, manual production guardrails | Passed for the checks described below |
| Regression and CI | Backend regression, trusted hosts, user/manual QA, frontend lint/build | Release main CI passed; closure PR must also pass its own CI |
| Environment freeze | Record exact deployments, sources, volumes, schedules, readiness and open items | Captured with the persistence and visual QA limitations explicit |

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
| staging | api-staging | `aa4c7f0c-f4f6-4a74-b933-257515b2c1bb` |
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
labels. This is HTTP/proxy/asset evidence, **not** a browser rendering or clicked
UI journey proof.

## Staging persistence: outstanding external dependency

The original staging service recovery intentionally left conversations in memory
and analytics persistence unconfigured. Fresh dedicated services were selected
to avoid sharing production storage. On October 12 the staging-linked Railway
Redis provisioning call failed with:

> Free plan resource provision limit exceeded. Please upgrade to provision more resources!

No Redis service was created, and the subsequent inventory still contained only
the existing staging API, web and weather scheduler. PostgreSQL was not provisioned
after the capacity failure. Staging remains `AGDA_CONVERSATION_BACKEND=memory`,
with no Redis URL or analytics database URL. Production persistence was unchanged.

The operator must supply additional Railway capacity or independently provisioned
**dedicated staging** Redis and PostgreSQL resources. Configure credentials through
secret settings; never put them in chat, tracked files or command output.
Analytics records have no environment discriminator, so the production analytics
database is not an acceptable staging destination.

The remaining restoration sequence is:

1. Verify service/environment identity and separate storage destinations. Check
   PostgreSQL existing objects and privileges before any bootstrap.
2. Apply [the staging SQL bootstrap](sql/staging_analytics_schema.sql) to the
   independently verified staging database, with its explicit session marker.
   Apply it twice and verify both tables plus all five view contracts. It is a
   guarded, transactional bootstrap, not an automatic migration of unknown tables.
3. Configure staging-only Redis/analytics references and select the Redis backend;
   preserve existing tokens and all production settings. Redeploy staging from
   the clean release SHA above. Verify its source identity and readiness.
4. Execute `tools/validate_phase29_persistence.py --phase before` inside the
   staging API, including when sent through SSH stdin. Retain its synthetic
   `proof_id` and `deployment_id`. Redeploy the same release and reverify source.
5. Run the tool with `--phase after --proof-id ID --previous-deployment-id ID`.
   It requires a different deployment identity, verifies Redis schema/TTL/context,
   persisted question and feedback rows, contextual follow-up, feedback upsert,
   all five SQL/API analytics contracts and authorization, and unchanged readiness.
   Direct storage connections are read-only; synthetic records are created through
   the application's normal question/feedback routes.
6. Verify the authenticated web analytics proxy, repeat the sanitized environment
   freeze, and replace this blocked status with actual live evidence.

The persistence tool has local contract/safety coverage; the SQL bootstrap has
been statically reviewed. Neither has been executed against a live dedicated
staging database. Selecting Redis
introduces the pre-existing conversation-store startup dependency; analytics write
failures remain non-blocking for answers. Neither changes the non-blocking external
source readiness contract.

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

Phase 29 must remain open until staging persistence is restored and survives its
redeployment proof, final CI is green, the environment freeze is renewed, and the
visual QA gap is resolved or explicitly accepted by the operator.
