from __future__ import annotations

import json
import logging

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Mapping,
)

import psycopg

from packages.contracts.answer import (
    AgDAAnswer,
)


logger = logging.getLogger(
    "agda.product"
)

logger.setLevel(
    logging.INFO
)


_INSERT_PRODUCT_EVENT_SQL = """
INSERT INTO product_events (
    event_name,
    event_timestamp,
    request_id,
    status,
    metric_id,
    operation,
    group_by,
    was_follow_up,
    question_length,
    result_count,
    evidence_grade,
    visualization_recommended,
    processing_duration_ms,
    data_version,
    metric_version
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
)
ON CONFLICT (
    request_id,
    event_name
)
DO NOTHING
"""


def _result_count(
    answer: AgDAAnswer,
) -> int:

    if answer.result is None:
        return 0

    if isinstance(
        answer.result,
        list,
    ):
        return len(
            answer.result
        )

    return 1


def emit_question_event(
    *,
    request_id: str | None,
    environment: str,
    answer: AgDAAnswer,
    was_follow_up: bool,
    question_length: int,
    processing_duration_ms: float,
) -> dict[str, Any] | None:
    """
    Build and log privacy-conscious product telemetry.

    Raw question text, answer text, filters,
    entities, and conversation identifiers
    are intentionally excluded.

    Telemetry failures must never break
    a user-facing AgDA request.
    """

    try:

        specification = (
            answer.question_specification
            or {}
        )

        evidence_grade = (
            answer.evidence.evidence_grade
            if answer.evidence is not None
            else None
        )

        visualization_recommended = bool(
            answer.visualization is not None
            and answer.visualization.recommended
        )

        payload: dict[str, Any] = {
            "event":
                "agda_question",

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "request_id":
                request_id,

            "environment":
                environment,

            "status":
                answer.status,

            "metric_id":
                specification.get(
                    "metric_id"
                ),

            "operation":
                specification.get(
                    "operation"
                ),

            "group_by":
                specification.get(
                    "group_by"
                ),

            "was_follow_up":
                was_follow_up,

            "question_length":
                question_length,

            "result_count":
                _result_count(
                    answer
                ),

            "evidence_grade":
                evidence_grade,

            "visualization_recommended":
                visualization_recommended,

            "processing_duration_ms":
                processing_duration_ms,

            "data_version":
                answer.data_version,

            "metric_version":
                answer.metric_version,
        }

        logger.info(
            json.dumps(
                payload,
                separators=(
                    ",",
                    ":",
                ),
                sort_keys=True,
            )
        )

        return payload

    except Exception as error:

        logger.warning(
            "Product analytics emit failed (%s).",
            type(error).__name__,
        )

        return None


def persist_question_event(
    *,
    database_url: str | None,
    payload: Mapping[str, Any] | None,
) -> None:
    """
    Persist one privacy-safe product event.

    Persistence is deliberately fail-open.
    Database failures must never affect
    the user-facing question response.
    """

    if (
        not database_url
        or payload is None
    ):
        return

    request_id = payload.get(
        "request_id"
    )

    if not request_id:

        logger.warning(
            "Product analytics persistence skipped: "
            "missing request ID."
        )

        return

    try:

        values = (
            payload.get(
                "event"
            ),
            payload.get(
                "timestamp"
            ),
            request_id,
            payload.get(
                "status"
            ),
            payload.get(
                "metric_id"
            ),
            payload.get(
                "operation"
            ),
            payload.get(
                "group_by"
            ),
            payload.get(
                "was_follow_up"
            ),
            payload.get(
                "question_length"
            ),
            payload.get(
                "result_count"
            ),
            payload.get(
                "evidence_grade"
            ),
            payload.get(
                "visualization_recommended"
            ),
            payload.get(
                "processing_duration_ms"
            ),
            payload.get(
                "data_version"
            ),
            payload.get(
                "metric_version"
            ),
        )

        with psycopg.connect(
            database_url,
            connect_timeout=5,
        ) as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    _INSERT_PRODUCT_EVENT_SQL,
                    values,
                )

    except Exception as error:

        logger.warning(
            "Product analytics persistence failed (%s).",
            type(error).__name__,
        )
