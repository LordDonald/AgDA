"""Guarded operational refreshes for external AgDA data sources.

This module does not replace source-specific fetching or persistence.
It wraps the existing validated ingestion paths with one operational
outcome contract and verifies that failed/no-data attempts cannot
silently replace the last-known-good stored snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable

from packages.data_sources.fews_ingestion import (
    FewsIngestionError,
    refresh_fews_market_prices,
)
from packages.data_sources.providers.fews_http_client import (
    FewsClientError,
    FewsMarketPriceClient,
    FewsMarketPriceQuery,
)
from packages.data_sources.providers.fews_market_prices import (
    FEWS_MARKET_SOURCE_ID,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    OpenMeteoForecastClient,
    OpenMeteoForecastQuery,
    WeatherClientError,
)
from packages.data_sources.registry import SourceRegistry
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore,
    SnapshotScopeError,
    SnapshotStoreError,
)
from packages.data_sources.weather_ingestion import (
    WeatherIngestionError,
    refresh_weather_forecast,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotScopeError,
    WeatherSnapshotStore,
    WeatherSnapshotStoreError,
)


class ExternalRefreshStatus(StrEnum):
    """Operational result of one explicit refresh attempt."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    NO_DATA_RETAINED = "no_data_retained"
    NO_DATA = "no_data"
    FAILED_RETAINED = "failed_retained"
    FAILED_NO_SNAPSHOT = "failed_no_snapshot"


class ExternalRefreshInvariantError(RuntimeError):
    """A refresh violated last-known-good snapshot preservation."""


@dataclass(frozen=True, slots=True)
class ExternalRefreshOutcome:
    """Provider-independent result suitable for scheduling/monitoring."""

    source_id: str
    status: ExternalRefreshStatus
    previous_snapshot_id: str | None
    active_snapshot_id: str | None
    retrieved_at: datetime | None
    record_count: int | None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_id, str)
            or not self.source_id.strip()
        ):
            raise ValueError(
                "source_id must be nonblank text."
            )

        for name in (
            "previous_snapshot_id",
            "active_snapshot_id",
        ):
            value = getattr(self, name)

            if value is not None and (
                not isinstance(value, str)
                or len(value) != 64
                or any(
                    character
                    not in "0123456789abcdef"
                    for character in value
                )
            ):
                raise ValueError(
                    f"{name} must be a lowercase "
                    "64-character SHA-256 hex value."
                )

        if (
            self.record_count is not None
            and (
                type(self.record_count) is not int
                or self.record_count < 0
            )
        ):
            raise ValueError(
                "record_count must be a nonnegative "
                "integer or None."
            )

        retained_statuses = {
            ExternalRefreshStatus.NO_DATA_RETAINED,
            ExternalRefreshStatus.FAILED_RETAINED,
        }

        if self.status in retained_statuses:
            if (
                self.previous_snapshot_id is None
                or self.active_snapshot_id
                != self.previous_snapshot_id
            ):
                raise ValueError(
                    "A retained outcome must preserve "
                    "the previous snapshot."
                )

        if (
            self.status
            == ExternalRefreshStatus.UPDATED
            and (
                self.active_snapshot_id is None
                or self.active_snapshot_id
                == self.previous_snapshot_id
            )
        ):
            raise ValueError(
                "An updated outcome must activate "
                "a different snapshot."
            )

        failed_statuses = {
            ExternalRefreshStatus.FAILED_RETAINED,
            ExternalRefreshStatus.FAILED_NO_SNAPSHOT,
        }

        if self.status in failed_statuses:
            if not self.error_type:
                raise ValueError(
                    "A failed outcome requires error_type."
                )
        elif (
            self.error_type is not None
            or self.error_message is not None
        ):
            raise ValueError(
                "Successful/no-data outcomes cannot "
                "carry error details."
            )


def _latest(store: Any) -> tuple[Any | None, str | None]:
    stored = store.latest()

    if stored is None:
        return None, None

    snapshot_id = getattr(
        stored,
        "snapshot_id",
        None,
    )

    if (
        not isinstance(snapshot_id, str)
        or len(snapshot_id) != 64
    ):
        raise ExternalRefreshInvariantError(
            "Stored snapshot does not expose "
            "a valid snapshot_id."
        )

    return stored, snapshot_id


