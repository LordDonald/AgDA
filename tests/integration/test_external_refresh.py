"""Phase 27A guarded external refresh contract tests."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

from packages.data_sources.external_refresh import (
    ExternalRefreshInvariantError,
    ExternalRefreshStatus,
    _run_guarded_refresh,
    refresh_fews_source,
    refresh_weather_source,
)
from packages.data_sources.providers.fews_http_client import (
    FewsClientError,
)
from packages.data_sources.providers.fews_market_prices import (
    FEWS_MARKET_SOURCE_ID,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    WeatherClientError,
)


A = "a" * 64
B = "b" * 64


@dataclass
class _Stored:
    snapshot_id: str


@dataclass
class _Result:
    snapshot: object | None
    records: tuple[object, ...]
    retrieved_at: datetime


class _Store:
    def __init__(
        self,
        snapshot_id: str | None = None,
    ):
        self.current = (
            _Stored(snapshot_id)
            if snapshot_id is not None
            else None
        )

    def latest(self):
        return self.current


class ExternalRefreshContractTests(
    unittest.TestCase
):

    def setUp(self):
        self.retrieved_at = datetime(
            2026,
            10,
            11,
            12,
            0,
            tzinfo=timezone.utc,
        )

    def run_guarded(
        self,
        *,
        store,
        refresh,
    ):
        return _run_guarded_refresh(
            source_id="test_source",
            store=store,
            refresh=refresh,
            expected_errors=(RuntimeError,),
            has_data=lambda result: (
                result.snapshot is not None
            ),
            retrieved_at=lambda result: (
                result.retrieved_at
            ),
            record_count=lambda result: (
                len(result.records)
            ),
        )

    def result(
        self,
        *,
        has_data=True,
    ):
        return _Result(
            snapshot=(
                object()
                if has_data
                else None
            ),
            records=(
                (object(),)
                if has_data
                else ()
            ),
            retrieved_at=self.retrieved_at,
        )

    def test_successful_refresh_reports_updated(self):
        store = _Store(A)

        def refresh():
            store.current = _Stored(B)
            return self.result()

        outcome = self.run_guarded(
            store=store,
            refresh=refresh,
        )

        self.assertEqual(
            outcome.status,
            ExternalRefreshStatus.UPDATED,
        )
        self.assertEqual(
            outcome.previous_snapshot_id,
            A,
        )
        self.assertEqual(
            outcome.active_snapshot_id,
            B,
        )
        self.assertEqual(
            outcome.record_count,
            1,
        )

    def test_completed_refresh_can_report_unchanged(self):
        store = _Store(A)

        outcome = self.run_guarded(
            store=store,
            refresh=lambda: self.result(),
        )

        self.assertEqual(
            outcome.status,
            ExternalRefreshStatus.UNCHANGED,
        )
        self.assertEqual(
            outcome.active_snapshot_id,
            A,
        )

    def test_no_data_retains_previous_snapshot(self):
        store = _Store(A)

        outcome = self.run_guarded(
            store=store,
            refresh=lambda: self.result(
                has_data=False
            ),
        )

        self.assertEqual(
            outcome.status,
            ExternalRefreshStatus.NO_DATA_RETAINED,
        )
        self.assertEqual(
            outcome.previous_snapshot_id,
            A,
        )
        self.assertEqual(
            outcome.active_snapshot_id,
            A,
        )

    def test_initial_no_data_keeps_store_empty(self):
        store = _Store()

        outcome = self.run_guarded(
            store=store,
            refresh=lambda: self.result(
                has_data=False
            ),
        )

        self.assertEqual(
            outcome.status,
            ExternalRefreshStatus.NO_DATA,
        )
        self.assertIsNone(
            outcome.active_snapshot_id
        )

    def test_failure_retains_previous_snapshot(self):
        store = _Store(A)

        def refresh():
            raise RuntimeError(
                "synthetic provider failure"
            )

        outcome = self.run_guarded(
            store=store,
            refresh=refresh,
        )

        self.assertEqual(
            outcome.status,
            ExternalRefreshStatus.FAILED_RETAINED,
        )
        self.assertEqual(
            outcome.active_snapshot_id,
            A,
        )
        self.assertEqual(
            outcome.error_type,
            "RuntimeError",
        )

    def test_initial_failure_reports_no_snapshot(self):
        store = _Store()

        def refresh():
            raise RuntimeError(
                "synthetic provider failure"
            )

        outcome = self.run_guarded(
            store=store,
            refresh=refresh,
        )

        self.assertEqual(
            outcome.status,
            ExternalRefreshStatus.FAILED_NO_SNAPSHOT,
        )
        self.assertIsNone(
            outcome.active_snapshot_id
        )

    def test_failed_attempt_cannot_change_snapshot(self):
        store = _Store(A)

        def refresh():
            store.current = _Stored(B)
            raise RuntimeError(
                "failed after mutation"
            )

        with self.assertRaises(
            ExternalRefreshInvariantError
        ):
            self.run_guarded(
                store=store,
                refresh=refresh,
            )

    def test_no_data_attempt_cannot_change_snapshot(self):
        store = _Store(A)

        def refresh():
            store.current = _Stored(B)
            return self.result(
                has_data=False
            )

        with self.assertRaises(
            ExternalRefreshInvariantError
        ):
            self.run_guarded(
                store=store,
                refresh=refresh,
            )

    def test_fews_wrapper_converts_provider_failure(self):
        store = _Store(A)

        with patch(
            "packages.data_sources.external_refresh."
            "refresh_fews_market_prices",
            side_effect=FewsClientError(
                "synthetic FEWS failure"
            ),
        ):
            outcome = refresh_fews_source(
                object(),
                store=store,
                registry=object(),
            )

        self.assertEqual(
            outcome.source_id,
            FEWS_MARKET_SOURCE_ID,
        )
        self.assertEqual(
            outcome.status,
            ExternalRefreshStatus.FAILED_RETAINED,
        )

    def test_weather_wrapper_converts_provider_failure(self):
        store = _Store(A)

        with patch(
            "packages.data_sources.external_refresh."
            "refresh_weather_forecast",
            side_effect=WeatherClientError(
                "synthetic weather failure"
            ),
        ):
            outcome = refresh_weather_source(
                object(),
                store=store,
                registry=object(),
            )

        self.assertEqual(
            outcome.source_id,
            OPEN_METEO_FORECAST_SOURCE_ID,
        )
        self.assertEqual(
            outcome.status,
            ExternalRefreshStatus.FAILED_RETAINED,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
