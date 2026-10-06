from __future__ import annotations

import io
import json
import logging

from apps.api.app.core.product_analytics import (
    emit_question_event,
)

from packages.contracts.answer import (
    AgDAAnswer,
    EvidencePayload,
    VisualizationPayload,
)


def capture_event(
    answer: AgDAAnswer,
) -> dict:

    stream = io.StringIO()

    handler = logging.StreamHandler(
        stream
    )

    logger = logging.getLogger(
        "agda.product"
    )

    previous_level = logger.level
    previous_propagate = logger.propagate

    logger.setLevel(
        logging.INFO
    )

    logger.propagate = False

    logger.addHandler(
        handler
    )

    try:

        emit_question_event(
            request_id=
                "req_product_test_001",

            environment=
                "test",

            answer=
                answer,

            was_follow_up=
                True,

            question_length=
                27,

            processing_duration_ms=
                123.45,
        )

    finally:

        logger.removeHandler(
            handler
        )

        logger.setLevel(
            previous_level
        )

        logger.propagate = (
            previous_propagate
        )

    payload = json.loads(
        stream.getvalue().strip()
    )

    return payload


def test_product_event() -> None:

    answer = AgDAAnswer(
        status=
            "answered",

        question=
            "What about rice?",

        conversation_id=
            "secret-conversation-id",

        answer_text=
            "Sensitive answer text",

        question_specification={
            "metric_id":
                "crop_grower_share",

            "operation":
                "value",

            "filters": {
                "state":
                    "Kaduna",

                "crop":
                    "RICE",
            },

            "group_by":
                None,

            "ascending":
                False,

            "top_n":
                None,

            "minimum_records":
                None,

            "metric_version":
                "1.0.0",
        },

        result={
            "value":
                0.3154,

            "unit":
                "proportion",
        },

        evidence=
            EvidencePayload(
                evidence_grade=
                    "Adequate",

                records=
                    54,

                households=
                    54,

                clusters=
                    None,

                value_available=
                    169,

                denominator_households=
                    169,

                minimum_evidence_threshold=
                    30,

                claim_type=
                    "descriptive",

                causal_interpretation_allowed=
                    False,

                methodological_caution=
                    "Test caution.",
            ),

        visualization=
            VisualizationPayload(
                recommended=
                    False,

                visual_type=
                    None,

                title=
                    None,

                dimension=
                    None,

                metric_id=
                    None,

                unit=
                    None,

                max_items=
                    None,

                data=
                    None,
            ),

        clarification=
            None,

        reframe=
            None,

        warnings=[],

        data_version=
            "wave5_v1",

        metric_version=
            "1.0.0",
    )

    payload = capture_event(
        answer
    )

    assert (
        payload["event"]
        == "agda_question"
    )

    assert (
        payload["request_id"]
        == "req_product_test_001"
    )

    assert (
        payload["environment"]
        == "test"
    )

    assert (
        payload["status"]
        == "answered"
    )

    assert (
        payload["metric_id"]
        == "crop_grower_share"
    )

    assert (
        payload["operation"]
        == "value"
    )

    assert (
        payload["group_by"]
        is None
    )

    assert (
        payload["was_follow_up"]
        is True
    )

    assert (
        payload["question_length"]
        == 27
    )

    assert (
        payload["result_count"]
        == 1
    )

    assert (
        payload["evidence_grade"]
        == "Adequate"
    )

    assert (
        payload[
            "visualization_recommended"
        ]
        is False
    )

    assert (
        payload[
            "processing_duration_ms"
        ]
        == 123.45
    )

    assert (
        payload["data_version"]
        == "wave5_v1"
    )

    assert (
        payload["metric_version"]
        == "1.0.0"
    )


    # Privacy contract:
    # raw user content and conversation identity
    # must never enter product telemetry.

    serialized = json.dumps(
        payload
    )

    assert (
        "What about rice?"
        not in serialized
    )

    assert (
        "Sensitive answer text"
        not in serialized
    )

    assert (
        "secret-conversation-id"
        not in serialized
    )

    assert (
        "Kaduna"
        not in serialized
    )

    assert (
        "RICE"
        not in serialized
    )


if __name__ == "__main__":

    test_product_event()

    print(
        "Product analytics payload: PASSED"
    )

    print(
        "Product analytics privacy contract: PASSED"
    )

    print(
        "PRODUCT ANALYTICS TEST: PASSED"
    )