"""Internal external-source runtime reload API tests."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.routes import (
    internal_external_sources as route_module,
)


TEST_TOKEN = "phase27-operations-token"
A = "a" * 64
B = "b" * 64
C = "c" * 64


@dataclass
class _Stored:
    snapshot_id: str


class _FakeRuntime:

    def __init__(self):
        self.ready = True

        self.fews_snapshot_restore_status = (
            "loaded"
        )

        self.weather_snapshot_restore_status = (
            "loaded"
        )

        self.fews_id = A
        self.weather_id = B

        self.fews_reload_calls = 0
        self.weather_reload_calls = 0

        self.next_fews_id = C
        self.next_weather_id = C

        self.next_fews_status = "loaded"
        self.next_weather_status = "loaded"

    def market_price_snapshot(self):
        return (
            _Stored(self.fews_id)
            if self.fews_id is not None
            else None
        )

    def weather_forecast_snapshot(self):
        return (
            _Stored(self.weather_id)
            if self.weather_id is not None
            else None
        )

    def reload_fews_snapshot(self):
        self.fews_reload_calls += 1
        self.fews_snapshot_restore_status = (
            self.next_fews_status
        )

        if self.next_fews_status == "loaded":
            self.fews_id = self.next_fews_id

    def reload_weather_snapshot(self):
        self.weather_reload_calls += 1
        self.weather_snapshot_restore_status = (
            self.next_weather_status
        )

        if (
            self.next_weather_status
            == "loaded"
        ):
            self.weather_id = (
                self.next_weather_id
            )


class InternalExternalSourceReloadTests(
    unittest.TestCase
):

    def setUp(self):
        self.runtime = _FakeRuntime()

        self.settings = replace(
            route_module.settings,
            operations_token=TEST_TOKEN,
        )

        self.runtime_patch = patch.object(
            route_module,
            "runtime",
            self.runtime,
        )

        self.settings_patch = patch.object(
            route_module,
            "settings",
            self.settings,
        )

        self.runtime_patch.start()
        self.settings_patch.start()

        self.addCleanup(
            self.runtime_patch.stop
        )

        self.addCleanup(
            self.settings_patch.stop
        )

        self.client = TestClient(
            app
        )

    def headers(self):
        return {
            "X-AgDA-Operations-Token":
                TEST_TOKEN
        }

    def post(
        self,
        source="all",
        *,
        headers=None,
    ):
        return self.client.post(
            "/v1/internal/external-sources/reload",
            json={
                "source": source,
            },
            headers=(
                self.headers()
                if headers is None
                else headers
            ),
        )

    def test_missing_token_is_unauthorized(self):
        response = self.post(
            headers={}
        )

        self.assertEqual(
            response.status_code,
            401,
        )

        self.assertEqual(
            self.runtime.fews_reload_calls,
            0,
        )

        self.assertEqual(
            self.runtime.weather_reload_calls,
            0,
        )

    def test_wrong_token_is_unauthorized(self):
        response = self.post(
            headers={
                "X-AgDA-Operations-Token":
                    "wrong-token"
            }
        )

        self.assertEqual(
            response.status_code,
            401,
        )

    def test_unconfigured_operations_returns_503(self):
        with patch.object(
            route_module,
            "settings",
            replace(
                self.settings,
                operations_token=None,
            ),
        ):
            response = self.post()

        self.assertEqual(
            response.status_code,
            503,
        )

        self.assertEqual(
            self.runtime.fews_reload_calls,
            0,
        )

        self.assertEqual(
            self.runtime.weather_reload_calls,
            0,
        )

    def test_weather_only_reloads_weather(self):
        response = self.post(
            "weather"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        payload = response.json()

        self.assertEqual(
            payload["status"],
            "reloaded",
        )

        self.assertIsNone(
            payload["fews"]
        )

        self.assertEqual(
            payload["weather"][
                "before_snapshot_id"
            ],
            B,
        )

        self.assertEqual(
            payload["weather"][
                "after_snapshot_id"
            ],
            C,
        )

        self.assertTrue(
            payload["weather"][
                "changed"
            ]
        )

        self.assertEqual(
            self.runtime.fews_reload_calls,
            0,
        )

        self.assertEqual(
            self.runtime.weather_reload_calls,
            1,
        )

    def test_all_reloads_both_sources(self):
        response = self.post(
            "all"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        payload = response.json()

        self.assertEqual(
            payload["status"],
            "reloaded",
        )

        self.assertTrue(
            payload["core_ready"]
        )

        self.assertEqual(
            self.runtime.fews_reload_calls,
            1,
        )

        self.assertEqual(
            self.runtime.weather_reload_calls,
            1,
        )

    def test_failed_adoption_returns_503_and_retains_snapshot(self):
        self.runtime.next_weather_status = (
            "error"
        )

        response = self.post(
            "weather"
        )

        self.assertEqual(
            response.status_code,
            503,
        )

        payload = response.json()

        self.assertEqual(
            payload["status"],
            "degraded",
        )

        self.assertEqual(
            payload["weather"][
                "restore_status"
            ],
            "error",
        )

        self.assertEqual(
            payload["weather"][
                "before_snapshot_id"
            ],
            B,
        )

        self.assertEqual(
            payload["weather"][
                "after_snapshot_id"
            ],
            B,
        )

        self.assertFalse(
            payload["weather"][
                "changed"
            ]
        )

        self.assertTrue(
            payload["core_ready"]
        )


    def test_weather_refresh_adopts_exact_snapshot(self):
        outcome = route_module.ExternalRefreshOutcome(
            source_id="open_meteo_forecast",
            status=route_module.ExternalRefreshStatus.UPDATED,
            previous_snapshot_id=B,
            active_snapshot_id=C,
            retrieved_at=None,
            record_count=72,
        )

        self.runtime.weather_id = B
        self.runtime.next_weather_id = C
        self.runtime.next_weather_status = "loaded"

        with patch.object(
            route_module,
            "_refresh_weather",
            return_value=outcome,
        ):
            response = self.client.post(
                "/v1/internal/external-sources/refresh",
                json={
                    "source": "weather",
                },
                headers=self.headers(),
            )

        self.assertEqual(
            response.status_code,
            200,
            response.text,
        )

        payload = response.json()

        self.assertEqual(
            payload["status"],
            "refreshed_and_adopted",
        )

        self.assertEqual(
            payload["refresh"][
                "active_snapshot_id"
            ],
            C,
        )

        self.assertEqual(
            payload["reload"][
                "after_snapshot_id"
            ],
            C,
        )

        self.assertEqual(
            self.runtime.weather_reload_calls,
            1,
        )

    def test_failed_weather_refresh_does_not_reload(self):
        outcome = route_module.ExternalRefreshOutcome(
            source_id="open_meteo_forecast",
            status=route_module.ExternalRefreshStatus.FAILED_RETAINED,
            previous_snapshot_id=B,
            active_snapshot_id=B,
            retrieved_at=None,
            record_count=72,
            error_type="WeatherClientError",
            error_message="synthetic failure",
        )

        with patch.object(
            route_module,
            "_refresh_weather",
            return_value=outcome,
        ):
            response = self.client.post(
                "/v1/internal/external-sources/refresh",
                json={
                    "source": "weather",
                },
                headers=self.headers(),
            )

        self.assertEqual(
            response.status_code,
            503,
        )

        payload = response.json()

        self.assertEqual(
            payload["status"],
            "refresh_not_adopted",
        )

        self.assertIsNone(
            payload["reload"]
        )

        self.assertEqual(
            self.runtime.weather_reload_calls,
            0,
        )

    def test_no_data_fews_refresh_does_not_reload(self):
        outcome = route_module.ExternalRefreshOutcome(
            source_id="fews_net_market_prices_ng",
            status=route_module.ExternalRefreshStatus.NO_DATA_RETAINED,
            previous_snapshot_id=A,
            active_snapshot_id=A,
            retrieved_at=None,
            record_count=1,
        )

        with patch.object(
            route_module,
            "_refresh_fews",
            return_value=outcome,
        ):
            response = self.client.post(
                "/v1/internal/external-sources/refresh",
                json={
                    "source": "fews",
                },
                headers=self.headers(),
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        payload = response.json()

        self.assertEqual(
            payload["status"],
            "refresh_not_adopted",
        )

        self.assertIsNone(
            payload["reload"]
        )

        self.assertEqual(
            self.runtime.fews_reload_calls,
            0,
        )

    def test_refresh_adoption_mismatch_returns_503(self):
        outcome = route_module.ExternalRefreshOutcome(
            source_id="open_meteo_forecast",
            status=route_module.ExternalRefreshStatus.UPDATED,
            previous_snapshot_id=B,
            active_snapshot_id=C,
            retrieved_at=None,
            record_count=72,
        )

        self.runtime.weather_id = B
        self.runtime.next_weather_id = A
        self.runtime.next_weather_status = "loaded"

        with patch.object(
            route_module,
            "_refresh_weather",
            return_value=outcome,
        ):
            response = self.client.post(
                "/v1/internal/external-sources/refresh",
                json={
                    "source": "weather",
                },
                headers=self.headers(),
            )

        self.assertEqual(
            response.status_code,
            503,
        )

        payload = response.json()

        self.assertEqual(
            payload["status"],
            "adoption_failed",
        )

        self.assertEqual(
            payload["reload"][
                "after_snapshot_id"
            ],
            A,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
