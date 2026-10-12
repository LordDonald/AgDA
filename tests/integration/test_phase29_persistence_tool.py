"""Local safety checks for the staging-only persistence proof; no live services."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from unittest import TestCase, main
from unittest.mock import Mock, patch

import fakeredis

# Tooling is intentionally outside installed packages; direct script execution
# must resolve this checkout without relying on an inherited PYTHONPATH.
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from packages.answering.conversations import RedisConversationStore
from packages.contracts.question import QuestionInterpretation, QuestionSpecification
from tools import validate_phase29_persistence as proof


DEPLOYMENT = "11111111-1111-1111-1111-111111111111"
PREVIOUS = "22222222-2222-2222-2222-222222222222"
PROOF_ID = "p29_" + "a" * 32
ENV = {
    "AGDA_ENV": "staging", "RAILWAY_ENVIRONMENT_NAME": "staging",
    "AGDA_CONVERSATION_BACKEND": "redis", "AGDA_REDIS_URL": "redis://example.invalid",
    "AGDA_ANALYTICS_DATABASE_URL": "postgresql://example.invalid",
    "AGDA_INTERNAL_ANALYTICS_TOKEN": "synthetic-test-token", "RAILWAY_DEPLOYMENT_ID": DEPLOYMENT,
}


def analytics_rows():
    """Valid aggregates for one synthetic answered question with unclear feedback."""
    usage = {
        "total_questions": 1, "answered_count": 1, "clarification_count": 0,
        "reframe_count": 0, "unsupported_count": 0, "follow_up_count": 0,
        "follow_up_rate_pct": 0.0, "visualization_count": 1,
        "avg_processing_ms": 10.0, "p95_processing_ms": 10.0,
    }
    return {
        "overview": [{**usage, "feedback_count": 1, "helpful_count": 0,
                      "not_helpful_count": 1, "helpful_rate_pct": 0.0}],
        "daily": [{"usage_date": "2026-10-12", **usage}],
        "metrics": [{"metric_id": "crop_grower_share", "question_count": 1,
                     "follow_up_count": 0, "avg_processing_ms": 10.0, "p95_processing_ms": 10.0,
                     "feedback_count": 1, "helpful_count": 0, "not_helpful_count": 1,
                     "helpful_rate_pct": 0.0}],
        "statuses": [{"status": "answered", "question_count": 1, "share_pct": 100.0}],
        "feedback-reasons": [{"reason_code": "unclear", "feedback_count": 1, "share_pct": 100.0}],
    }


def analytics_client(rows):
    client = Mock()
    client.RESOURCES = proof.StagingHTTP.RESOURCES

    def request(path, **kwargs):
        if kwargs.get("expected_status") == 401:
            return None
        resource = path.rsplit("/", 1)[1]
        return rows[resource][0] if resource == "overview" else rows[resource]

    client.request.side_effect = request
    return client


class PersistenceProofSafetyTests(TestCase):
    def test_environment_refusal_happens_before_http(self):
        for changes in ({"AGDA_ENV": "production"}, {"RAILWAY_ENVIRONMENT_NAME": "production"},
                        {"AGDA_CONVERSATION_BACKEND": "memory"}, {"AGDA_REDIS_URL": ""}):
            with self.subTest(changes=changes), patch.dict(proof.os.environ, {**ENV, **changes}, clear=True), \
                    patch.object(proof, "StagingHTTP") as http, redirect_stdout(io.StringIO()):
                self.assertEqual(proof.main(["--phase", "before"]), 1)
                http.assert_not_called()

    def test_restart_proof_requires_changed_container(self):
        self.assertEqual(proof.validate_environment(ENV, "after", PREVIOUS), (DEPLOYMENT, 8000, 86400))
        for previous in (None, DEPLOYMENT, "untrusted-value"):
            with self.subTest(previous=previous), self.assertRaises(proof.CheckFailure):
                proof.validate_environment(ENV, "after", previous)

    def test_invalid_arguments_never_echo_secrets(self):
        output = io.StringIO()
        secret_url = "postgresql://user:do-not-echo@private.invalid/database"
        with redirect_stdout(output):
            self.assertEqual(proof.main(["--phase", "before", "--database", secret_url]), 1)
        self.assertNotIn(secret_url, output.getvalue())
        self.assertNotIn("do-not-echo", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["status"], "failed")

    def test_http_gate_and_path_allowlist(self):
        client = proof.StagingHTTP(8000, "test-token")
        with patch.object(client.opener, "open") as opened:
            with self.assertRaises(proof.CheckFailure):
                client.request("/v1/questions", payload={"question": "synthetic"})
            client.verified = True
            with self.assertRaises(proof.CheckFailure):
                client.request("/v1/internal/external-sources/weather/refresh", payload={})
            with self.assertRaises(proof.CheckFailure):
                client.request("/v1/health", authenticated=True)
            opened.assert_not_called()
        self.assertIsNone(proof.NoRedirect().redirect_request(None, None, 302, None, None, "https://example.invalid"))

    def test_health_failure_revokes_authorization(self):
        client = proof.StagingHTTP(8000, "test-token")
        client.verified = True
        with patch.object(client, "request", return_value={"environment": "production", "ready": True}), \
                self.assertRaises(proof.CheckFailure):
            client.health()
        self.assertFalse(client.verified)

    def test_postgres_connection_is_read_only(self):
        with patch.dict(proof.os.environ, ENV, clear=True), \
                patch.object(proof.StagingHTTP, "health"), patch.object(proof, "run_proof"), \
                patch("redis.Redis.from_url"), patch("psycopg.connect") as connect, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(proof.main(["--phase", "before", "--proof-id", PROOF_ID]), 0)
        options = connect.call_args.kwargs
        self.assertTrue(options["autocommit"])
        self.assertIn("default_transaction_read_only=on", options["options"])
        self.assertIn("statement_timeout=5000", options["options"])

    def test_driver_failure_is_sanitized(self):
        output = io.StringIO()
        with patch.dict(proof.os.environ, ENV, clear=True), \
                patch.object(proof.StagingHTTP, "health"), \
                patch("redis.Redis.from_url", side_effect=RuntimeError("PASSWORD=never-print-this")), \
                redirect_stdout(output):
            self.assertEqual(proof.main(["--phase", "before"]), 1)
        self.assertNotIn("PASSWORD", output.getvalue())
        self.assertNotIn("never-print-this", output.getvalue())

    def test_stored_context_requires_ttl_and_valid_schema(self):
        conversation, _, _ = proof.proof_identifiers(PROOF_ID)
        redis = fakeredis.FakeRedis(decode_responses=True)
        store = RedisConversationStore(client=redis, ttl_seconds=60, key_prefix="agda:staging:conversation")
        specification = QuestionSpecification(metric_id="crop_grower_share", operation="rank",
                                             filters={"crop": "RICE"}, group_by="state", metric_version="1.0.0")
        interpretation = QuestionInterpretation(
            question="Synthetic RICE question", normalized_question="synthetic rice question",
            status="interpreted", metric_id="crop_grower_share", operation="rank", group_by="state",
            filters={"crop": "RICE"}, entities={"crop": ["RICE"]}, metric_candidates=["crop_grower_share"],
            question_specification=specification,
        )
        store.put(conversation, interpretation)
        self.assertGreater(proof.check_redis(redis, conversation, 60, False), 0)
        key = "agda:staging:conversation:" + conversation
        redis.persist(key)
        with self.assertRaises(proof.CheckFailure):
            proof.check_redis(redis, conversation, 60, False)
        redis.expire(key, 60)
        with self.assertRaises(proof.CheckFailure):
            proof.check_redis(redis, conversation, 60, True)
        value = json.loads(redis.get(key))
        value["schema_version"] = 2
        redis.set(key, json.dumps(value), ex=60)
        with self.assertRaises(proof.CheckFailure):
            proof.check_redis(redis, conversation, 60, False)

    def test_event_proof_rejects_duplicates_and_wrong_followup(self):
        _, request_id, _ = proof.proof_identifiers(PROOF_ID)
        row = {"event_name": "agda_question", "request_id": request_id, "status": "answered",
               "metric_id": "crop_grower_share", "operation": "rank", "was_follow_up": False,
               "data_version": "wave5_v1", "metric_version": "1.0.0"}
        with patch.object(proof, "query", return_value=[row]):
            proof.check_event(None, request_id, False)
            with self.assertRaises(proof.CheckFailure):
                proof.check_event(None, request_id, True)
        with patch.object(proof, "query", return_value=[row, row]), self.assertRaises(proof.CheckFailure):
            proof.check_event(None, request_id, False)
        with self.assertRaises(proof.CheckFailure):
            proof.proof_identifiers("p29_'; DELETE FROM product_events; --")

    def test_api_views_must_include_existing_sql_proof_evidence(self):
        for resource in ("daily", "metrics", "statuses", "feedback-reasons"):
            with self.subTest(resource=resource):
                sql_rows = analytics_rows()
                api_rows = analytics_rows()
                api_rows[resource] = []
                with patch.object(proof, "query", side_effect=list(sql_rows.values())), \
                        self.assertRaises(proof.CheckFailure):
                    proof.check_views(None, analytics_client(api_rows), phase="before")

    def test_nonempty_api_views_must_include_matching_positive_evidence(self):
        changes = {
            "overview": {"total_questions": 0},
            "daily": {"total_questions": 0},
            "metrics": {"metric_id": "unrelated_metric"},
            "statuses": {"status": "unsupported"},
            "feedback-reasons": {"reason_code": "other"},
        }
        for resource, change in changes.items():
            with self.subTest(resource=resource):
                sql_rows = analytics_rows()
                api_rows = analytics_rows()
                api_rows[resource][0].update(change)
                with patch.object(proof, "query", side_effect=list(sql_rows.values())), \
                        self.assertRaises(proof.CheckFailure):
                    proof.check_views(None, analytics_client(api_rows), phase="before")

    def test_valid_views_pass_and_after_feedback_reasons_may_be_empty(self):
        for phase in ("before", "after"):
            with self.subTest(phase=phase):
                sql_rows = analytics_rows()
                api_rows = analytics_rows()
                if phase == "after":
                    sql_rows["feedback-reasons"] = []
                    api_rows["feedback-reasons"] = []
                with patch.object(proof, "query", side_effect=list(sql_rows.values())), \
                        redirect_stdout(io.StringIO()):
                    proof.check_views(None, analytics_client(api_rows), phase=phase)


if __name__ == "__main__":
    main()
