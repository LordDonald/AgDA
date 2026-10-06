from __future__ import annotations

import json
import logging

from datetime import (
    datetime,
    timezone,
)

from packages.contracts.answer import (
    AgDAAnswer,
)


logger = logging.getLogger(
    "agda.product"
)

logger.setLevel(
    logging.INFO
)


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
) -> None:
    """
    Emit privacy-conscious product telemetry.

    Raw question text, answer text, filters,
    entities, and conversation identifiers
    are intentionally excluded.
    """

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

    payload = {
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

    try:

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

    except Exception:

        # Product telemetry must never break
        # a user-facing AgDA request.
        logger.exception(
            "Product analytics emit failed."
        )