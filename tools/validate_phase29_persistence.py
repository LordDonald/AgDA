"""Prove staging conversation and analytics persistence across an API redeploy.

Run from the API container repository root with ``python -m
tools.validate_phase29_persistence --phase before``. Save the emitted proof_id and
deployment_id, redeploy the SAME verified release, then run ``--phase after
--proof-id ID --previous-deployment-id ID``. The separate release identity probe
must verify the source revision on both deployments; this tool cannot prove it.

Requires staging AGDA_ENV/RAILWAY_ENVIRONMENT_NAME, Redis conversation backend,
RAILWAY_DEPLOYMENT_ID, and environment-provided Redis/analytics/token settings.
Resource isolation must already be verified by the operator: database rows have
no environment discriminator. Credentials are never accepted as arguments.

This creates synthetic staging questions/feedback through loopback HTTP. Direct
Redis operations only read; direct PostgreSQL connections are read-only. It does
not restart services, initialize schemas, refresh providers, or delete evidence.
"""

import argparse
import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4


class CheckFailure(Exception):
    """Only constant, non-sensitive messages may be used."""


def require(condition, message):
    if not condition:
        raise CheckFailure(message)


def emit(check, **fields):
    print(json.dumps({"check": check, **fields}, separators=(",", ":")), flush=True)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise CheckFailure("Invalid proof arguments; use --help for supported options.")


