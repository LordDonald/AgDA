"""Scheduler-facing external refresh command tests."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch

from packages.data_sources.external_refresh import (
    ExternalRefreshInvariantError,
    ExternalRefreshOutcome,
    ExternalRefreshStatus,
)
from packages.data_sources.providers.fews_market_prices import (
    FEWS_MARKET_SOURCE_ID,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
)
command_spec = importlib.util.spec_from_file_location(
    "agda_external_refresh_command",
    Path(__file__).resolve().parents[2]
    / "tools"
    / "refresh_external_source.py",
)

if (
    command_spec is None
    or command_spec.loader is None
):
    raise RuntimeError(
        "Could not load external refresh command."
    )

refresh_external_source = (
    importlib.util.module_from_spec(
        command_spec
    )
)

command_spec.loader.exec_module(
    refresh_external_source
)


A = "a" * 64
B = "b" * 64


class ExternalRefreshCommandTests(
    unittest.TestCase
):

    def outcome(
        self,
        *,
        source_id=FEWS_MARKET_SOURCE_ID,
        status=ExternalRefreshStatus.UPDATED,
        previous=A,
        active=B,
        error_type=None,
        error_message=None,
    ):
        return ExternalRefreshOutcome(
            source_id=source_id,
            status=status,
            previous_snapshot_id=previous,
            active_snapshot_id=active,
            retrieved_at=datetime(
                2026,
                10,
                11,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            record_count=16,
            error_type=error_type,
            error_message=error_message,
        )

    def run_main(
        self,
        arguments,
    ):
        output = io.StringIO()

        with redirect_stdout(output):
            status = (
                refresh_external_source.main(
                    arguments
                )
            )

        payload = json.loads(
            output.getvalue()
        )

        return status, payload

    def test_updated_returns_zero(self):
        with patch.object(
            refresh_external_source,
            "_refresh_fews",
            return_value=self.outcome(),
        ):
            status, payload = self.run_main(
                ["fews"]
            )

        self.assertEqual(
            status,
            0,
        )

        self.assertEqual(
            payload["status"],
            "updated",
        )

        self.assertEqual(
            payload[
                "active_snapshot_id"
            ],
            B,
        )

    def test_unchanged_returns_zero(self):
        with patch.object(
            refresh_external_source,
            "_refresh_fews",
            return_value=self.outcome(
                status=
                    ExternalRefreshStatus.UNCHANGED,
                previous=A,
                active=A,
            ),
        ):
            status, payload = self.run_main(
                ["fews"]
            )

        self.assertEqual(
            status,
            0,
        )

        self.assertEqual(
            payload["status"],
            "unchanged",
        )

    def test_failed_retained_returns_two(self):
        with patch.object(
            refresh_external_source,
            "_refresh_fews",
            return_value=self.outcome(
                status=
                    ExternalRefreshStatus.FAILED_RETAINED,
                previous=A,
                active=A,
                error_type=
                    "FewsClientError",
                error_message=
                    "synthetic failure",
            ),
        ):
            status, payload = self.run_main(
                ["fews"]
            )

        self.assertEqual(
            status,
            2,
        )

        self.assertEqual(
            payload["status"],
            "failed_retained",
        )

        self.assertEqual(
            payload[
                "previous_snapshot_id"
            ],
            payload[
                "active_snapshot_id"
            ],
        )

    def test_no_data_retained_returns_three(self):
        with patch.object(
            refresh_external_source,
            "_refresh_fews",
            return_value=self.outcome(
                status=
                    ExternalRefreshStatus.NO_DATA_RETAINED,
                previous=A,
                active=A,
            ),
        ):
            status, payload = self.run_main(
                ["fews"]
            )

        self.assertEqual(
            status,
            3,
        )

        self.assertEqual(
            payload["status"],
            "no_data_retained",
        )

    def test_initial_no_data_returns_three(self):
        with patch.object(
            refresh_external_source,
            "_refresh_fews",
            return_value=self.outcome(
                status=
                    ExternalRefreshStatus.NO_DATA,
                previous=None,
                active=None,
            ),
        ):
            status, payload = self.run_main(
                ["fews"]
            )

        self.assertEqual(
            status,
            3,
        )

        self.assertEqual(
            payload["status"],
            "no_data",
        )

    def test_invariant_violation_returns_four(self):
        with patch.object(
            refresh_external_source,
            "_refresh_fews",
            side_effect=
                ExternalRefreshInvariantError(
                    "synthetic invariant"
                ),
        ):
            status, payload = self.run_main(
                ["fews"]
            )

        self.assertEqual(
            status,
            4,
        )

        self.assertEqual(
            payload["status"],
            "invariant_violation",
        )

    def test_weather_uses_weather_path(self):
        weather_outcome = self.outcome(
            source_id=
                OPEN_METEO_FORECAST_SOURCE_ID,
        )

        with patch.object(
            refresh_external_source,
            "_refresh_weather",
            return_value=
                weather_outcome,
        ) as refresh:
            status, payload = self.run_main(
                [
                    "weather",
                    "--latitude",
                    "5.10719",
                    "--longitude",
                    "7.37063",
                    "--days",
                    "3",
                ]
            )

        self.assertEqual(
            status,
            0,
        )

        self.assertEqual(
            payload["source_id"],
            OPEN_METEO_FORECAST_SOURCE_ID,
        )

        refresh.assert_called_once()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
