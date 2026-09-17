\# AgDA Staging Readiness



\## Status



\*\*Step 22: PASSED\*\*



AgDA has been successfully deployed to the Railway staging environment and

validated remotely through the public Next.js application.



\## Staging Architecture



Browser -> Railway Web -> Railway Private Network -> FastAPI -> wave5\_v1



The FastAPI service is not publicly exposed.



\## Validated Release



\- Data version: `wave5\_v1`

\- Release state: `stable`

\- Metric version: `1.0.0`

\- Registered metrics: `18`



\## Staging Validation Completed



\- Railway API deployment successful

\- Railway web deployment successful

\- API readiness healthcheck passed

\- Web public domain returned HTTP 200

\- Web-to-API private networking passed

\- Stable release checksum validation passed

\- Remote analytical question passed

\- Remote conversational follow-up passed

\- Desktop browser QA passed

\- 412px responsive QA passed

\- 390px responsive QA passed

\- Persistent follow-up composer implemented and validated

\- Full answer content remains accessible above the composer

\- Production-style dependency packaging validated



\## Deployment Controls



\- API is private-only

\- Web is publicly accessible

\- API documentation is disabled outside development

\- Trusted host validation is enabled

\- Runtime uses Python 3.12

\- Production dependencies are pinned

\- Stable release artifacts are preserved byte-for-byte through `.gitattributes`



\## Known MVP Limitation



Conversation context remains process-scoped and is therefore lost if the API

process restarts. Multiple API replicas would not share conversation state.



The initial MVP should therefore remain single-replica until shared

conversation persistence is introduced.



\## Decision



\*\*Staging readiness: GO\*\*



AgDA is ready to proceed to production-launch preparation.

