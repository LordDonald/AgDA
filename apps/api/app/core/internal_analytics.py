from __future__ import annotations

from typing import Any

import psycopg

from psycopg.rows import (
    dict_row,
)


_OVERVIEW_SQL = """
SELECT *
FROM analytics_overview
"""


_DAILY_SQL = """
SELECT *
FROM analytics_daily_usage
ORDER BY usage_date DESC
"""


_METRICS_SQL = """
SELECT *
FROM analytics_metric_usage
ORDER BY
    question_count DESC,
    metric_id
"""


_STATUSES_SQL = """
SELECT *
FROM analytics_status_summary
ORDER BY
    question_count DESC,
    status
"""


_FEEDBACK_REASONS_SQL = """
SELECT *
FROM analytics_feedback_reasons
ORDER BY
    feedback_count DESC,
    reason_code
"""


def _fetch_one(
    *,
    database_url: str,
    sql: str,
) -> dict[str, Any]:

    with psycopg.connect(
        database_url,
        connect_timeout=5,
        row_factory=dict_row,
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                sql
            )

            row = cursor.fetchone()

    if row is None:

        raise RuntimeError(
            "Internal analytics query "
            "returned no row."
        )

    return dict(row)


def _fetch_all(
    *,
    database_url: str,
    sql: str,
) -> list[dict[str, Any]]:

    with psycopg.connect(
        database_url,
        connect_timeout=5,
        row_factory=dict_row,
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                sql
            )

            rows = cursor.fetchall()

    return [
        dict(row)
        for row in rows
    ]


def fetch_overview(
    database_url: str,
) -> dict[str, Any]:

    return _fetch_one(
        database_url=
            database_url,
        sql=
            _OVERVIEW_SQL,
    )


def fetch_daily_usage(
    database_url: str,
) -> list[dict[str, Any]]:

    return _fetch_all(
        database_url=
            database_url,
        sql=
            _DAILY_SQL,
    )


def fetch_metric_usage(
    database_url: str,
) -> list[dict[str, Any]]:

    return _fetch_all(
        database_url=
            database_url,
        sql=
            _METRICS_SQL,
    )


def fetch_status_summary(
    database_url: str,
) -> list[dict[str, Any]]:

    return _fetch_all(
        database_url=
            database_url,
        sql=
            _STATUSES_SQL,
    )


def fetch_feedback_reasons(
    database_url: str,
) -> list[dict[str, Any]]:

    return _fetch_all(
        database_url=
            database_url,
        sql=
            _FEEDBACK_REASONS_SQL,
    )
