\# AgDA Environment Contract



\## Backend



| Variable | Default | Production |

| --- | --- | --- |

| `AGDA\_ENV` | `development` | `production` |

| `AGDA\_LOG\_LEVEL` | `INFO` | `WARNING` |

| `AGDA\_MAX\_CONVERSATIONS` | `500` | Capacity dependent |

| `AGDA\_MAX\_REQUEST\_BYTES` | `16384` | `16384` |

| `AGDA\_DOCS\_ENABLED` | `true` | `false` |

| `AGDA_ALLOWED_HOSTS` | `*` in development/test | Deployment hostname(s) |

| `AGDA\_SERVICE\_NAME` | `AgDA API` | `AgDA API` |

| `AGDA\_SERVICE\_VERSION` | `0.1.0` | Release version |



\## Frontend



| Variable | Local Development | Production |

| --- | --- | --- |

| `AGDA\_API\_URL` | `http://127.0.0.1:8000` | Hosted FastAPI URL |



## Host Security

FastAPI uses `TrustedHostMiddleware`.

Development and test environments allow all hosts by default so local
development and automated testing remain straightforward.

Staging and production should explicitly configure `AGDA_ALLOWED_HOSTS` with
the hostname or hostnames through which the API is expected to receive traffic.

Example:

`AGDA_ALLOWED_HOSTS=api.agda.example.com`

Do not use `*` in production unless there is a deliberate infrastructure
reason to disable host-header validation.

CORS is intentionally not enabled for the current architecture because browser
traffic is proxied through Next.js rather than sent directly to FastAPI.



\## Secrets



The current AgDA MVP does not require external API keys, passwords,

database credentials, or other application secrets.



Real `.env` files must not be committed.



Only `.env.example` files may be committed.



\## API Boundary



The browser communicates with Next.js.



Next.js communicates with FastAPI.



Browser -> Next.js `/api/\*` -> FastAPI



`AGDA\_API\_URL` therefore remains server-side and should not use

the `NEXT\_PUBLIC\_` prefix.

## Optional FEWS snapshot restoration

| Variable | Default | Meaning |
| --- | --- | --- |
| `AGDA_FEWS_SNAPSHOT_PATH` | Unset | Opt in to loading a local completed FEWS snapshot at API startup. Prefer an absolute path outside `data/releases/`. |
| `AGDA_FEWS_STALE_AFTER_HOURS` | `48` | Positive local retrieval-age threshold; independent of observation dates and FEWS publication cadence. |

Startup reads local storage only. Missing or unreadable storage is reported in
external-source health and does not affect core Wave 5 readiness. See
[FEWS snapshot persistence](fews_snapshot_persistence.md) for ingestion and
restoration commands.

