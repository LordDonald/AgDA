from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


# ============================================================
# EVIDENCE
# ============================================================

class EvidencePayload(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    evidence_grade: str

    records: int

    households: int | None = None

    clusters: int | None = None

    value_available: int | None = None

    denominator_households: int | None = None

    minimum_evidence_threshold: int

    claim_type: str | None = None

    causal_interpretation_allowed: bool

    methodological_caution: str | None = None


# ============================================================
# VISUALIZATION
# ============================================================

class VisualizationPayload(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    recommended: bool

    visual_type: str | None = None

    title: str | None = None

    dimension: str | None = None

    metric_id: str | None = None

    unit: str | None = None

    max_items: int | None = None

    data: list[dict[str, Any]] | dict[str, Any] | None = None


# ============================================================
# CLARIFICATION
# ============================================================

class ClarificationPayload(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    clarification_required: bool

    prompt: str

    options: list[str] = Field(
        default_factory=list
    )

    resolved_entities: dict[str, list[str]] = Field(
        default_factory=dict
    )

    candidate_metrics: list[str] = Field(
        default_factory=list
    )


# ============================================================
# REFRAME
# ============================================================

class ReframePayload(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    original_request_type: str

    reason: str

    supported_alternative: str | None = None


# ============================================================
# AgDA ANSWER
# ============================================================

class AgDAAnswer(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    status: str

    question: str

    conversation_id: str | None = None

    answer_text: str

    question_specification: dict[str, Any] | None = None

    result: dict[str, Any] | list[dict[str, Any]] | None = None

    evidence: EvidencePayload | None = None

    visualization: VisualizationPayload | None = None

    clarification: ClarificationPayload | None = None

    reframe: ReframePayload | None = None

    warnings: list[str] = Field(
        default_factory=list
    )

    data_version: str

    metric_version: str | None = None