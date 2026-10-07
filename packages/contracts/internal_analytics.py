from __future__ import annotations

from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
)


class AnalyticsOverview(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    total_questions: int
    answered_count: int
    clarification_count: int
    reframe_count: int
    unsupported_count: int
    follow_up_count: int
    follow_up_rate_pct: float | None
    visualization_count: int
    avg_processing_ms: float | None
    p95_processing_ms: float | None
    feedback_count: int
    helpful_count: int
    not_helpful_count: int
    helpful_rate_pct: float | None


class AnalyticsDailyUsage(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    usage_date: date
    total_questions: int
    answered_count: int
    clarification_count: int
    reframe_count: int
    unsupported_count: int
    follow_up_count: int
    follow_up_rate_pct: float | None
    visualization_count: int
    avg_processing_ms: float | None
    p95_processing_ms: float | None


class AnalyticsMetricUsage(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    metric_id: str
    question_count: int
    follow_up_count: int
    avg_processing_ms: float | None
    p95_processing_ms: float | None
    feedback_count: int
    helpful_count: int
    not_helpful_count: int
    helpful_rate_pct: float | None


class AnalyticsStatusSummary(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    status: str
    question_count: int
    share_pct: float | None


class AnalyticsFeedbackReason(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    reason_code: str
    feedback_count: int
    share_pct: float | None
