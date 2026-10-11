"""External refresh + runtime adoption orchestration tests."""

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
    / "refresh_and_reload_external_source.py"
)

SPEC = (
    importlib.util.spec_from_file_location(
        "refresh_and_reload_external_source",
        MODULE_PATH,
    )
)

if (
    SPEC is None
    or SPEC.loader is None
):
    raise RuntimeError(
        "Could not load orchestration command."
    )

orchestrator = (
    importlib.util.module_from_spec(
        SPEC
    )
)

SPEC.loader.exec_module(
    orchestrator
)


TOKEN = "phase27-secret-operations-token"
URL = (
    "http://127.0.0.1:8000/"
    "v1/internal/external-sources/reload"
)
SNAPSHOT = "a" * 64


def refresh_payload(
    status="updated",
):
    return {
        "active_snapshot_id":
            SNAPSHOT,
        "error_message":
            None,
        "error_type":
            None,
        "previous_snapshot_id":
            None,
        "record_count":
            72,
        "retrieved_at":
            "2026-10-11T20:29:19+00:00",
        "source_id":
            "open_meteo_forecast",
        "status":
            status,
    }


def reload_payload(
    *,
    after=SNAPSHOT,
    status="reloaded",
    restore_status="loaded",
):
    return {
        "status":
            status,
        "source":
            "weather",
        "core_ready":
            True,
        "fews":
            None,
        "weather": {
            "before_snapshot_id":
                None,
            "after_snapshot_id":
                after,
            "restore_status":
                restore_status,
            "changed":
                True,
        },
    }


