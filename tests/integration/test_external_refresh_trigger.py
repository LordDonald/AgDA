"""Tests for the cron-safe external refresh trigger."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch


MODULE_PATH = (
    Path(__file__)
    .resolve()
    .parents[2]
    / "tools"
    / "trigger_external_refresh.py"
)

SPEC = importlib.util.spec_from_file_location(
    "trigger_external_refresh",
    MODULE_PATH,
)

if (
    SPEC is None
    or SPEC.loader is None
):
    raise RuntimeError(
        "Could not load trigger command."
    )

trigger = importlib.util.module_from_spec(
    SPEC
)

SPEC.loader.exec_module(
    trigger
)


TOKEN = "phase27d-secret-token"
URL = (
    "http://api.railway.internal:8000/"
    "v1/internal/external-sources/refresh"
)


class ExternalRefreshTriggerTests(
    unittest.TestCase
):

    def run_main(
        self,
        *,
        environment=None,
    ):
        values = {
            "AGDA_OPERATIONS_TOKEN":
                TOKEN,
            "AGDA_OPERATIONS_REFRESH_URL":
                URL,
        }

        if environment:
            values.update(
                environment
            )

        output = io.StringIO()

        with (
            patch.dict(
                os.environ,
                values,
                clear=True,
            ),
            patch(
                "sys.stdout",
                output,
            ),
        ):
            status = trigger.main(
                [
                    "weather",
                ]
            )

        return (
            status,
            json.loads(
                output.getvalue()
            ),
        )

    def test_success_returns_zero(self):
        payload = {
            "status":
                "refreshed_and_adopted",
            "source":
                "weather",
        }

        with patch.object(
            trigger,
            "_request",
            return_value=(
                200,
                payload,
            ),
        ):
            status, result = (
                self.run_main()
            )

        self.assertEqual(
            status,
            0,
        )

        self.assertEqual(
            result,
            payload,
        )

    def test_failed_refresh_returns_two(self):
        payload = {
            "status":
                "refresh_not_adopted",
            "refresh": {
                "status":
                    "failed_retained",
            },
        }

        with patch.object(
            trigger,
            "_request",
            return_value=(
                503,
                payload,
            ),
        ):
            status, _ = (
                self.run_main()
            )

        self.assertEqual(
            status,
            2,
        )

    def test_no_data_returns_three(self):
        payload = {
            "status":
                "refresh_not_adopted",
            "refresh": {
                "status":
                    "no_data_retained",
            },
        }

        with patch.object(
            trigger,
            "_request",
            return_value=(
                200,
                payload,
            ),
        ):
            status, _ = (
                self.run_main()
            )

        self.assertEqual(
            status,
            3,
        )

    def test_adoption_failure_returns_five(self):
        payload = {
            "status":
                "adoption_failed",
            "refresh": {
                "status":
                    "updated",
            },
        }

        with patch.object(
            trigger,
            "_request",
            return_value=(
                503,
                payload,
            ),
        ):
            status, _ = (
                self.run_main()
            )

        self.assertEqual(
            status,
            5,
        )

    def test_missing_token_fails_before_request(self):
        with patch.object(
            trigger,
            "_request",
        ) as request:
            status, payload = (
                self.run_main(
                    environment={
                        "AGDA_OPERATIONS_TOKEN":
                            "",
                    },
                )
            )

        self.assertEqual(
            status,
            5,
        )

        self.assertEqual(
            payload["status"],
            "trigger_error",
        )

        request.assert_not_called()

    def test_token_is_not_written_to_output(self):
        payload = {
            "status":
                "refreshed_and_adopted",
            "source":
                "weather",
        }

        with patch.object(
            trigger,
            "_request",
            return_value=(
                200,
                payload,
            ),
        ):
            _, result = (
                self.run_main()
            )

        self.assertNotIn(
            TOKEN,
            json.dumps(
                result
            ),
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
