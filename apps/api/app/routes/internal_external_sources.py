"""Authenticated runtime adoption of validated external snapshots."""

from __future__ import annotations

import hmac
from datetime import date
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Response,
)
from pydantic import BaseModel

from apps.api.app.core.external_refresh_observability import (
    emit_external_refresh_event,
)
from apps.api.app.core.runtime import runtime
from apps.api.app.core.settings import settings

from packages.data_sources.external_refresh import (
    ExternalRefreshOutcome,
    ExternalRefreshStatus,
    refresh_fews_source,
    refresh_weather_source,
)
from packages.data_sources.providers.fews_http_client import (
    FewsClientLimits,
    FewsMarketPriceClient,
    FewsMarketPriceQuery,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OpenMeteoForecastClient,
    OpenMeteoForecastQuery,
    WeatherClientLimits,
)
from packages.data_sources.registry import SourceRegistry
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
)


router = APIRouter(
    prefix="/v1/internal/external-sources",
    tags=["internal-external-sources"],
)

_RELOAD_LOCK = Lock()


class ExternalSourceReloadRequest(BaseModel):
    source: Literal[
        "fews",
        "weather",
        "all",
    ] = "all"


class ExternalSourceRefreshRequest(BaseModel):
    source: Literal[
        "fews",
        "weather",
    ]


class ExternalSourceReloadState(BaseModel):
    before_snapshot_id: str | None
    after_snapshot_id: str | None
    restore_status: str
    changed: bool


class ExternalSourceReloadResponse(BaseModel):
    status: Literal[
        "reloaded",
        "degraded",
    ]
    source: Literal[
        "fews",
        "weather",
        "all",
    ]
    core_ready: bool
    fews: ExternalSourceReloadState | None
    weather: ExternalSourceReloadState | None


class ExternalSourceRefreshResult(BaseModel):
    source_id: str
    status: str
    previous_snapshot_id: str | None
    active_snapshot_id: str | None
    retrieved_at: str | None
    record_count: int
    error_type: str | None
    error_message: str | None


class ExternalSourceRefreshResponse(BaseModel):
    status: Literal[
        "refreshed_and_adopted",
        "refresh_not_adopted",
        "adoption_failed",
    ]
    source: Literal[
        "fews",
        "weather",
    ]
    core_ready: bool
    refresh: ExternalSourceRefreshResult
    reload: ExternalSourceReloadState | None