class ExternalRefreshOrchestrationTests(
    unittest.TestCase
):

    def run_main(
        self,
        arguments,
        *,
        environment=None,
    ):
        output = io.StringIO()

        values = {
            "AGDA_OPERATIONS_TOKEN":
                TOKEN,
            "AGDA_OPERATIONS_RELOAD_URL":
                URL,
        }

        if environment:
            values.update(
                environment
            )

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
            status = (
                orchestrator.main(
                    arguments
                )
            )

        return (
            status,
            json.loads(
                output.getvalue()
            ),
        )

    def test_updated_refresh_is_adopted(self):
        refresh = refresh_payload()

        reload = reload_payload()

        with (
            patch.object(
                orchestrator,
                "_run_refresh",
                return_value=(
                    0,
                    refresh,
                ),
            ),
            patch.object(
                orchestrator,
                "_post_reload",
                return_value=(
                    200,
                    reload,
                ),
            ) as post_reload,
        ):
            status, payload = (
                self.run_main(
                    [
                        "weather",
                        "--database",
                        "weather.sqlite3",
                    ]
                )
            )

        self.assertEqual(
            status,
            0,
        )

        self.assertEqual(
            payload["status"],
            "refreshed_and_adopted",
        )

        post_reload.assert_called_once_with(
            url=URL,
            source="weather",
            token=TOKEN,
            timeout_seconds=20.0,
        )

    def test_unchanged_refresh_is_still_adopted(self):
        with (
            patch.object(
                orchestrator,
                "_run_refresh",
                return_value=(
                    0,
                    refresh_payload(
                        "unchanged"
                    ),
                ),
            ),
            patch.object(
                orchestrator,
                "_post_reload",
                return_value=(
                    200,
                    reload_payload(),
                ),
            ) as post_reload,
        ):
            status, _ = self.run_main(
                ["weather"]
            )

        self.assertEqual(
            status,
            0,
        )

        post_reload.assert_called_once()

    def test_failed_refresh_never_reloads(self):
        failed = refresh_payload(
            "failed_retained"
        )

        failed[
            "error_type"
        ] = "WeatherClientError"

        with (
            patch.object(
                orchestrator,
                "_run_refresh",
                return_value=(
                    2,
                    failed,
                ),
            ),
            patch.object(
                orchestrator,
                "_post_reload",
            ) as post_reload,
        ):
            status, payload = (
                self.run_main(
                    ["weather"]
                )
            )

        self.assertEqual(
            status,
            2,
        )

        self.assertEqual(
            payload["status"],
            "refresh_not_adopted",
        )

        self.assertIsNone(
            payload["reload"]
        )

        post_reload.assert_not_called()

    def test_no_data_never_reloads(self):
        no_data = refresh_payload(
            "no_data_retained"
        )

        with (
            patch.object(
                orchestrator,
                "_run_refresh",
                return_value=(
                    3,
                    no_data,
                ),
            ),
            patch.object(
                orchestrator,
                "_post_reload",
            ) as post_reload,
        ):
            status, _ = self.run_main(
                ["fews"]
            )

        self.assertEqual(
            status,
            3,
        )

        post_reload.assert_not_called()

    def test_missing_token_fails_before_refresh(self):
        with patch.object(
            orchestrator,
            "_run_refresh",
        ) as refresh:
            status, payload = (
                self.run_main(
                    ["weather"],
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
            "configuration_error",
        )

        refresh.assert_not_called()

    def test_reload_http_failure_returns_five(self):
        with (
            patch.object(
                orchestrator,
                "_run_refresh",
                return_value=(
                    0,
                    refresh_payload(),
                ),
            ),
            patch.object(
                orchestrator,
                "_post_reload",
                return_value=(
                    503,
                    {
                        "status":
                            "degraded",
                    },
                ),
            ),
        ):
            status, payload = (
                self.run_main(
                    ["weather"]
                )
            )

        self.assertEqual(
            status,
            5,
        )

        self.assertEqual(
            payload["status"],
            "adoption_failed",
        )

    def test_snapshot_mismatch_is_invariant_failure(self):
        with (
            patch.object(
                orchestrator,
                "_run_refresh",
                return_value=(
                    0,
                    refresh_payload(),
                ),
            ),
            patch.object(
                orchestrator,
                "_post_reload",
                return_value=(
                    200,
                    reload_payload(
                        after=(
                            "b" * 64
                        )
                    ),
                ),
            ),
        ):
            status, payload = (
                self.run_main(
                    ["weather"]
                )
            )

        self.assertEqual(
            status,
            4,
        )

        self.assertEqual(
            payload["status"],
            "adoption_invariant_error",
        )

    def test_zero_exit_nonreloadable_status_is_invariant(self):
        with (
            patch.object(
                orchestrator,
                "_run_refresh",
                return_value=(
                    0,
                    refresh_payload(
                        "no_data"
                    ),
                ),
            ),
            patch.object(
                orchestrator,
                "_post_reload",
            ) as post_reload,
        ):
            status, payload = (
                self.run_main(
                    ["weather"]
                )
            )

        self.assertEqual(
            status,
            4,
        )

        self.assertEqual(
            payload["status"],
            "refresh_contract_error",
        )

        post_reload.assert_not_called()

    def test_token_is_not_forwarded_to_refresh_command(self):
        captured = {}

        def fake_refresh(
            source,
            arguments,
        ):
            captured["source"] = (
                source
            )

            captured["arguments"] = (
                list(arguments)
            )

            return (
                0,
                refresh_payload(),
            )

        with (
            patch.object(
                orchestrator,
                "_run_refresh",
                side_effect=
                    fake_refresh,
            ),
            patch.object(
                orchestrator,
                "_post_reload",
                return_value=(
                    200,
                    reload_payload(),
                ),
            ),
        ):
            status, payload = (
                self.run_main(
                    [
                        "weather",
                        "--database",
                        "weather.sqlite3",
                    ]
                )
            )

        self.assertEqual(
            status,
            0,
        )

        self.assertNotIn(
            TOKEN,
            captured["arguments"],
        )

        self.assertNotIn(
            TOKEN,
            json.dumps(
                payload
            ),
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
