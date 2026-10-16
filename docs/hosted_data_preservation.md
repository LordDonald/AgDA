# Hosted-data preservation record

Original October 16, 2026 UTC result: **6/6 sets passed artifact checks**.
A later inspection found the production runtime namespace empty on two scans;
**its coverage at the original capture time remains unproven**.

This record combines the operator-supplied capture results with subsequent
read-only checks of the Redis artifacts and a dated production Redis inspection.
The original master inventory, hashes and preservation files remain unchanged.
The follow-up findings below distinguish saved-file integrity, namespace coverage
and observed live state; they do not establish a completed restore or continuing
service availability.

The preservation run recorded a clean `main` at
`b8e21b75d7e8604ac3f7c54fbdcabe335d7a7a03`. That is the repository reference for
the preservation record; the separately verified runtime release is documented
in the [Phase 29 closure record](phase29_closure.md).

## Master inventory and integrity references

Preservation root on the operator's computer:

```text
C:\Users\LORD DONALD\Documents\AgDA-preservation
```

Verified master directory:

```text
C:\Users\LORD DONALD\Documents\AgDA-preservation\master-20261016T025103Z
```

| File in the master directory | Recorded SHA-256 |
| --- | --- |
| `AgDA-preservation-master.json` | `718bd01316e1156a51cba9f3144d980278aed7f8d6c5d0013d2fdd8a6f9aed93` |
| `AgDA-preservation-summary.txt` | `237c1842cf6abb62efeb5e073ccba53fb4307f218fb2c8126c61cdbf51c5cbda` |

The master inventory records each included set's manifest, preservation status,
file count, byte count, relative file paths and SHA-256 hashes. Its creation
checkpoint checked the six manifests and rehashed the files in the included
sets. The reported result was `AGDA_HOSTED_DATA_PRESERVATION=PASS`.

The later read-only reconciliation matched both master-file hashes above and all
12 files in the two Redis sets against their recorded sizes and SHA-256 hashes.
The other four sets retain their original reported verification; they were not
rehashed during this Redis reconciliation. Passing hashes do not validate an
export selector's coverage.

These paths are local custody locations, not downloadable repository assets.
The completed result reports `NO_CREDENTIALS_IN_MASTER=True` for the master
inventory. The master inventory is an index; the referenced
sets must also be retained. Keep the raw databases, Redis payloads, analytics
exports and preservation manifests outside Git. This document records their
scope and integrity references without copying their contents into the repository.

## Six sets in the reported verified inventory

Each directory below is directly under the preservation root. All six were
included in the verified master inventory.

| Target | Preservation directory | Captured scope | Recorded result |
| --- | --- | --- | --- |
| Production Railway volume | `production-volume-20261016T014430Z` | FEWS and weather SQLite databases | PASS; 2 FEWS snapshot rows and 25 weather snapshot rows |
| Production Neon PostgreSQL | `production-neon-20261016T021231Z` | Analytics and feedback; 2 public tables and 5 views | PASS; 30 `product_events` rows and 1 `product_feedback` row |
| Production Upstash Redis | `production-upstash-20261016T023643Z` | Selected `agda:conversation:*` keys; original runtime-namespace coverage unproven | PASS; 1 key, 1 recognized index member, 0 recognized active conversations |
| Staging Railway volume | `staging-volume-20261016T024225Z` | FEWS and weather SQLite databases | PASS; 2 FEWS snapshot rows and 25 weather snapshot rows |
| Staging Neon PostgreSQL | `staging-neon-20261016T024453Z` | Analytics and feedback; 2 public tables and 5 views | PASS; 4 `product_events` rows and 1 `product_feedback` row |
| Staging Render Redis | `staging-render-redis-20261016T024726Z` | Entire selected staging Redis database | PASS; 3 keys, 0 recognized index members, 0 recognized active conversations |

Counts describe capture-time records. SQLite counts are stored snapshot rows,
not counts of market observations or forecast hours. Redis index members are
not evidence of surviving conversation payloads. Redis conversation/index counts
use the export scripts' recognition rules; see the reconciliation below.

## Export formats and completed checks

### Railway SQLite

Both environments preserved these files from their API-owned `/data/external`
volume:

- `fews_ng_white_maize_2025_01.sqlite3`
- `weather_aba_forecast.sqlite3`

Two independent downloads per database matched by SHA-256. SQLite integrity
and foreign-key checks passed, and the local manifests passed JSON validation.
These sets preserve the two named databases; they are not full volume images.

### Neon PostgreSQL

Both sets contain table data in CSV and JSONL, row counts, schema/column metadata,
constraint metadata, index metadata, view definitions, hashes and manifests.
CSV/JSONL and hash checks passed for both tables, and definitions for five public
views were captured. Exports used read-only transactions.

