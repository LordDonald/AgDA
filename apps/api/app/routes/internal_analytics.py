from __future__ import annotations

import hmac
import logging

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
)

from apps.api.app.core.internal_analytics import (
    fetch_daily_usage,
    fetch_feedback_reasons,
    fetch_metric_usage,
    fetch_overview,
    fetch_status_summary,
)

from apps.api.app.core.settings import (
    settings,
)

from packages.contracts.internal_analytics import (
    AnalyticsDailyUsage,
    AnalyticsFeedbackReason,
    AnalyticsMetricUsage,
    AnalyticsOverview,
    AnalyticsStatusSummary,
)


logger = logging.getLogger(
    "agda.internal_analytics"
)


router = APIRouter(
    prefix="/v1/internal/analytics",
    tags=["internal-analytics"],
)


def _authorize(
    supplied_token: str | None,
) -> str:

    configured_token = (
        settings.internal_analytics_token
    )

    database_url = (
        settings.analytics_database_url
    )

    if (
        not configured_token
        or not database_url
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "Internal analytics is "
                "not configured."
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

    return database_url


def _query_failure(
    error: Exception,
) -> HTTPException:

    logger.warning(
        "Internal analytics query failed (%s).",
        type(error).__name__,
    )

    return HTTPException(
        status_code=503,
        detail=(
            "Internal analytics is "
            "temporarily unavailable."
        ),
    )


@router.get(
    "/overview",
    response_model=AnalyticsOverview,
)
def get_overview(
    internal_token: str | None = Header(
        default=None,
        alias="X-AgDA-Internal-Token",
    ),
) -> AnalyticsOverview:

    database_url = _authorize(
        internal_token
    )

    try:

        row = fetch_overview(
            database_url
        )

        return AnalyticsOverview.model_validate(
            row
        )

    except HTTPException:

        raise

    except Exception as error:

        raise _query_failure(
            error
        ) from error


@router.get(
    "/daily",
    response_model=list[AnalyticsDailyUsage],
)
def get_daily(
    internal_token: str | None = Header(
        default=None,
        alias="X-AgDA-Internal-Token",
    ),
) -> list[AnalyticsDailyUsage]:

    database_url = _authorize(
        internal_token
    )

    try:

        return [
            AnalyticsDailyUsage.model_validate(
                row
            )
            for row in fetch_daily_usage(
                database_url
            )
        ]

    except Exception as error:

        raise _query_failure(
            error
        ) from error


@router.get(
    "/metrics",
    response_model=list[AnalyticsMetricUsage],
)
def get_metrics(
    internal_token: str | None = Header(
        default=None,
        alias="X-AgDA-Internal-Token",
    ),
) -> list[AnalyticsMetricUsage]:

    database_url = _authorize(
        internal_token
    )

    try:

        return [
            AnalyticsMetricUsage.model_validate(
                row
            )
            for row in fetch_metric_usage(
                database_url
            )
        ]

    except Exception as error:

        raise _query_failure(
            error
        ) from error


@router.get(
    "/statuses",
    response_model=list[AnalyticsStatusSummary],
)
def get_statuses(
    internal_token: str | None = Header(
        default=None,
        alias="X-AgDA-Internal-Token",
    ),
) -> list[AnalyticsStatusSummary]:

    database_url = _authorize(
        internal_token
    )

    try:

        return [
            AnalyticsStatusSummary.model_validate(
                row
            )
            for row in fetch_status_summary(
                database_url
            )
        ]

    except Exception as error:

        raise _query_failure(
            error
        ) from error


@router.get(
    "/feedback-reasons",
    response_model=list[AnalyticsFeedbackReason],
)
def get_feedback_reasons(
    internal_token: str | None = Header(
        default=None,
        alias="X-AgDA-Internal-Token",
    ),
) -> list[AnalyticsFeedbackReason]:

    database_url = _authorize(
        internal_token
    )

    try:

        return [
            AnalyticsFeedbackReason.model_validate(
                row
            )
            for row in fetch_feedback_reasons(
                database_url
            )
        ]

    except Exception as error:

        raise _query_failure(
            error
        ) from error