def _authorize(
    supplied_token: str | None,
) -> None:
    configured_token = (
        settings.operations_token
    )

    if not configured_token:
        raise HTTPException(
            status_code=503,
            detail=(
                "External source operations "
                "are not configured."
            ),
        )

    if (
        supplied_token is None
        or not hmac.compare_digest(
            supplied_token,
            configured_token,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized.",
        )


def _serialize_refresh(
    outcome: ExternalRefreshOutcome,
) -> ExternalSourceRefreshResult:
    return ExternalSourceRefreshResult(
        source_id=outcome.source_id,
        status=outcome.status.value,
        previous_snapshot_id=
            outcome.previous_snapshot_id,
        active_snapshot_id=
            outcome.active_snapshot_id,
        retrieved_at=(
            outcome.retrieved_at.isoformat()
            if outcome.retrieved_at
            is not None
            else None
        ),
        record_count=
            outcome.record_count,
        error_type=
            outcome.error_type,
        error_message=
            outcome.error_message,
    )


def _refresh_fews() -> ExternalRefreshOutcome:
    path = settings.fews_snapshot_path

    if not path:
        raise HTTPException(
            status_code=503,
            detail=(
                "FEWS snapshot storage "
                "is not configured."
            ),
        )

    query = FewsMarketPriceQuery(
        start_date=date(
            2025,
            1,
            1,
        ),
        end_date=date(
            2025,
            1,
            31,
        ),
        cpcv2="R01122AC",
    )

    client = FewsMarketPriceClient(
        limits=FewsClientLimits(
            page_size=100,
            max_pages=3,
            max_requests=3,
            max_records=300,
        )
    )

    return refresh_fews_source(
        query,
        store=FewsSnapshotStore(
            Path(path)
        ),
        registry=SourceRegistry(),
        client=client,
        stale_after_hours=
            settings.fews_stale_after_hours,
    )


def _refresh_weather() -> ExternalRefreshOutcome:
    path = settings.weather_snapshot_path

    if not path:
        raise HTTPException(
            status_code=503,
            detail=(
                "Weather snapshot storage "
                "is not configured."
            ),
        )

    query = OpenMeteoForecastQuery(
        latitude=Decimal(
            "5.10719"
        ),
        longitude=Decimal(
            "7.37063"
        ),
        forecast_days=3,
    )

    client = OpenMeteoForecastClient(
        limits=WeatherClientLimits(
            max_records=168,
            timeout_seconds=20,
            max_response_bytes=
                1024 * 1024,
        )
    )

    return refresh_weather_source(
        query,
        store=WeatherSnapshotStore(
            Path(path)
        ),
        registry=SourceRegistry(),
        client=client,
        stale_after_hours=
            settings.weather_stale_after_hours,
    )


def _fews_snapshot_id() -> str | None:
    stored = runtime.market_price_snapshot()

    return (
        stored.snapshot_id
        if stored is not None
        else None
    )


def _weather_snapshot_id() -> str | None:
    stored = runtime.weather_forecast_snapshot()

    return (
        stored.snapshot_id
        if stored is not None
        else None
    )


@router.post(
    "/refresh",
    response_model=
        ExternalSourceRefreshResponse,
    responses={
        401: {
            "description":
                "Unauthorized.",
        },
        503: {
            "description": (
                "Refresh or runtime adoption "
                "could not complete safely."
            ),
        },
    },
)
def refresh_external_source(
    request: ExternalSourceRefreshRequest,
    response: Response,
    operations_token: str | None = Header(
        default=None,
        alias="X-AgDA-Operations-Token",
    ),
) -> ExternalSourceRefreshResponse:
    """Refresh, persist, and adopt one external source."""

    _authorize(
        operations_token
    )

    with _RELOAD_LOCK:
        if request.source == "fews":
            outcome = _refresh_fews()
        else:
            outcome = _refresh_weather()

        refresh_result = (
            _serialize_refresh(
                outcome
            )
        )

        if outcome.status not in {
            ExternalRefreshStatus.UPDATED,
            ExternalRefreshStatus.UNCHANGED,
        }:
            if outcome.status in {
                ExternalRefreshStatus.FAILED_RETAINED,
                ExternalRefreshStatus.FAILED_NO_SNAPSHOT,
            }:
                response.status_code = 503

            emit_external_refresh_event(
                event=
                    "agda_external_refresh_retained",
                source=request.source,
                outcome=outcome,
                core_ready=runtime.ready,
            )

            return ExternalSourceRefreshResponse(
                status=
                    "refresh_not_adopted",
                source=request.source,
                core_ready=runtime.ready,
                refresh=refresh_result,
                reload=None,
            )

        before = (
            _fews_snapshot_id()
            if request.source == "fews"
            else _weather_snapshot_id()
        )

        if request.source == "fews":
            runtime.reload_fews_snapshot()

            after = (
                _fews_snapshot_id()
            )

            restore_status = (
                runtime
                .fews_snapshot_restore_status
            )

        else:
            runtime.reload_weather_snapshot()

            after = (
                _weather_snapshot_id()
            )

            restore_status = (
                runtime
                .weather_snapshot_restore_status
            )

        reload_state = (
            ExternalSourceReloadState(
                before_snapshot_id=
                    before,
                after_snapshot_id=
                    after,
                restore_status=
                    restore_status,
                changed=(
                    before != after
                ),
            )
        )

        adopted = (
            restore_status == "loaded"
            and after
            == outcome.active_snapshot_id
        )

        if not adopted:
            response.status_code = 503

            emit_external_refresh_event(
                event=
                    "agda_external_refresh_adoption_failed",
                source=request.source,
                outcome=outcome,
                core_ready=runtime.ready,
                restore_status=
                    restore_status,
                runtime_snapshot_id=
                    after,
                changed=(
                    before != after
                ),
            )

            return ExternalSourceRefreshResponse(
                status=
                    "adoption_failed",
                source=request.source,
                core_ready=runtime.ready,
                refresh=refresh_result,
                reload=reload_state,
            )

        emit_external_refresh_event(
            event=
                "agda_external_refresh_success",
            source=request.source,
            outcome=outcome,
            core_ready=runtime.ready,
            restore_status=
                restore_status,
            runtime_snapshot_id=
                after,
            changed=(
                before != after
            ),
        )

        return ExternalSourceRefreshResponse(
            status=
                "refreshed_and_adopted",
            source=request.source,
            core_ready=runtime.ready,
            refresh=refresh_result,
            reload=reload_state,
        )


@router.post(
    "/reload",
    response_model=ExternalSourceReloadResponse,
    responses={
        401: {
            "description": "Unauthorized.",
        },
        503: {
            "description": (
                "Operations are not configured "
                "or one requested snapshot could "
                "not be adopted."
            ),
        },
    },
)
def reload_external_sources(
    request: ExternalSourceReloadRequest,
    response: Response,
    operations_token: str | None = Header(
        default=None,
        alias="X-AgDA-Operations-Token",
    ),
) -> ExternalSourceReloadResponse:
    """Adopt already-validated local snapshots.

    This endpoint never performs provider HTTP requests.
    """

    _authorize(
        operations_token
    )

    include_fews = (
        request.source
        in {
            "fews",
            "all",
        }
    )

    include_weather = (
        request.source
        in {
            "weather",
            "all",
        }
    )

    with _RELOAD_LOCK:
        fews_before = (
            _fews_snapshot_id()
            if include_fews
            else None
        )

        weather_before = (
            _weather_snapshot_id()
            if include_weather
            else None
        )

        if include_fews:
            runtime.reload_fews_snapshot()

        if include_weather:
            runtime.reload_weather_snapshot()

        fews_after = (
            _fews_snapshot_id()
            if include_fews
            else None
        )

        weather_after = (
            _weather_snapshot_id()
            if include_weather
            else None
        )

        fews_state = (
            ExternalSourceReloadState(
                before_snapshot_id=
                    fews_before,
                after_snapshot_id=
                    fews_after,
                restore_status=
                    runtime
                    .fews_snapshot_restore_status,
                changed=(
                    fews_before
                    != fews_after
                ),
            )
            if include_fews
            else None
        )

        weather_state = (
            ExternalSourceReloadState(
                before_snapshot_id=
                    weather_before,
                after_snapshot_id=
                    weather_after,
                restore_status=
                    runtime
                    .weather_snapshot_restore_status,
                changed=(
                    weather_before
                    != weather_after
                ),
            )
            if include_weather
            else None
        )

    requested_states = [
        state
        for state in (
            fews_state,
            weather_state,
        )
        if state is not None
    ]

    degraded = any(
        state.restore_status
        != "loaded"
        for state
        in requested_states
    )

    if degraded:
        response.status_code = 503

    return ExternalSourceReloadResponse(
        status=(
            "degraded"
            if degraded
            else "reloaded"
        ),
        source=request.source,
        core_ready=runtime.ready,
        fews=fews_state,
        weather=weather_state,
    )
