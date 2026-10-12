"""Explicit, read-only computations over one accepted external snapshot."""

from datetime import date, datetime, timezone
from decimal import Decimal
import re
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.api.app.core.runtime import runtime
from apps.api.app.routes.questions import _external_answer_text
from packages.data_sources.external_provenance import captured_source_manifest
from packages.data_sources.external_router import ExternalQuestionRoute, ExternalRouteStatus
from packages.data_sources.external_selection import ExternalSelection


router = APIRouter(prefix="/v1", tags=["external-queries"])


class ExternalQuerySelection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    market: str | None = Field(default=None, min_length=1, max_length=200, strict=True)
    admin_1: str | None = Field(default=None, min_length=1, max_length=200, strict=True)
    cpcv2: str | None = Field(default=None, min_length=1, max_length=40, strict=True)
    period_date: date | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    descending: bool = Field(default=True, strict=True)

    @field_validator("period_date", mode="before")
    @classmethod
    def explicit_date(cls, value):
        if value is not None and not (
            type(value) is date
            or isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
        ):
            raise ValueError("Observation dates must use YYYY-MM-DD.")
        return value

    @field_validator("valid_from", "valid_to", mode="before")
    @classmethod
    def explicit_time(cls, value):
        if value is not None and not (
            isinstance(value, datetime)
            or isinstance(value, str) and re.fullmatch(
                r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:[Zz]|[+-]\d{2}:\d{2})",
                value,
            )
        ):
            raise ValueError("Forecast times must use ISO date/time text with a timezone.")
        return value

    @field_validator("valid_from", "valid_to")
    @classmethod
    def utc_hours(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Forecast times must include a timezone.")
            try:
                value = value.astimezone(timezone.utc)
            except (OverflowError, ValueError) as error:
                raise ValueError("Forecast time cannot be represented in UTC.") from error
        return value

    @model_validator(mode="after")
    def valid_selection(self):
        self.as_selection()
        return self

    def as_selection(self) -> ExternalSelection:
        return ExternalSelection(**self.model_dump())


class ExternalQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: Literal[
        "market_price_ngn_per_kg", "forecast_temperature_2m_c",
        "forecast_relative_humidity_2m_pct", "forecast_precipitation_mm",
    ]
    operation: Literal["value", "rank", "range", "sum"]
    selection: ExternalQuerySelection = Field(default_factory=ExternalQuerySelection)
    snapshot_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    max_items: int = Field(default=5, ge=1, le=20, strict=True)


class ExternalQueryResponse(BaseModel):
    domain: Literal["external"] = "external"
    status: Literal["answered", "needs_clarification", "unavailable"]
    affects_core_readiness: Literal[False] = False
    metric_id: str
    source_id: str
    operation: str
    snapshot_id: str
    source: dict[str, Any]
    selection: dict[str, Any]
    rows: list[dict[str, Any]]
    reason: str | None
    answer_text: str
    time_semantics: str
    caution: str


@router.post("/external-queries", response_model=ExternalQueryResponse,
             summary="Query one saved external snapshot with explicit selectors")
def query_external(request: ExternalQueryRequest) -> ExternalQueryResponse:
    metric = runtime.external_metric_registry.get(request.metric_id)
    if request.operation not in metric.supported_operations:
        raise HTTPException(422, "The operation is not supported for this external metric.")
    selection = request.selection.as_selection()
    is_market = request.metric_id == "market_price_ngn_per_kg"
    market_fields = (selection.market, selection.admin_1, selection.cpcv2, selection.period_date)
    weather_fields = (selection.valid_from, selection.valid_to, selection.latitude, selection.longitude)
    if any(value is not None for value in (weather_fields if is_market else market_fields)):
        raise HTTPException(422, "Selectors must belong to the requested external source.")
    if "descending" in request.selection.model_fields_set and request.operation != "rank":
        raise HTTPException(422, "descending is only supported for market rankings.")
    if "max_items" in request.model_fields_set and request.operation != "rank":
        raise HTTPException(422, "max_items is only supported for market rankings.")
    if not runtime.ready:
        raise HTTPException(503, "AgDA is not ready.")

    # Capture once: provenance and rows must describe the same immutable snapshot,
    # even if a refresh replaces the runtime reference during this request.
    stored = runtime.market_price_snapshot() if is_market else runtime.weather_forecast_snapshot()
    if stored is None:
        raise HTTPException(503, "No validated local snapshot is available for this external source.")
    if request.snapshot_id is not None and request.snapshot_id != stored.snapshot_id:
        raise HTTPException(409, "The active snapshot changed; repeat the query with the new snapshot.")

    route = ExternalQuestionRoute(
        question="Explicit external query", normalized_question=("highest" if selection.descending else "lowest"),
        status=ExternalRouteStatus.ROUTED, metric_id=metric.metric_id,
        source_id=metric.source_id, operation=request.operation,
    )
    try:
        execution = runtime.external_metric_executor.execute(
            route, market_snapshot=stored if is_market else None,
            weather_snapshot=None if is_market else stored,
            max_items=request.max_items, selection=selection,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    source = captured_source_manifest(runtime.source_registry, metric.source_id, stored)
    return ExternalQueryResponse(
        status=execution.status.value, metric_id=metric.metric_id, source_id=metric.source_id,
        operation=request.operation, snapshot_id=stored.snapshot_id, source=source,
        selection=request.selection.model_dump(mode="json", exclude_none=True),
        rows=list(execution.rows), reason=execution.reason,
        answer_text=_external_answer_text(route, execution),
        time_semantics=metric.time_semantics, caution=metric.caution,
    )
