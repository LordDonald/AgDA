"""Read-only access to the accepted local FEWS monthly snapshot."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from apps.api.app.core.runtime import runtime
from packages.data_sources.catalog import source_state_manifest
from packages.data_sources.contracts import evaluate_freshness
from packages.data_sources.market_prices import MarketPriceRecord
from packages.data_sources.providers.fews_market_prices import FEWS_MARKET_SOURCE_ID
from packages.data_sources.registry import SourceState
from packages.data_sources.snapshot_store import effective_fews_query


router = APIRouter(prefix="/v1", tags=["market-prices"])


class MarketPricePage(BaseModel):
    snapshot_id: str
    source: dict[str, Any]
    snapshot_restore_status: str
    filters: dict[str, str]
    total: int
    limit: int
    offset: int
    returned_count: int
    next_offset: int | None
    # The typed response preserves Decimal values as JSON strings.
    records: list[MarketPriceRecord]


@router.get(
    "/market-prices",
    response_model=MarketPricePage,
    summary="Read saved monthly market-price observations",
    description=(
        "Reads only the loaded local snapshot, without fetching from FEWS. "
        "Coverage is limited to source.query. Text filters are exact matches "
        "ignoring case and surrounding whitespace; dates are inclusive. "
        "Records retain saved order. Pass the returned snapshot_id on subsequent "
        "pages to detect a reload. Source freshness measures retrieval age, "
        "not observation age. Prices and coordinates are decimal strings."
    ),
    responses={
        409: {"description": "The requested snapshot is no longer active; restart pagination."},
        503: {"description": "The API or a validated local market-price snapshot is unavailable."},
    },
)
def market_prices(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    snapshot_id: Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")] = None,
    admin_1: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    market: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    cpcv2: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> MarketPricePage:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date.")

    filters = {}
    for name, value in (("admin_1", admin_1), ("market", market), ("cpcv2", cpcv2)):
        if value is not None:
            trimmed = value.strip()
            if not trimmed:
                raise HTTPException(status_code=422, detail=f"{name} must not be blank.")
            filters[name] = trimmed

    if not runtime.ready:
        raise HTTPException(status_code=503, detail="AgDA is not ready.")
    stored = runtime.market_price_snapshot()
    if stored is None:
        raise HTTPException(status_code=503, detail="No validated local market-price snapshot is available.")
    if snapshot_id is not None and snapshot_id != stored.snapshot_id:
        raise HTTPException(status_code=409, detail="The active snapshot changed; restart pagination.")

    # Hold this immutable snapshot for the whole response, including its metadata.
    matches = [
        record for record in stored.result.records
        if all((getattr(record, name) or "").strip().casefold() == value.casefold()
               for name, value in filters.items())
        and (start_date is None or record.period_date >= start_date)
        and (end_date is None or record.period_date <= end_date)
    ]
    records = matches[offset:offset + limit]
    following_offset = offset + len(records)
    for name, value in (("start_date", start_date), ("end_date", end_date)):
        if value is not None:
            filters[name] = value.isoformat()

    snapshot = stored.result.snapshot
    definition = runtime.source_registry.get_definition(FEWS_MARKET_SOURCE_ID)
    source = source_state_manifest(SourceState(
        definition=definition,
        snapshot=snapshot,
        freshness=evaluate_freshness(definition, snapshot),
    ))
    source["query"] = effective_fews_query(stored.query)
    return MarketPricePage(
        snapshot_id=stored.snapshot_id,
        source=source,
        snapshot_restore_status=runtime.fews_snapshot_restore_status,
        filters=filters,
        total=len(matches),
        limit=limit,
        offset=offset,
        returned_count=len(records),
        next_offset=following_offset if following_offset < len(matches) else None,
        records=records,
    )
