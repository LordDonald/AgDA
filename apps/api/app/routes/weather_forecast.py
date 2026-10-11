"""Read-only access to the accepted local Open-Meteo forecast snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from apps.api.app.core.runtime import runtime
from packages.data_sources.catalog import (
    source_state_manifest,
)
from packages.data_sources.contracts import (
    evaluate_freshness,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
)
from packages.data_sources.registry import (
    SourceState,
)
from packages.data_sources.weather_forecasts import (
    WeatherForecastRecord,
)
from packages.data_sources.weather_snapshot_store import (
    effective_open_meteo_query,
)


router = APIRouter(
    prefix="/v1",
    tags=["weather-forecast"],
)


class WeatherForecastPage(BaseModel):
    snapshot_id: str
    source: dict[str, Any]
    weather_snapshot_restore_status: str
    filters: dict[str, str]
    total: int
    limit: int
    offset: int
    returned_count: int
    next_offset: int | None
    records: list[WeatherForecastRecord]


def _utc_filter(
    name: str,
    value: datetime | None,
) -> datetime | None:

    if value is None:
        return None

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise HTTPException(
            status_code=422,
            detail=f"{name} must include a timezone.",
        )

    return value.astimezone(
        timezone.utc
    )


@router.get(
    "/weather-forecast",
    response_model=WeatherForecastPage,
    summary="Read saved hourly weather forecast",
    description=(
        "Reads only the loaded local weather snapshot, without fetching "
        "from Open-Meteo. Coverage is limited to source.query and the saved "
        "forecast-valid window. valid_from and valid_to are inclusive and "
        "must include a timezone. Pass snapshot_id on subsequent pages to "
        "detect a reload. Source freshness measures AgDA retrieval age, "
        "not forecast accuracy or model issue age."
    ),
    responses={
        409: {
            "description":
                "The requested snapshot is no longer active; "
                "restart pagination."
        },
        503: {
            "description":
                "The API or a validated local weather snapshot "
                "is unavailable."
        },
    },
)
def weather_forecast(
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=168,
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
        ),
    ] = 0,
    snapshot_id: Annotated[
        str | None,
        Query(
            pattern=r"^[0-9a-f]{64}$"
        ),
    ] = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> WeatherForecastPage:

    valid_from = _utc_filter(
        "valid_from",
        valid_from,
    )

    valid_to = _utc_filter(
        "valid_to",
        valid_to,
    )

    if (
        valid_from is not None
        and valid_to is not None
        and valid_from > valid_to
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "valid_from must not be after valid_to."
            ),
        )

    if not runtime.ready:
        raise HTTPException(
            status_code=503,
            detail="AgDA is not ready.",
        )

    stored = runtime.weather_forecast_snapshot()

    if stored is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "No validated local weather forecast "
                "snapshot is available."
            ),
        )

    if (
        snapshot_id is not None
        and snapshot_id != stored.snapshot_id
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "The active snapshot changed; "
                "restart pagination."
            ),
        )

    matches = [
        record
        for record
        in stored.result.records
        if (
            valid_from is None
            or record.valid_at >= valid_from
        )
        and (
            valid_to is None
            or record.valid_at <= valid_to
        )
    ]

    records = matches[
        offset:
        offset + limit
    ]

    following_offset = (
        offset
        + len(
            records
        )
    )

    filters = {}

    if valid_from is not None:
        filters[
            "valid_from"
        ] = valid_from.isoformat()

    if valid_to is not None:
        filters[
            "valid_to"
        ] = valid_to.isoformat()

    snapshot = stored.result.snapshot

    definition = (
        runtime.source_registry.get_definition(
            OPEN_METEO_FORECAST_SOURCE_ID
        )
    )

    source = source_state_manifest(
        SourceState(
            definition=definition,
            snapshot=snapshot,
            freshness=evaluate_freshness(
                definition,
                snapshot,
            ),
        )
    )

    source["query"] = (
        effective_open_meteo_query(
            stored.query
        )
    )

    return WeatherForecastPage(
        snapshot_id=
            stored.snapshot_id,
        source=
            source,
        weather_snapshot_restore_status=
            runtime.weather_snapshot_restore_status,
        filters=
            filters,
        total=
            len(
                matches
            ),
        limit=
            limit,
        offset=
            offset,
        returned_count=
            len(
                records
            ),
        next_offset=(
            following_offset
            if following_offset
            < len(
                matches
            )
            else None
        ),
        records=
            records,
    )