def _latest_after_attempt(
    *,
    store: Any,
    source_id: str,
) -> tuple[Any | None, str | None]:
    try:
        return _latest(store)
    except Exception as error:
        raise ExternalRefreshInvariantError(
            f"Could not verify active snapshot "
            f"after refreshing {source_id}."
        ) from error


def _run_guarded_refresh(
    *,
    source_id: str,
    store: Any,
    refresh: Callable[[], Any],
    expected_errors: tuple[type[Exception], ...],
    has_data: Callable[[Any], bool],
    retrieved_at: Callable[[Any], datetime | None],
    record_count: Callable[[Any], int | None],
) -> ExternalRefreshOutcome:
    _, previous_id = _latest(store)

    try:
        result = refresh()

    except expected_errors as error:
        _, active_id = _latest_after_attempt(
            store=store,
            source_id=source_id,
        )

        if active_id != previous_id:
            raise ExternalRefreshInvariantError(
                "A failed refresh changed the "
                "last-known-good snapshot for "
                f"{source_id}."
            ) from error

        return ExternalRefreshOutcome(
            source_id=source_id,
            status=(
                ExternalRefreshStatus.FAILED_RETAINED
                if previous_id is not None
                else
                ExternalRefreshStatus.FAILED_NO_SNAPSHOT
            ),
            previous_snapshot_id=previous_id,
            active_snapshot_id=active_id,
            retrieved_at=None,
            record_count=None,
            error_type=type(error).__name__,
            error_message=str(error),
        )

    _, active_id = _latest_after_attempt(
        store=store,
        source_id=source_id,
    )

    if not has_data(result):
        if active_id != previous_id:
            raise ExternalRefreshInvariantError(
                "A no-data refresh changed the "
                "last-known-good snapshot for "
                f"{source_id}."
            )

        return ExternalRefreshOutcome(
            source_id=source_id,
            status=(
                ExternalRefreshStatus.NO_DATA_RETAINED
                if previous_id is not None
                else
                ExternalRefreshStatus.NO_DATA
            ),
            previous_snapshot_id=previous_id,
            active_snapshot_id=active_id,
            retrieved_at=retrieved_at(result),
            record_count=record_count(result),
        )

    if active_id is None:
        raise ExternalRefreshInvariantError(
            "A completed refresh did not leave "
            f"a stored snapshot for {source_id}."
        )

    return ExternalRefreshOutcome(
        source_id=source_id,
        status=(
            ExternalRefreshStatus.UPDATED
            if active_id != previous_id
            else
            ExternalRefreshStatus.UNCHANGED
        ),
        previous_snapshot_id=previous_id,
        active_snapshot_id=active_id,
        retrieved_at=retrieved_at(result),
        record_count=record_count(result),
    )


def refresh_fews_source(
    query: FewsMarketPriceQuery,
    *,
    store: FewsSnapshotStore,
    registry: SourceRegistry,
    client: FewsMarketPriceClient | None = None,
    stale_after_hours: int = 48,
) -> ExternalRefreshOutcome:
    """Run one guarded FEWS refresh."""

    return _run_guarded_refresh(
        source_id=FEWS_MARKET_SOURCE_ID,
        store=store,
        refresh=lambda: refresh_fews_market_prices(
            query,
            store=store,
            registry=registry,
            client=client,
            stale_after_hours=stale_after_hours,
        ),
        expected_errors=(
            FewsClientError,
            FewsIngestionError,
            SnapshotStoreError,
            SnapshotScopeError,
            ValueError,
            OSError,
        ),
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


def refresh_weather_source(
    query: OpenMeteoForecastQuery,
    *,
    store: WeatherSnapshotStore,
    registry: SourceRegistry,
    client: OpenMeteoForecastClient | None = None,
    stale_after_hours: int = 6,
) -> ExternalRefreshOutcome:
    """Run one guarded Open-Meteo refresh."""

    return _run_guarded_refresh(
        source_id=OPEN_METEO_FORECAST_SOURCE_ID,
        store=store,
        refresh=lambda: refresh_weather_forecast(
            query,
            store=store,
            registry=registry,
            client=client,
            stale_after_hours=stale_after_hours,
        ),
        expected_errors=(
            WeatherClientError,
            WeatherIngestionError,
            WeatherSnapshotStoreError,
            WeatherSnapshotScopeError,
            ValueError,
            OSError,
        ),
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
