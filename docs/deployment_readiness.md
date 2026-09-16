\# AgDA Deployment Readiness



\## Status



AgDA has completed local production-environment preparation and production-mode

smoke testing.



This document defines the application artifacts required for deployment before

a hosting platform is selected.



\---



\## 1. Backend Runtime



Tested runtime:



\- Python 3.12.7

\- FastAPI 0.141.1

\- Uvicorn 0.52.4

\- DuckDB 1.5.5

\- Pandas 2.2.2

\- Pydantic 2.11.7

\- PyArrow 16.1.0



Production dependency lock:



`requirements-production.txt`



The project also retains `pyproject.toml` as its Python package definition.



\---



\## 2. Frontend Runtime



Frontend:



\- Next.js 16.3.4

\- React 19.2.8

\- React DOM 19.2.8

\- TypeScript

\- npm dependency lock via `apps/web/package-lock.json`



Production build command:



`npm run build`



Production start command:



`npm run start`



\---



\## 3. Runtime Data Release



The production application reads from:



`data/releases/`



The current stable release is:



\- Data version: `wave5\_v1`

\- Release state: `stable`

\- Metric version: `1.0.0`

\- Registered metrics: `18`



Current runtime release footprint:



\- 43 files

\- approximately 3.72 MB



The runtime loader resolves the stable release through:



`data/releases/stable\_release.json`



and validates the release manifest and checksums during startup.



\---



\## 4. Development Data Exclusion



The `03\_data/` directory contains development, inventory, QA, and release-building

artifacts.



It is not required by the normal application runtime.



Production deployment should package the validated `data/releases/` artifacts

rather than the full `03\_data/` workspace.



Release-building utilities may still depend on `03\_data/`, but those utilities

are not part of the normal production request path.



\---



\## 5. Backend Environment



Recommended production values:



\- `AGDA\_ENV=production`

\- `AGDA\_LOG\_LEVEL=WARNING`

\- `AGDA\_DOCS\_ENABLED=false`

\- `AGDA\_MAX\_REQUEST\_BYTES=16384`

\- `AGDA\_ALLOWED\_HOSTS=<deployment hostname>`

\- `AGDA\_SERVICE\_NAME=AgDA API`

\- `AGDA\_SERVICE\_VERSION=0.1.0`



Real environment files and secrets must not be committed.



\---



\## 6. Frontend Environment



Required in production:



`AGDA\_API\_URL=<FastAPI service URL>`



`AGDA\_API\_URL` remains server-side.



The browser communicates with the Next.js application, and Next.js proxies

requests to FastAPI.



Architecture:



Browser -> Next.js `/api/\*` -> FastAPI



\---



\## 7. API Security Boundary



FastAPI uses TrustedHostMiddleware.



Production hosts must be explicitly configured using `AGDA\_ALLOWED\_HOSTS`.



Interactive API documentation and OpenAPI output are disabled in production.



CORS is not enabled because the browser does not directly communicate with

FastAPI in the current architecture.



\---



\## 8. Production Startup



Backend development-equivalent production command:



`python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000`



The final port and process command may be adapted to the selected hosting

platform.



Frontend:



`npm run build`



then:



`npm run start`



The final deployment platform may supply its own port automatically.



\---



\## 9. Local Production Smoke Test



The following behavior has been validated:



\- FastAPI production startup

\- `/v1/live` returned HTTP 200

\- environment reported `production`

\- `/docs` returned HTTP 404

\- `/openapi.json` returned HTTP 404

\- Next.js `/api/health` successfully reached FastAPI

\- runtime loaded `wave5\_v1`

\- release state reported `stable`

\- all 18 registered metrics loaded

\- question submission through Next.js succeeded

\- browser question submission succeeded

\- conversational follow-up succeeded



Example production smoke question:



`What are farmers mostly growing in Kaduna?`



The system returned the validated Kaduna crop-grower ranking.



\---



\## 10. Runtime State Limitation



Conversation context is currently stored in process memory.



Consequences:



\- conversation state is lost when the backend process restarts;

\- multiple backend instances would not automatically share conversation state;

\- horizontal scaling requires shared conversation persistence in a future

&#x20; architecture.



For the initial single-instance MVP deployment, this is an accepted limitation.



\---



\## 11. Deployment Package



Required:



\- `apps/api/`

\- `apps/web/`

\- `packages/`

\- `data/releases/`

\- `pyproject.toml`

\- `requirements-production.txt`

\- frontend `package.json`

\- frontend `package-lock.json`

\- required documentation/configuration



Not required for normal production runtime:



\- `03\_data/`

\- Jupyter checkpoints

\- `node\_modules/`

\- `.next/` source-machine build artifacts

\- local `.env` files

\- test caches

\- virtual environments



\---



\## 12. Remaining Pre-Launch Work



Before final production launch:



1\. Select and configure hosting infrastructure.

2\. Perform staging deployment and remote smoke testing.

3\. Implement the persistent bottom chat composer UX.

4\. Perform final responsive/browser QA.

5\. Configure real production hostnames and environment variables.

6\. Perform final production launch validation.

