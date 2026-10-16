# Local development

This guide starts AgDA locally with the bundled Wave 5 release and runs the
repository's local validation checks. Hosted services, provider ingestion and
preservation restoration are separate workflows. For the project overview, see
the [root README](../README.md); for all settings, see the
[environment contract](environment_contract.md).

## Prerequisites and working directory

- Git and a local checkout of this repository.
- Python 3.12 and Node.js 24 with npm, matching the
  [CI workflow](../.github/workflows/ci.yml).
- Network access for dependency installation. Once installed, the core local
  application uses the checked-in release without needing hosted data services.

Examples use Windows PowerShell. Open a dedicated local terminal at the
repository root, where `pyproject.toml` and `requirements.txt` are located. Keep
each checkout or worktree's Python environment separate so imports resolve to
the code being edited.

## Install dependencies

Create the environment once, then install the same production and test
dependencies used by CI. Run each command separately and stop if it fails:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install httpx2==2.13.1 fakeredis==2.37.1
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m pip check
```

If `py` is unavailable, invoke an installed Python 3.12 interpreter directly;
PowerShell uses `&` before a quoted executable path. Activation is unnecessary
when using the explicit `.venv` executable. These commands install into that
environment, not a global Anaconda or Python environment.

In a second terminal at the repository root, install frontend dependencies:

```powershell
Set-Location apps/web
npm.cmd ci
```

The committed npm lockfile defines the frontend dependency set. Using `npm.cmd`
avoids PowerShell's `npm.ps1` execution-policy wrapper. On macOS/Linux, create
the environment with `python3.12 -m venv .venv`, use `.venv/bin/python` for the
Python commands, and use `npm` in place of `npm.cmd`.

## Start the core API

In the dedicated backend terminal at the repository root, reset AgDA settings
for this local shell and start the API:

```powershell
Get-ChildItem Env:AGDA_* | Remove-Item
$env:AGDA_ENV = "development"
$env:AGDA_CONVERSATION_BACKEND = "memory"
$env:AGDA_DOCS_ENABLED = "true"
$env:AGDA_ALLOWED_HOSTS = "localhost,127.0.0.1,testserver"
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```

The reset removes only `AGDA_*` process variables in this terminal. It does not
change saved user/machine settings or hosted configuration. It also removes
inherited database URLs, Redis URLs, tokens and snapshot paths without printing
their values. `testserver` permits the in-process test client used by the local
checks below; this host list is for local development.

The backend reads process environment variables at import/startup. It does not
automatically load the root `.env` file. The
[backend example](../.env.example) documents available settings; set desired
values in the launching process and restart the API after changing them.

This core setup has the following behavior:

| Feature | Local core behavior |
| --- | --- |
| Wave 5 questions | Served from the bundled `wave5_v1` release |
| Conversations | Held in memory and lost when the API restarts |
| Redis and PostgreSQL | Not required or connected by these settings |
| Analytics persistence and feedback storage | Disabled until a database is configured; feedback requests return 503 |
| Internal analytics | Disabled until the database and analytics token are configured |
| FEWS/weather snapshots | Restoration disabled until snapshot paths are configured; core readiness is independent |
| LLM service | Not required by the current deterministic answering path |

## Start the web interface

In the frontend terminal, still in `apps/web`, use the local API explicitly:

```powershell
Get-ChildItem Env:AGDA_* | Remove-Item
$env:AGDA_API_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

