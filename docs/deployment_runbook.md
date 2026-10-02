\# AgDA Deployment Runbook



\## Deployment Policy



AgDA uses a controlled staging-to-production deployment workflow.



Production must not automatically deploy changes from GitHub.



\---



\## Development Flow



1\. Create a feature or maintenance branch from `main`.



2\. Make and validate changes locally.



3\. Push the branch to GitHub.



4\. Open a pull request targeting `main`.



5\. GitHub Actions must pass:



&#x20;  - Backend regression and QA

&#x20;  - Frontend lint and production build



6\. Merge the pull request only after all required checks pass.



\---



\## Staging Deployment



The Railway `staging` environment is connected to GitHub branch `main`.



Staging configuration:



\- Auto deploy: enabled

\- Wait for CI: enabled

\- Production promotion: manual



\### API watch paths



\- `/apps/api/\*\*`

\- `/packages/\*\*`

\- `/data/releases/\*\*`

\- `/requirements.txt`

\- `/requirements-production.txt`

\- `/pyproject.toml`

\- `/.gitattributes`



\### Web watch paths



\- `/apps/web/\*\*`



Changes outside these paths may be intentionally skipped by Railway.



\---



\## Staging Validation



After a relevant staging deployment:



1\. Confirm `api` is Online.

2\. Confirm `web` is Online.

3\. Check:



&#x20;  `https://web-staging-4660.up.railway.app/api/health`



4\. Confirm:



&#x20;  - status: `ready`

&#x20;  - environment: `staging`

&#x20;  - data version: `wave5\_v1`

&#x20;  - release state: `stable`

&#x20;  - metric version: `1.0.0`

&#x20;  - registered metrics: `18`



5\. Run an analytical smoke test.



6\. Run a conversational follow-up test.



7\. Run at least one safety/guardrail test when routing or answering logic changed.



8\. Check the browser UI when frontend code changed.



\---



\## Production Promotion



Production is intentionally not connected to a Git branch for automatic deployment.



After staging validation passes:



1\. Open Railway.

2\. Switch to the `production` environment.

3\. Deploy the latest validated commit manually.

4\. Confirm both services become Online.

5\. Confirm the deployed commit matches the staging-validated commit.



Do not promote a different commit from the one validated in staging.



\---



\## Production Validation



After production deployment:



1\. Check:



&#x20;  `https://web-production-ba3f9.up.railway.app/api/health`



2\. Confirm:



&#x20;  - status: `ready`

&#x20;  - environment: `production`

&#x20;  - data version: `wave5\_v1`

&#x20;  - release state: `stable`

&#x20;  - metric version: `1.0.0`

&#x20;  - registered metrics: `18`



3\. Test:



&#x20;  `What are farmers mostly growing in Kaduna?`



4\. Follow with:



&#x20;  `What about rice?`



5\. Confirm conversation context is retained.



6\. Run a safety check such as:



&#x20;  `Does that mean rice is more profitable there?`



&#x20;  Expected behavior: AgDA must not fabricate profitability.



7\. Confirm Better Stack reports:



&#x20;  `AgDA Production Health — Up`



\---



\## Rollback



If production fails after promotion:



1\. Do not modify the stable release artifacts.

2\. Identify the previous known-good production commit.

3\. Redeploy that commit in Railway.

4\. Confirm `/api/health` returns `ready`.

5\. Record the failed deployment and root cause before attempting another release.



\---



\## Production Constraints



The API should remain:



\- private to the Railway network;

\- single-replica while conversation context is process-scoped;

\- protected by trusted-host validation;

\- configured with production documentation disabled.



The public entry point is the Next.js web service.



\---



\## Monitoring



Operational monitoring includes:



\- Railway project usage;

\- Railway API memory;

\- Railway CPU;

\- Web request count;

\- Web 5xx rate;

\- Web latency;

\- Railway deployment/crash notifications;

\- Better Stack external uptime monitoring;

\- AgDA request-ID correlation.



\---



\## Rule



No production deployment should occur unless:



\*\*CI passed → staging deployed → staging validated → exact validated commit promoted.\*\*