def validate_environment(env, phase, previous_deployment):
    require(env.get("AGDA_ENV") == "staging" and env.get("RAILWAY_ENVIRONMENT_NAME") == "staging",
            "Both application and Railway environments must be exactly staging.")
    require(env.get("AGDA_CONVERSATION_BACKEND") == "redis", "Staging conversation backend must be redis.")
    for name in ("AGDA_REDIS_URL", "AGDA_ANALYTICS_DATABASE_URL", "AGDA_INTERNAL_ANALYTICS_TOKEN"):
        require(bool(env.get(name, "").strip()), "Required staging persistence settings are missing.")
    deployment = env.get("RAILWAY_DEPLOYMENT_ID", "")
    pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    require(bool(re.fullmatch(pattern, deployment)), "A valid container deployment identity is required.")
    if phase == "after":
        require(bool(re.fullmatch(pattern, previous_deployment or "")) and previous_deployment != deployment,
                "After proof requires a different deployment and the prior deployment identity.")
    else:
        require(previous_deployment is None, "Prior deployment identity is only valid for after proof.")
    port = env.get("PORT", "8000")
    ttl = env.get("AGDA_CONVERSATION_TTL_SECONDS", "86400")
    require(bool(re.fullmatch(r"[0-9]{1,5}", port)) and 1 <= int(port) <= 65535, "Invalid API port.")
    require(bool(re.fullmatch(r"[0-9]{1,9}", ttl)) and int(ttl) > 0, "Invalid conversation TTL.")
    return deployment, int(port), int(ttl)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class StagingHTTP:
    RESOURCES = ("overview", "daily", "metrics", "statuses", "feedback-reasons")

    def __init__(self, port, token):
        self.origin = f"http://127.0.0.1:{port}"
        self.token = token
        self.verified = False
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, *, payload=None, request_id=None, authenticated=False, expected_status=200):
        method = "GET" if payload is None else "POST"
        require(self.verified or (method == "GET" and path == "/v1/health"),
                "Staging health must pass before other HTTP requests.")
        reads = ("/v1/health",) + tuple("/v1/internal/analytics/" + x for x in self.RESOURCES)
        require((method == "GET" and path in reads)
                or (method == "POST" and path in ("/v1/questions", "/v1/feedback")),
                "HTTP path is outside the persistence proof scope.")
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if request_id:
            headers["X-Request-ID"] = request_id
        if authenticated:
            require(path.startswith("/v1/internal/analytics/"), "Token is restricted to analytics reads.")
            headers["X-AgDA-Internal-Token"] = self.token
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(self.origin + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(request, timeout=20) as response:
                require(response.status == expected_status, "Unexpected HTTP response status.")
                if request_id:
                    require(response.headers.get("X-Request-ID") == request_id, "Request identity changed.")
                body = response.read(2 * 1024 * 1024 + 1)
        except HTTPError as error:
            status = error.code
            error.close()
            require(status == expected_status, "Unexpected HTTP error status.")
            return None
        except (URLError, TimeoutError, OSError):
            raise CheckFailure("Local API request failed or timed out.") from None
        require(len(body) <= 2 * 1024 * 1024, "HTTP response exceeded proof limits.")
        return json.loads(body)

    def health(self):
        self.verified = False
        body = self.request("/v1/health")
        require(body.get("environment") == "staging" and body.get("ready") is True
                and body.get("status") == "ready", "Staging core is not ready.")
        require(body.get("data_version") == "wave5_v1" and body.get("release_state") == "stable"
                and body.get("metric_version") == "1.0.0" and body.get("registered_metrics") == 18,
                "Stable Wave5 release contract changed.")
        require(body.get("external_sources", {}).get("affects_core_readiness") is False,
                "External-source readiness independence changed.")
        self.verified = True


def proof_identifiers(proof_id):
    require(bool(re.fullmatch(r"p29_[0-9a-f]{32}", proof_id)), "Invalid synthetic proof identifier.")
    return "conv_" + proof_id, "req_" + proof_id + "_before", "req_" + proof_id + "_after"


def check_answer(answer, conversation, follow_up):
    require(answer.get("status") == "answered" and answer.get("conversation_id") == conversation,
            "Synthetic question was not answered in the expected conversation.")
    require(answer.get("data_version") == "wave5_v1" and answer.get("metric_version") == "1.0.0",
            "Synthetic question changed Wave5 provenance.")
    specification = answer.get("question_specification") or {}
    expected_filters = {"crop": "RICE", "state": "Kaduna"} if follow_up else {"crop": "RICE"}
    require(specification.get("metric_id") == "crop_grower_share"
            and specification.get("operation") == ("value" if follow_up else "rank")
            and specification.get("filters") == expected_filters,
            "Persisted conversation context was not interpreted correctly.")


def check_redis(redis_client, conversation, ttl_limit, follow_up):
    key = "agda:staging:conversation:" + conversation
    value = redis_client.get(key)
    require(value is not None, "Synthetic conversation is missing from staging Redis.")
    stored = json.loads(value)
    require(stored.get("schema_version") == 1, "Redis conversation schema changed.")
    from packages.contracts.question import QuestionInterpretation
    interpretation = QuestionInterpretation.model_validate(stored.get("last_interpretation"))
    expected_filters = {"crop": "RICE", "state": "Kaduna"} if follow_up else {"crop": "RICE"}
    require(interpretation.status.value == "interpreted" and interpretation.question_specification is not None
            and interpretation.question_specification.filters == expected_filters
            and interpretation.question_specification.metric_id == "crop_grower_share"
            and interpretation.question_specification.operation.value == ("value" if follow_up else "rank"),
            "Redis conversation does not contain the expected analytical context.")
    ttl = redis_client.ttl(key)
    require(0 < ttl <= ttl_limit, "Redis conversation lacks the configured expiration.")
    return ttl


def query(connection, sql, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, parameters)
        return cursor.fetchall()


EVENT_SQL = """SELECT event_name, request_id, status, metric_id, operation,
    was_follow_up, data_version, metric_version FROM product_events
    WHERE request_id = %s AND event_name = 'agda_question'"""
FEEDBACK_SQL = """SELECT rating, reason_code, created_at, updated_at
    FROM product_feedback WHERE request_id = %s"""


def check_event(connection, request_id, follow_up, *, wait=False):
    deadline = time.monotonic() + (15 if wait else 0)
    while True:
        rows = query(connection, EVENT_SQL, (request_id,))
        if rows or time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    require(len(rows) == 1, "Expected exactly one durable synthetic question event.")
    row = rows[0]
    require(row == {"event_name": "agda_question", "request_id": request_id, "status": "answered",
                    "metric_id": "crop_grower_share", "operation": "value" if follow_up else "rank",
                    "was_follow_up": follow_up, "data_version": "wave5_v1", "metric_version": "1.0.0"},
            "Durable question event does not match the analytical response.")


def check_feedback(connection, request_id, helpful):
    rows = query(connection, FEEDBACK_SQL, (request_id,))
    require(len(rows) == 1, "Expected one durable synthetic feedback record.")
    row = rows[0]
    require(row["rating"] == ("helpful" if helpful else "not_helpful")
            and row["reason_code"] == (None if helpful else "unclear")
            and row["created_at"] is not None and row["updated_at"] >= row["created_at"],
            "Durable feedback fields or timestamp defaults changed.")


def check_view_evidence(resource, rows, *, phase):
    """Both SQL and HTTP must contain positive synthetic proof evidence."""
    if resource == "overview":
        require(len(rows) == 1 and rows[0]["total_questions"] >= 1,
                "Analytics overview does not contain the proof event.")
    if resource == "daily":
        require(any(row["total_questions"] >= 1 for row in rows),
                "Daily analytics omitted the proof event.")
    if resource == "metrics":
        require(any(row["metric_id"] == "crop_grower_share" and row["question_count"] >= 1 for row in rows),
                "Metric analytics omitted the proof event.")
    if resource == "statuses":
        require(any(row["status"] == "answered" and row["question_count"] >= 1 for row in rows),
                "Status analytics omitted the proof event.")
    if resource == "feedback-reasons" and phase == "before":
        require(any(row["reason_code"] == "unclear" and row["feedback_count"] >= 1 for row in rows),
                "Feedback analytics omitted the synthetic reason.")


def check_views(connection, client, *, phase):
    from packages.contracts.internal_analytics import (
        AnalyticsOverview, AnalyticsDailyUsage, AnalyticsMetricUsage,
        AnalyticsStatusSummary, AnalyticsFeedbackReason,
    )
    models = (AnalyticsOverview, AnalyticsDailyUsage, AnalyticsMetricUsage,
              AnalyticsStatusSummary, AnalyticsFeedbackReason)
    names = ("analytics_overview", "analytics_daily_usage", "analytics_metric_usage",
             "analytics_status_summary", "analytics_feedback_reasons")
    client.request("/v1/internal/analytics/overview", expected_status=401)
    counts = []
    for name, resource, model in zip(names, client.RESOURCES, models):
        # Every interpolated table name is a fixed local allowlist entry.
        rows = query(connection, "SELECT * FROM " + name)
        for row in rows:
            model.model_validate(row)
        check_view_evidence(resource, rows, phase=phase)
        payload = client.request("/v1/internal/analytics/" + resource, authenticated=True)
        api_rows = [payload] if resource == "overview" else payload
        require(isinstance(api_rows, list), "Unexpected analytics API collection shape.")
        for row in api_rows:
            model.model_validate(row)
        check_view_evidence(resource, api_rows, phase=phase)
        counts.append(len(rows))
    emit("analytics_views", status="passed", contracts=5, authorization="required", row_counts=counts)


def run_proof(client, redis_client, connection, *, phase, proof_id, ttl_limit):
    conversation, before_id, after_id = proof_identifiers(proof_id)
    client.health()
    redis_client.ping()
    if phase == "before":
        require(redis_client.get("agda:staging:conversation:" + conversation) is None
                and not query(connection, EVENT_SQL, (before_id,))
                and not query(connection, EVENT_SQL, (after_id,))
                and not query(connection, FEEDBACK_SQL, (before_id,)),
                "Proof identifier is already used; choose a new synthetic identifier.")
        answer = client.request("/v1/questions", request_id=before_id, payload={
            "question": "Which states have the highest grower share for RICE?", "conversation_id": conversation,
        })
        check_answer(answer, conversation, False)
        ttl = check_redis(redis_client, conversation, ttl_limit, False)
        check_event(connection, before_id, False, wait=True)
        response = client.request("/v1/feedback", payload={
            "request_id": before_id, "rating": "not_helpful", "reason_code": "unclear",
        })
        require(response.get("status") == "saved", "Synthetic feedback was not saved.")
        check_feedback(connection, before_id, False)
    else:
        # All original evidence must survive BEFORE issuing the follow-up.
        check_redis(redis_client, conversation, ttl_limit, False)
        check_event(connection, before_id, False)
        check_feedback(connection, before_id, False)
        require(not query(connection, EVENT_SQL, (after_id,)), "After proof has already run.")
        emit("pre_restart_records_survived", status="passed", conversation=True, event=True, feedback=True)
        answer = client.request("/v1/questions", request_id=after_id, payload={
            "question": "What about Kaduna?", "conversation_id": conversation,
        })
        check_answer(answer, conversation, True)
        ttl = check_redis(redis_client, conversation, ttl_limit, True)
        check_event(connection, after_id, True, wait=True)
        response = client.request("/v1/feedback", payload={"request_id": before_id, "rating": "helpful"})
        require(response.get("status") == "saved", "Synthetic feedback update was not saved.")
        check_feedback(connection, before_id, True)
        check_event(connection, before_id, False)
    check_views(connection, client, phase=phase)
    client.health()
    emit("staging_persistence", status="passed", phase=phase, redis_schema_version=1,
         redis_ttl_seconds=ttl, synthetic_question_events=1 if phase == "before" else 2,
         feedback_upsert="inserted" if phase == "before" else "updated", core_ready=True,
         data_version="wave5_v1", metric_version="1.0.0", registered_metrics=18,
         affects_core_readiness=False)


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--phase", required=True, choices=("before", "after"))
        parser.add_argument("--proof-id", help="Synthetic ID emitted by before; required for after.")
        parser.add_argument("--previous-deployment-id", help="Deployment identity emitted by before; required for after.")
        args = parser.parse_args(argv)
        deployment, port, ttl = validate_environment(os.environ, args.phase, args.previous_deployment_id)
        require(args.phase != "after" or args.proof_id is not None, "After proof requires the prior proof identifier.")
        proof_id = args.proof_id or "p29_" + uuid4().hex
        proof_identifiers(proof_id)
        # Imports/connections occur only after all staging/argument gates pass.
        import psycopg
        from psycopg.rows import dict_row
        from redis import Redis
        client = StagingHTTP(port, os.environ["AGDA_INTERNAL_ANALYTICS_TOKEN"])
        client.health()
        with Redis.from_url(os.environ["AGDA_REDIS_URL"], decode_responses=True,
                            socket_connect_timeout=5, socket_timeout=5) as redis_client:
            with psycopg.connect(os.environ["AGDA_ANALYTICS_DATABASE_URL"], connect_timeout=5,
                                 autocommit=True, row_factory=dict_row,
                                 options="-c default_transaction_read_only=on -c statement_timeout=5000") as connection:
                emit("phase29_persistence", status="started", phase=args.phase, proof_id=proof_id,
                     deployment_id=deployment, environment="staging")
                run_proof(client, redis_client, connection, phase=args.phase, proof_id=proof_id, ttl_limit=ttl)
        emit("phase29_persistence", status="passed", phase=args.phase, proof_id=proof_id,
             deployment_id=deployment, environment="staging")
        return 0
    except CheckFailure as error:
        emit("phase29_persistence", status="failed", reason=str(error))
    except Exception as error:
        # Exceptions may contain passwords, URLs, database details or raw payloads.
        emit("phase29_persistence", status="failed", reason="Persistence proof failed; details suppressed.",
             error_type=type(error).__name__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
