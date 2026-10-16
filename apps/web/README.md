# AgDA web application

This Next.js application provides AgDA's question-and-answer interface, feedback
controls and internal analytics dashboard. Browser requests go to same-origin
server routes, which call the FastAPI backend. The current dependencies are
defined in [package.json](package.json) and locked in
[package-lock.json](package-lock.json).

Start with the [local-development guide](../../docs/local_development.md) for the
Python environment, backend startup, optional services and complete validation
commands. The [root README](../../README.md) describes AgDA's supported questions
and analytical limitations.

## Run in development

Use Node.js 24 with npm, matching CI. With the API running on port 8000, open a
dedicated local terminal in `apps/web`:

```powershell
npm.cmd ci
$env:AGDA_API_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

Open [http://localhost:3000](http://localhost:3000). On macOS/Linux use `npm` and
the shell's equivalent environment assignment. In PowerShell, `npm.cmd` avoids
the execution-policy restriction on `npm.ps1`.

The core development flow needs no web tokens. Questions use the local API's
memory conversation store by default. Feedback storage and the internal
dashboard require the optional PostgreSQL setup; feedback returns 503 when the
API database URL is unset. Reloading the browser resets the current interface
state; restarting a memory-backed API loses its stored conversation context.

## Web configuration

Use process variables or an uncommitted `apps/web/.env.local`, alongside
`package.json`, not inside `src/`. Review the existing file before changing it.
The [.env.example](.env.example) documents the supported settings. Process
variables take precedence over environment files. Restart the local web server
after configuration changes.

| Variable | Purpose |
| --- | --- |
| `AGDA_API_URL` | Absolute HTTP(S) FastAPI base URL. Defaults to `http://127.0.0.1:8000` outside production mode; required for production-mode proxy requests |
| `AGDA_INTERNAL_ANALYTICS_TOKEN` | Backend analytics credential held by the web server; must match the API's value in the same environment |
| `AGDA_INTERNAL_DASHBOARD_TOKEN` | Separate web-only operator credential entered into the dashboard |

Keep these values server-side and never prefix them with `NEXT_PUBLIC_`. Redis,
database and operations credentials do not belong on the web service. The
[environment contract](../../docs/environment_contract.md) is the complete
configuration and environment-isolation reference.

## Server routes

| Browser request | FastAPI destination |
| --- | --- |
| `GET /api/health` | `GET /v1/health` (core readiness) |
| `POST /api/questions` | `POST /v1/questions` |
| `POST /api/feedback` | `POST /v1/feedback` |
| `GET /api/internal/analytics?resource=<name>` | `GET /v1/internal/analytics/<name>` after dashboard authentication |

Analytics resources are limited to `overview`, `daily`, `metrics`, `statuses`
and `feedback-reasons`. The proxies use `no-store` upstream fetches and preserve
backend status codes when parsing succeeds. Connection, configuration or
response-parsing failures return 503. The question proxy forwards request IDs.
The explicit backend `/v1/external-queries` endpoint has no dedicated web proxy.

## Internal analytics dashboard

Dashboard setup requires a dedicated development analytics database with the
application schema and `AGDA_ANALYTICS_DATABASE_URL` configured on the API.
Configure the same `AGDA_INTERNAL_ANALYTICS_TOKEN` on API and web, then set a
different `AGDA_INTERNAL_DASHBOARD_TOKEN` on the web server. Keep production and
staging credentials separate from development.

Visit [http://localhost:3000/internal/analytics](http://localhost:3000/internal/analytics)
and enter the dashboard token. The browser sends it in
`X-AgDA-Dashboard-Token`; the web server authenticates it and supplies the separate
backend credential in `X-AgDA-Internal-Token`. The backend analytics token is not
sent to the browser. The entered dashboard token is kept in React component
state, not local storage or a query URL. Proxied analytics responses use
`Cache-Control: no-store`.

The default core setup leaves this dashboard disabled. A 401 can mean a missing
or incorrect dashboard token, or a mismatch in the backend analytics token. A
503 can mean the web analytics token or API database/token is missing, the
database query failed, or the API is unreachable. Inspect the relevant layer
without logging credential values.

## Validate and preview a production build locally

Stop the frontend development server with Ctrl+C. From `apps/web`, run the
following commands one at a time, stopping if a check fails:

```powershell
npm.cmd run lint
npm.cmd run build
$env:AGDA_API_URL = "http://127.0.0.1:8000"
npm.cmd run start
```

Keep the local API running for proxy requests. `start` serves a completed
production build and requires the prior build step. The API URL is required when
production-mode proxy handlers execute; a successful build alone does not prove
backend connectivity. Stop each long-running server with Ctrl+C before reusing
its port. These commands preview the frontend locally and do not deploy it.

If port 3000 is occupied, development can use `npm.cmd run dev -- --port 3001`.
For an offline/503 message, check the API's
[readiness endpoint](http://127.0.0.1:8000/v1/ready), then the web API URL and port.
If environment-file changes appear ineffective, check whether a process variable
overrides them and restart the web server.

## Source map

| Path | Responsibility |
| --- | --- |
| [src/app/page.tsx](src/app/page.tsx) | Main question interface, conversation state, answers and feedback controls |
| [src/app/internal/analytics/page.tsx](src/app/internal/analytics/page.tsx) | Authenticated operator dashboard |
| [src/app/api](src/app/api) | Server-side proxy routes |
| [src/lib/server-config.ts](src/lib/server-config.ts) | API URL resolution and validation |
| [src/app/layout.tsx](src/app/layout.tsx) and [src/app/globals.css](src/app/globals.css) | Shared application shell and styles |
| [next.config.ts](next.config.ts) | Next.js configuration |

Before changing Next.js code, follow [AGENTS.md](AGENTS.md) and the relevant
installed Next.js guides. The [documentation index](../../docs/README.md) links
the dated deployment records; the [environment contract](../../docs/environment_contract.md)
defines manual production promotion safeguards.
