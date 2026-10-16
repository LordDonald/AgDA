# AgDA

AgDA is an evidence-backed agricultural question-answering application. It
answers bounded questions about Nigerian agricultural survey data and supports
separately attributed market-price observations and weather forecasts from saved
external snapshots.

The current answering path uses deterministic routing and analytical execution.
A Next.js web application sends questions through server-side routes to a
FastAPI backend. The backend loads the versioned Wave 5 Parquet release into
DuckDB and returns answers with their evidence, scope and limitations.

## Capabilities and evidence

| Area | Supported scope |
| --- | --- |
| Wave 5 analytics | Crop prevalence, observed yields, commercialization, food security, and community climate-risk perceptions within the registered metrics and release coverage |
| FEWS market prices | Saved Nigerian white-maize retail observations in NGN/kg, with exact selections and compatible market rankings |
| Open-Meteo weather | Saved hourly temperature, relative humidity and precipitation forecasts within the captured location and time coverage |
| Conversation and feedback | Contextual follow-up questions, feedback collection, and an optional authenticated internal analytics dashboard |

The stable core release is `wave5_v1`, with metric version `1.0.0` and 18 core
metrics. See the [release manifest](data/releases/wave5_v1/release_manifest.json)
and [Phase 29 validation record](docs/phase29_closure.md). External metrics and
snapshots are separate from that release; their availability does not determine
core readiness.

Examples from the [user-question QA bank](tests/qa/user_question_bank.py):

- What crops do people farm most in Kaduna?
- How much maize do farmers sell?
- Which states have the highest grower share for rice?

External queries require an available accepted snapshot. The
[Phase 28 external query contract](docs/phase28_external_capabilities.md)
describes selectors, operations and provenance for `POST /v1/external-queries`.

To assess AgDA's agricultural usefulness, use the
[agriculture evaluation guide](docs/agriculture_evaluation.md) or its
[shareable PDF](docs/agriculture_evaluation.pdf). They explain the aims,
capabilities and limitations, with sample questions and a feedback worksheet.

## Status and reading order

For system structure, read the [architecture guide](docs/architecture.md). For
the last recorded hosted topology and manual release process, read the
[deployment guide](docs/deployment.md).

1. Read the [Phase 29 closure record](docs/phase29_closure.md) for the completed
   release, final CI, merge provenance and persistence/browser checks. It records
   the closure commit separately from the last source-verified deployed runtime.
2. Read the [hosted-data preservation record](docs/hosted_data_preservation.md)
   for the six reported passing sets captured on October 16, 2026 UTC, master
   hashes, the excluded incomplete attempt, historical Redis coverage limits,
   the dated follow-up inspection and recovery limitations.
3. Use the [environment contract](docs/environment_contract.md) for configuration
   behavior and the [documentation index](docs/README.md) to navigate the rest.

Release, deployment and preservation results are dated evidence. They do not
establish current hosted availability. Preservation verification also does not
establish a completed restore drill.

## Run locally

The [local-development guide](docs/local_development.md) expands this quick start
with configuration, validation commands, optional services and troubleshooting.

The following Windows PowerShell example uses Python 3.12 and Node.js 24, matching
the [CI configuration](.github/workflows/ci.yml). Install Git, those runtimes and
npm before starting. Use a local development shell without hosted `AGDA_*`
settings; existing process variables override the application defaults.

From the repository root, create a Python environment and start the API:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8000
```

If the Windows Python launcher is unavailable, invoke your Python 3.12 interpreter
directly to create `.venv`. Leave the API running. In a second PowerShell
terminal, starting at the repository root:

```powershell
Set-Location apps/web
npm.cmd ci
npm.cmd run dev
```

Open the [web application](http://localhost:3000). Check
[core readiness](http://127.0.0.1:8000/v1/ready) or browse the development
[API documentation](http://127.0.0.1:8000/docs).

With development defaults, the web server uses `http://127.0.0.1:8000`,
conversations are held in memory, and the bundled core release needs no Redis,
PostgreSQL, external snapshots or LLM service. Conversation context is lost when
the API restarts. External data, persisted analytics and feedback storage need
separate setup.

The API reads process environment variables; it does not automatically load a
root `.env` file. Review the [backend examples](.env.example),
[web examples](apps/web/.env.example) and
[environment contract](docs/environment_contract.md) before enabling optional
services. Backend URLs and tokens belong on the server, never in `NEXT_PUBLIC_*`
variables. On macOS/Linux, use the equivalent Python 3.12 environment commands,
`.venv/bin/python`, and `npm` instead of the Windows executable paths above.

## Repository map

| Path | Purpose |
| --- | --- |
| [apps/web](apps/web) | Next.js interface, server-side API proxy and internal dashboard |
| [apps/api](apps/api) | FastAPI routes, runtime settings, health and persistence integration |
| [packages](packages) | Question routing, analytics, answer composition, contracts, release loading and external sources |
| [data/releases](data/releases) | Versioned analytical release artifacts, manifests and checksums |
| [tools](tools) | Source ingestion/refresh and release/persistence validation commands; some perform live operations |
| [tests](tests) | Backend regression tests and user/manual QA cases |
| [docs](docs/README.md) | Configuration, contracts, dated release evidence and preservation records |

The [CI workflow](.github/workflows/ci.yml) defines the exact dependency installs
and validation commands: backend regressions and QA, plus frontend lint and
production build. CI does not deploy production. Production promotion is manual
under the safeguards in the environment contract.

## Analytical boundaries

- Answers describe supported evidence. Observed yields are not agronomic
  potential, descriptive comparisons do not establish causation, and the system
  does not provide individual planting prescriptions or complete profitability
  estimates.
- Wave 5 community climate-risk perceptions and Open-Meteo forecasts have
  different meanings. Forecasts are model outputs, not observed weather.
- External answers stay within saved coverage and retain source and time
  provenance. Retrieval freshness does not establish recent market observations
  or forecast accuracy. Request-time queries do not fetch providers, expand
  coverage or silently join external data to Wave 5.
- Unsupported or ambiguous requests may require clarification or reframing
  rather than produce an answer.