These are **verified logical exports, not native `pg_dump` archives**. The
production manifest status is `verified_emergency_logical_backup`; staging uses
`verified_logical_backup`. Their format must be considered when planning a
future restoration; a successful export does not establish a completed restore.

### Redis

Both Redis sets contain per-key native `DUMP` payloads, TTL metadata, conversation
JSON export artifacts and index metadata. Native payload, JSON export and
manifest checks passed. These are per-key exports, not full Redis RDB images.

The recorded production export script selected `agda:conversation:*`, including
`agda:conversation:index`. The staging script selected the entire Redis database
for native per-key capture. Both scripts recognized conversations and their index
using the unqualified `agda:conversation:` prefix.

### Redis namespace reconciliation

The [API runtime](../apps/api/app/core/runtime.py) explicitly passes
`agda:{environment}:conversation` to the
[Redis store](../packages/answering/conversations.py). This behavior is present
both at the preservation repository reference and the independently
source-verified deployed revision
`722e6d5b00b6f97d798d64cb568651bcbc35052e`. The corresponding runtime prefixes are
`agda:production:conversation:*` and `agda:staging:conversation:*`, each with its
own `:index` key. The store constructor's unqualified default is overridden.

Read-only inspection of the saved inventories established:

| Set | Saved key metadata | Interpretation |
| --- | --- | --- |
| Production Upstash | Only `agda:conversation:index`, a sorted set; 1 index member reported as stale | The selector did not include the runtime production prefix. The saved index is not evidence of a surviving conversation payload. |
| Staging Render | Two `agda:staging:conversation:<id>` string keys and `agda:staging:conversation:index`, a sorted set | All three keys have native `DUMP` artifacts matching their inventory hashes. The whole-database export included these runtime-prefixed keys. |

Both `conversations.jsonl` files are empty. Staging's original zero recognized
conversations/index members came from the unqualified-prefix classifier, even
though its native capture included runtime-prefixed keys. The native values were
not decoded or restored during reconciliation; two string keys do not establish
two validated or restorable conversations. The production selector mismatch
alone does not establish whether runtime keys existed at capture or were lost.

### Dated production namespace inspection

A separate read-only inspection ran on **October 16, 2026, from 04:00:38.656625
to 04:00:43.109269 UTC**, against the Redis database configured for the production
API. The project, environment and service IDs were checked, and the connection
used TLS with certificate verification.

- Two complete scans of `agda:production:conversation:*` each returned **0 keys**.
- `agda:production:conversation:index` was absent in both observations.
- No conversation values were read. Commands sent were authentication, `PING`,
  `SCAN`, `TYPE` and `PTTL`; no Redis write commands were issued.

There were no matching payloads to export at that inspection time, so no
supplemental payload export was created. The two scans were not an atomic
snapshot and do not establish continuous emptiness, capture-time coverage, or
future state. The earlier production selector limitation remains part of the
record; the original six-set result is not retrospectively upgraded.

The [sanitized reconciliation evidence](evidence/redis_preservation_reconciliation_20261016.json)
records the local integrity checks and dated live observations without
credentials, conversation IDs or payloads. It is separate from the original
master inventory. No preservation artifacts, hosted configuration or deployments
were changed by either follow-up check. Payloads already expired before capture
cannot be reconstructed from an index or TTL metadata.

## Excluded incomplete attempt

The following directory is retained as an incomplete attempt and **is not part
of the verified inventory**:

```text
C:\Users\LORD DONALD\Documents\AgDA-preservation\production-upstash-20261016T023058Z
```

That attempt stopped when a development-namespace key changed between reads.
The retry that passed artifact checks is `production-upstash-20261016T023643Z`;
its namespace-coverage limitation is recorded above.
Do not count the incomplete directory toward the six reported passing sets, use it as
the verified production backup, or delete, modify or merge it during documentation
work.

## Verification boundaries and future recovery

The completed preservation outputs report no database/Redis writes, live
configuration changes, deployments or Git changes during capture. Preservation
created local artifacts outside the repository.

The six sets were captured separately. The master index ties their identities
and hashes together; it does not establish a simultaneous snapshot across all
services. Later hosted writes, refreshes and TTL expiry are outside this record.

No end-to-end restore drill is established by the handoff evidence. Any future
recovery should first verify the selected artifacts against the master inventory
and use a separately planned, isolated restore destination. Preserve the source
artifacts unchanged, keep staging and production separate, and explicitly decide
how captured Redis TTLs will be handled. This checkpoint performs no restoration.

The [environment contract](environment_contract.md) describes configuration and
environment separation. The [Phase 29 closure record](phase29_closure.md) provides
the earlier deployment and persistence evidence; its API-redeployment continuity
proof is separate from restoration of these preservation sets.
