"""Authenticated runtime adoption of validated external snapshots."""

from __future__ import annotations

import hmac
from threading import Lock
from typing import Literal

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Response,
)
from pydantic import BaseModel

from apps.api.app.core.runtime import runtime
from apps.api.app.core.settings import settings


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
