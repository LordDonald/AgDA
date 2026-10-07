from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)

from apps.api.app.routes import (
    internal_analytics,
)


TEST_TOKEN = (
    "test_internal_analytics_token_123456"
)


def _settings():

    return SimpleNamespace(
        internal_analytics_token=
            TEST_TOKEN,

        analytics_database_url=
            "postgresql://example.invalid/test",
    )


def _overview():

    return {
        "total_questions": 3,
        "answered_count": 3,
        "clarification_count": 0,
        "reframe_count": 0,
        "unsupported_count": 0,
        "follow_up_count": 0,
        "follow_up_rate_pct": 0.0,
        "visualization_count": 3,
        "avg_processing_ms": 148.01,
        "p95_processing_ms": 154.72,
        "feedback_count": 2,
        "helpful_count": 1,
        "not_helpful_count": 1,
        "helpful_rate_pct": 50.0,
    }


def main():

    original_settings = (
        internal_analytics.settings
    )

    original_overview = (
        internal_analytics.fetch_overview
    )

    original_daily = (
        internal_analytics.fetch_daily_usage
    )

    original_metrics = (
        internal_analytics.fetch_metric_usage
    )

    original_statuses = (
        internal_analytics.fetch_status_summary
    )

    original_reasons = (
        internal_analytics.fetch_feedback_reasons
    )


    internal_analytics.settings = (
        _settings()
    )

    internal_analytics.fetch_overview = (
        lambda database_url:
            _overview()
    )

    internal_analytics.fetch_daily_usage = (
        lambda database_url: [
            {
                "usage_date":
                    date(
                        2026,
                        10,
                        7,
                    ),

                "total_questions":
                    2,

                "answered_count":
                    2,

                "clarification_count":
                    0,

                "reframe_count":
                    0,

                "unsupported_count":
                    0,

                "follow_up_count":
                    0,

                "follow_up_rate_pct":
                    0.0,

                "visualization_count":
                    2,

                "avg_processing_ms":
                    150.0,

                "p95_processing_ms":
                    155.0,
            }
        ]
    )

    internal_analytics.fetch_metric_usage = (
        lambda database_url: [
            {
                "metric_id":
                    "crop_grower_share",

                "question_count":
                    3,

                "follow_up_count":
                    0,

                "avg_processing_ms":
                    148.01,

                "p95_processing_ms":
                    154.72,

                "feedback_count":
                    2,

                "helpful_count":
                    1,

                "not_helpful_count":
                    1,

                "helpful_rate_pct":
                    50.0,
            }
        ]
    )

    internal_analytics.fetch_status_summary = (
        lambda database_url: [
            {
                "status":
                    "answered",

                "question_count":
                    3,

                "share_pct":
                    100.0,
            }
        ]
    )

    internal_analytics.fetch_feedback_reasons = (
        lambda database_url: [
            {
                "reason_code":
                    "unclear",

                "feedback_count":
                    1,

                "share_pct":
                    100.0,
            }
        ]
    )


    try:

        with TestClient(
            app,
            raise_server_exceptions=False,
        ) as client:

            missing = client.get(
                "/v1/internal/analytics/overview"
            )

            assert (
                missing.status_code
                == 401
            )


            wrong = client.get(
                "/v1/internal/analytics/overview",

                headers={
                    "X-AgDA-Internal-Token":
                        "wrong-token"
                },
            )

            assert (
                wrong.status_code
                == 401
            )


            headers = {
                "X-AgDA-Internal-Token":
                    TEST_TOKEN
            }


            overview = client.get(
                "/v1/internal/analytics/overview",
                headers=headers,
            )

            assert (
                overview.status_code
                == 200
            )

            assert (
                overview.json()[
                    "total_questions"
                ]
                == 3
            )

            assert (
                overview.json()[
                    "helpful_rate_pct"
                ]
                == 50.0
            )


            daily = client.get(
                "/v1/internal/analytics/daily",
                headers=headers,
            )

            assert (
                daily.status_code
                == 200
            )

            assert (
                daily.json()[0][
                    "usage_date"
                ]
                == "2026-10-07"
            )


            metrics = client.get(
                "/v1/internal/analytics/metrics",
                headers=headers,
            )

            assert (
                metrics.status_code
                == 200
            )

            assert (
                metrics.json()[0][
                    "metric_id"
                ]
                == "crop_grower_share"
            )


            statuses = client.get(
                "/v1/internal/analytics/statuses",
                headers=headers,
            )

            assert (
                statuses.status_code
                == 200
            )

            assert (
                statuses.json()[0][
                    "status"
                ]
                == "answered"
            )


            reasons = client.get(
                (
                    "/v1/internal/analytics/"
                    "feedback-reasons"
                ),
                headers=headers,
            )

            assert (
                reasons.status_code
                == 200
            )

            assert (
                reasons.json()[0][
                    "reason_code"
                ]
                == "unclear"
            )


            def fail_query(
                database_url,
            ):

                raise RuntimeError(
                    "Synthetic analytics failure"
                )


            internal_analytics.fetch_overview = (
                fail_query
            )


            failed = client.get(
                "/v1/internal/analytics/overview",
                headers=headers,
            )

            assert (
                failed.status_code
                == 503
            )

            assert (
                failed.json()[
                    "detail"
                ]
                == (
                    "Internal analytics is "
                    "temporarily unavailable."
                )
            )


        print(
            "Internal analytics auth: PASSED"
        )

        print(
            "Internal analytics contracts: PASSED"
        )

        print(
            "Internal analytics DB failure: PASSED"
        )

        print(
            "INTERNAL ANALYTICS API TEST: PASSED"
        )

    finally:

        internal_analytics.settings = (
            original_settings
        )

        internal_analytics.fetch_overview = (
            original_overview
        )

        internal_analytics.fetch_daily_usage = (
            original_daily
        )

        internal_analytics.fetch_metric_usage = (
            original_metrics
        )

        internal_analytics.fetch_status_summary = (
            original_statuses
        )

        internal_analytics.fetch_feedback_reasons = (
            original_reasons
        )


if __name__ == "__main__":

    main()