Open [http://localhost:3000](http://localhost:3000). Browser requests use the
Next.js `/api/*` routes; the Next.js server calls FastAPI. The API URL and backend
tokens must stay server-side.

Next.js can also load settings from `apps/web/.env.local`. Process variables
take precedence, so inspect the names of any existing local configuration before
assuming defaults. Keep any optional database/dashboard configuration local to
development. See the [web README](../apps/web/README.md) for proxy routes,
environment-file behavior, dashboard access and a local production-mode preview.

## Confirm local behavior

With the API running, use another terminal:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/live"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/ready"

$agdaQuestion = @{ question = "What crops do people farm most in Kaduna?" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/questions" -Method Post -ContentType "application/json" -Body $agdaQuestion
```

Liveness reports `status: alive`. Core readiness should report `ready: true`,
`data_version: wave5_v1`, `release_state: stable`, `metric_version: 1.0.0` and
`registered_metrics: 18`. `/v1/health` is a readiness alias. `/v1/sources` describes
optional external-source availability; absent external snapshots do not make
the core unready.

The example question is covered by the
[user-question QA bank](../tests/qa/user_question_bank.py) and expects an answered
`crop_grower_share` result. For API follow-ups, send the returned `conversation_id`
with the next question. The web interface manages that ID for its current
conversation. Development API documentation is at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Run local validation

No running API server is needed for the backend suite. Stop the local API with
Ctrl+C and, from the repository root in the same configured terminal, run:

```powershell
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe tests/integration/run_backend_regression.py
.\.venv\Scripts\python.exe tests/integration/test_api_trusted_hosts.py
.\.venv\Scripts\python.exe tests/integration/test_manual_qa_regressions.py
.\.venv\Scripts\python.exe tests/qa/run_user_qa.py
```

These are the CI backend commands, with UTF-8 output enabled for Windows so
Unicode test output is handled consistently by child processes. They use local
test clients, fixtures and mocked integrations, including fake Redis and
provider/database substitutes.
Stop and inspect a failure before moving to the next command; do not treat the
last command's exit status as the result of all earlier checks.

Stop the frontend development server with Ctrl+C. In that terminal, still in
`apps/web`, run each frontend check separately:

```powershell
npm.cmd run lint
npm.cmd run build
```

Installing dependencies and building the frontend creates local environment and
build artifacts. These checks do not deploy the application. Run `git status`
afterward to review any workspace changes.

## Optional local services

Use dedicated local/development resources and the
[environment contract](environment_contract.md). They are not prerequisites for
the core workflow above.

| Capability | Configuration and prerequisites |
| --- | --- |
| Persistent conversations | `AGDA_CONVERSATION_BACKEND=redis` and a reachable development `AGDA_REDIS_URL`; Redis is checked during API startup, and conversations use the configured TTL |
| Analytics and feedback | A separate development PostgreSQL database with the application's schema, plus `AGDA_ANALYTICS_DATABASE_URL` on the API |
| Internal dashboard | The database above, a matching `AGDA_INTERNAL_ANALYTICS_TOKEN` on API and web, and a separate web `AGDA_INTERNAL_DASHBOARD_TOKEN`; see the web README |
| Saved external data | Completed development SQLite snapshots outside `data/releases/`, selected by `AGDA_FEWS_SNAPSHOT_PATH` and/or `AGDA_WEATHER_SNAPSHOT_PATH` |

The supplied [SQL bootstrap](sql/staging_analytics_schema.sql) is guarded for a
verified staging database; it is not a general development migration or a
production restore script. Database provisioning is a separate setup step.
Startup restoration reads saved snapshots without fetching providers.

Provider probes, ingestion, refresh and hosted validation tools are separate
from the local checks. In particular, `validate_phase29_release.py` sends hosted
analytical requests, and `validate_phase29_persistence.py` creates synthetic
staging questions and feedback. Ingestion/refresh tools can contact providers
and write snapshot stores. Do not run those tools as part of this core quick start
or use preserved backup artifacts as writable development stores.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `py` is not found | Use the path to an installed Python 3.12 interpreter to create `.venv`; keep subsequent installs in that environment |
| PowerShell blocks `npm.ps1` | Use `npm.cmd`; no execution-policy change is needed |
| Imports come from another checkout | Use this checkout's `.venv`, reinstall `-e . --no-deps` from its root, and set the current shell's `PYTHONPATH` to that root as above |
| Backend settings appear unchanged | Set process variables in the terminal that launches the API, then restart; copying a root `.env` file alone does not load it |
| HTTP 400 from the local API | Check `AGDA_ALLOWED_HOSTS` for the hostname in use; local tests use `testserver` |
| Redis connection failure during startup | For the core workflow, use the reset block and `memory`; for the optional Redis workflow, verify the development connection |
| Questions show offline/503 in the browser | Check API readiness, the listening port and the web server's `AGDA_API_URL`; see the web README for production-mode requirements |
| External answers unavailable or feedback returns 503 | External snapshots and feedback storage are optional and disabled by the core setup |
| Dashboard returns 401/503 | Check dashboard versus backend token roles and the analytics database setup described in the web README |

For deployment evidence and preserved-data boundaries, use the
[Phase 29 record](phase29_closure.md) and
[hosted-data preservation record](hosted_data_preservation.md).
