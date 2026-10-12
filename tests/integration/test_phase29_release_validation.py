"""Offline safety checks for the explicit-environment release validation tool."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

# Tooling is intentionally outside installed packages; direct script execution
# must resolve this checkout without relying on an inherited PYTHONPATH.
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from tools import validate_phase28_staging as staging
from tools import validate_phase29_release as release


def health(environment="staging", **changes):
    return {
        "environment": environment, "ready": True, "status": "ready",
        "data_version": "wave5_v1", "release_state": "stable", "metric_version": "1.0.0",
        "registered_metrics": 18, "external_sources": {"affects_core_readiness": False},
        **changes,
    }


def response(body):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.status = 200
    result.read.return_value = json.dumps(body).encode("utf-8")
    return result


class ReleaseValidationTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)
        self.opener = Mock()
        self.patch_opener = patch.object(staging, "build_opener", return_value=self.opener)
        self.patch_opener.start()
        self.addCleanup(self.patch_opener.stop)

    def client(self, environment="staging"):
        return release.ReleaseClient("http://127.0.0.1:8000", expected_environment=environment)

    def assert_post_refused(self, client):
        before = self.opener.open.call_count
        with self.assertRaises(staging.CheckFailure):
            client.request("/v1/questions", payload={"question": "Which states have the lowest maize yields?"})
        self.assertEqual(self.opener.open.call_count, before)

    def test_missing_or_invalid_explicit_environment_never_makes_a_request(self):
        for args in ([], ["--expected-environment", "Production"], ["--expected-environment", ""]):
            with self.subTest(args=args):
                self.assertEqual(release.main(args), 1)
        self.opener.open.assert_not_called()
        for line in self.output.getvalue().splitlines():
            self.assertEqual(json.loads(line)["status"], "failed")

    def test_client_requires_explicit_environment_and_initial_health(self):
        with self.assertRaises(TypeError):
            release.ReleaseClient("http://127.0.0.1:8000")
        with self.assertRaises(staging.CheckFailure):
            self.client(None)
        self.assert_post_refused(self.client())
        self.opener.open.assert_not_called()

    def test_missing_or_mismatched_health_environment_never_allows_post(self):
        for expected, actual in (("staging", None), ("production", None),
                                 ("staging", "production"), ("production", "staging"),
                                 ("production", "Production")):
            with self.subTest(expected=expected, actual=actual):
                client = self.client(expected)
                self.opener.open.return_value = response(health(actual))
                with self.assertRaises(staging.CheckFailure):
                    client.health("core_before")
                self.assertFalse(client.staging_verified)
                self.assert_post_refused(client)
        self.assertTrue(all(call.args[0].method == "GET" for call in self.opener.open.call_args_list))

    def test_every_core_contract_failure_keeps_post_gate_closed(self):
        changes = (
            {"ready": False}, {"status": "degraded"}, {"data_version": "external"},
            {"release_state": "candidate"}, {"metric_version": "2.0.0"},
            {"registered_metrics": 17}, {"external_sources": {"affects_core_readiness": True}},
            {"external_sources": {}},
        )
        for changed in changes:
            with self.subTest(changed=changed):
                client = self.client("production")
                self.opener.open.return_value = response(health("production", **changed))
                with self.assertRaises(staging.CheckFailure):
                    client.health("core_before")
                self.assert_post_refused(client)

    def test_exact_health_allows_analytical_post_in_each_selected_environment(self):
        for environment in ("staging", "production"):
            with self.subTest(environment=environment):
                client = self.client(environment)
                self.opener.open.side_effect = [response(health(environment)), response({"status": "answered"})]
                client.health("core_before")
                client.request("/v1/questions", payload={"question": "Which states have the lowest maize yields?"})
                self.assertEqual(self.opener.open.call_args.args[0].method, "POST")

    def test_external_unavailable_is_non_blocking_when_core_guards_hold(self):
        client = self.client("production")
        self.opener.open.return_value = response(health("production", external_sources={
            "affects_core_readiness": False, "status": "unavailable", "fresh_sources": 0,
        }))
        client.health("core_before")
        self.assertTrue(client.staging_verified)

    def test_failed_revalidation_revokes_previously_open_gate(self):
        client = self.client()
        self.opener.open.side_effect = [response(health()), response(health("production"))]
        client.health("core_before")
        with self.assertRaises(staging.CheckFailure):
            client.health("core_after")
        self.assert_post_refused(client)

    def test_original_staging_helper_still_refuses_production(self):
        client = staging.StagingClient("http://127.0.0.1:8000")
        self.opener.open.return_value = response(health("production"))
        with self.assertRaises(staging.CheckFailure):
            client.health("core_before")
        self.assert_post_refused(client)

    def test_verified_client_still_refuses_refresh_and_configuration_endpoints(self):
        client = self.client("production")
        self.opener.open.return_value = response(health("production"))
        client.health("core_before")
        for path in ("/v1/internal/external-sources/refresh", "/v1/config", "/v1/health"):
            with self.subTest(path=path), self.assertRaises(staging.CheckFailure):
                client.request(path, payload={})
        self.assertEqual(self.opener.open.call_count, 1)

    def test_mismatch_stops_main_before_saved_data_or_questions(self):
        self.opener.open.return_value = response(health("production"))
        with patch.object(release, "check_saved_data") as saved, patch.object(release, "check_questions") as questions:
            self.assertEqual(release.main(["--expected-environment", "staging"]), 1)
        saved.assert_not_called()
        questions.assert_not_called()
        self.assertEqual(self.opener.open.call_count, 1)

    def test_success_checks_core_before_and_after_shared_assertions(self):
        self.opener.open.return_value = response(health("production"))
        with (patch.object(release, "check_saved_data") as saved,
              patch.object(release, "check_questions") as questions,
              patch.dict(os.environ, {"PORT": "9123"})):
            self.assertEqual(release.main(["--expected-environment", "production"]), 0)
        saved.assert_called_once()
        questions.assert_called_once_with(saved.call_args.args[0])
        self.assertEqual([call.args[0].full_url for call in self.opener.open.call_args_list],
                         ["http://127.0.0.1:9123/v1/health"] * 2)
        self.assertEqual(json.loads(self.output.getvalue().splitlines()[-1])["environment"], "production")

    def test_error_output_does_not_disclose_urls_secrets_or_response_bodies(self):
        secret = "phase29-test-secret"
        self.assertEqual(release.main(["--expected-environment", "production", "--unknown", secret]), 1)
        self.assertEqual(release.main(["--expected-environment", "production", "--base-url",
                                       f"http://user:{secret}@example.test"]), 1)
        self.opener.open.side_effect = HTTPError(f"http://{secret}.test", 302, secret, {}, io.BytesIO(secret.encode()))
        self.assertEqual(release.main(["--expected-environment", "production"]), 1)
        self.assertNotIn(secret, self.output.getvalue())
        self.assertTrue(all(json.loads(line)["status"] == "failed" for line in self.output.getvalue().splitlines()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
