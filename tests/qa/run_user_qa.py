from __future__ import annotations

from collections import (
    Counter,
    defaultdict,
)

from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)

from user_question_bank import (
    USER_QUESTION_BANK,
)


# ============================================================
# RESULT HELPERS
# ============================================================

def make_result(
    case_id: str,
    persona: str,
    passed: bool,
    reason: str | None = None,
    actual_status: str | None = None,
    actual_metric: str | None = None,
) -> dict:

    return {
        "case_id":
            case_id,

        "persona":
            persona,

        "passed":
            passed,

        "reason":
            reason,

        "actual_status":
            actual_status,

        "actual_metric":
            actual_metric,
    }


def metric_from_payload(
    payload: dict,
) -> str | None:

    specification = (
        payload.get(
            "question_specification"
        )
    )


    if not specification:

        return None


    return specification.get(
        "metric_id"
    )


# ============================================================
# SINGLE-TURN CASE
# ============================================================

def run_single_case(
    client: TestClient,
    case: dict,
) -> dict:

    case_id = (
        case["id"]
    )

    persona = (
        case["persona"]
    )

    expected_status = (
        case[
            "expected_status"
        ]
    )

    expected_metric = (
        case[
            "expected_metric"
        ]
    )


    response = client.post(
        "/v1/questions",

        json={
            "question":
                case[
                    "question"
                ],

            "conversation_id":
                f"qa_{case_id}",

            "max_rank_items":
                5,

            "include_visualization":
                True,

            "locale":
                "en-NG",
        },
    )


    if response.status_code != 200:

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Unexpected HTTP status "
                f"{response.status_code}: "
                f"{response.text}"
            ),
        )


    payload = (
        response.json()
    )


    actual_status = (
        payload.get(
            "status"
        )
    )

    actual_metric = (
        metric_from_payload(
            payload
        )
    )


    # --------------------------------------------------------
    # Status must match
    # --------------------------------------------------------

    if (
        actual_status
        != expected_status
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Status mismatch. "
                f"Expected {expected_status!r}, "
                f"received {actual_status!r}."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    # --------------------------------------------------------
    # Metric must match where one is expected
    # --------------------------------------------------------

    if (
        expected_metric
        is not None
        and actual_metric
        != expected_metric
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Metric mismatch. "
                f"Expected {expected_metric!r}, "
                f"received {actual_metric!r}."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    # --------------------------------------------------------
    # Answered questions must actually contain results
    # --------------------------------------------------------

    if (
        expected_status
        == "answered"
        and payload.get(
            "result"
        )
        is None
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Answered response contained "
                "no analytical result."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    # --------------------------------------------------------
    # Guardrail outcomes must not expose fake results
    # --------------------------------------------------------

    if (
        expected_status
        in {
            "unsupported",
            "reframe_required",
            "needs_clarification",
        }
        and payload.get(
            "result"
        )
        is not None
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Guardrail response unexpectedly "
                "contained an analytical result."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    # --------------------------------------------------------
    # Every answer must contain human-readable language
    # --------------------------------------------------------

    answer_text = (
        payload.get(
            "answer_text"
        )
    )


    if (
        not isinstance(
            answer_text,
            str,
        )
        or not answer_text.strip()
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Response contained no usable "
                "answer_text."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    # --------------------------------------------------------
    # Data provenance must always be present
    # --------------------------------------------------------

    if (
        payload.get(
            "data_version"
        )
        != "wave5_v1"
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Unexpected or missing data_version."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    return make_result(
        case_id=
            case_id,

        persona=
            persona,

        passed=
            True,

        actual_status=
            actual_status,

        actual_metric=
            actual_metric,
    )


# ============================================================
# CONVERSATION CASE
# ============================================================

def run_conversation_case(
    client: TestClient,
    case: dict,
) -> dict:

    case_id = (
        case["id"]
    )

    persona = (
        case["persona"]
    )

    conversation_id = (
        f"qa_{case_id}"
    )


    final_payload = None


    for turn_number, question in enumerate(
        case[
            "conversation"
        ],
        start=1,
    ):

        response = client.post(
            "/v1/questions",

            json={
                "question":
                    question,

                "conversation_id":
                    conversation_id,

                "max_rank_items":
                    5,

                "include_visualization":
                    True,

                "locale":
                    "en-NG",
            },
        )


        if response.status_code != 200:

            return make_result(
                case_id=
                    case_id,

                persona=
                    persona,

                passed=
                    False,

                reason=(
                    f"Conversation turn {turn_number} "
                    f"returned HTTP "
                    f"{response.status_code}: "
                    f"{response.text}"
                ),
            )


        final_payload = (
            response.json()
        )


        returned_conversation_id = (
            final_payload.get(
                "conversation_id"
            )
        )


        if (
            returned_conversation_id
            != conversation_id
        ):

            return make_result(
                case_id=
                    case_id,

                persona=
                    persona,

                passed=
                    False,

                reason=(
                    f"Conversation ID changed at "
                    f"turn {turn_number}."
                ),
            )


    if final_payload is None:

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=
                "Conversation produced no response.",
        )


    expected_status = (
        case[
            "expected_final_status"
        ]
    )

    expected_metric = (
        case[
            "expected_final_metric"
        ]
    )


    actual_status = (
        final_payload.get(
            "status"
        )
    )


    actual_metric = (
        metric_from_payload(
            final_payload
        )
    )


    if (
        actual_status
        != expected_status
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Final conversation status mismatch. "
                f"Expected {expected_status!r}, "
                f"received {actual_status!r}."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    if (
        actual_metric
        != expected_metric
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Final conversation metric mismatch. "
                f"Expected {expected_metric!r}, "
                f"received {actual_metric!r}."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    if (
        final_payload.get(
            "result"
        )
        is None
    ):

        return make_result(
            case_id=
                case_id,

            persona=
                persona,

            passed=
                False,

            reason=(
                "Final conversational answer "
                "contained no analytical result."
            ),

            actual_status=
                actual_status,

            actual_metric=
                actual_metric,
        )


    return make_result(
        case_id=
            case_id,

        persona=
            persona,

        passed=
            True,

        actual_status=
            actual_status,

        actual_metric=
            actual_metric,
    )


# ============================================================
# MAIN QA RUNNER
# ============================================================

def main():

    print(
        "\n========================================"
    )

    print(
        "AgDA USER QUESTION QA"
    )

    print(
        "========================================"
    )


    results = []


    with TestClient(
        app,
        raise_server_exceptions=False,
    ) as client:

        for index, case in enumerate(
            USER_QUESTION_BANK,
            start=1,
        ):

            print(
                "\n----------------------------------------"
            )

            print(
                f"[{index}/{len(USER_QUESTION_BANK)}] "
                f"{case['id']} "
                f"({case['persona']})"
            )


            if (
                "conversation"
                in case
            ):

                result = (
                    run_conversation_case(
                        client,
                        case,
                    )
                )

            else:

                print(
                    "QUESTION:",
                    case[
                        "question"
                    ]
                )


                result = (
                    run_single_case(
                        client,
                        case,
                    )
                )


            results.append(
                result
            )


            if result[
                "passed"
            ]:

                print(
                    "RESULT: PASS"
                )

            else:

                print(
                    "RESULT: FAIL"
                )

                print(
                    "REASON:",
                    result[
                        "reason"
                    ]
                )


    # ========================================================
    # SUMMARY
    # ========================================================

    total = len(
        results
    )

    passed_count = sum(
        1
        for result in results
        if result[
            "passed"
        ]
    )

    failed = [
        result
        for result in results
        if not result[
            "passed"
        ]
    ]


    by_persona = (
        defaultdict(
            lambda: {
                "passed": 0,
                "failed": 0,
            }
        )
    )


    for result in results:

        key = (
            "passed"
            if result[
                "passed"
            ]
            else "failed"
        )


        by_persona[
            result[
                "persona"
            ]
        ][
            key
        ] += 1


    status_counts = Counter(
        result[
            "actual_status"
        ]
        for result in results
        if result[
            "actual_status"
        ]
        is not None
    )


    print(
        "\n========================================"
    )

    print(
        "USER QA SUMMARY"
    )

    print(
        "========================================"
    )


    print(
        "\nOverall:",
        passed_count,
        "/",
        total,
        "passed",
    )


    print(
        "\nBy persona:"
    )


    for persona in sorted(
        by_persona
    ):

        counts = (
            by_persona[
                persona
            ]
        )


        print(
            f"  {persona}: "
            f"{counts['passed']} passed, "
            f"{counts['failed']} failed"
        )


    print(
        "\nResponse statuses:"
    )


    for status, count in sorted(
        status_counts.items()
    ):

        print(
            f"  {status}: {count}"
        )


    if failed:

        print(
            "\n========================================"
        )

        print(
            "FAILED CASES"
        )

        print(
            "========================================"
        )


        for result in failed:

            print(
                f"\n{result['case_id']}"
            )

            print(
                "Persona:",
                result[
                    "persona"
                ]
            )

            print(
                "Reason:",
                result[
                    "reason"
                ]
            )


        print(
            "\nUSER QUESTION QA: FAILED"
        )


        raise SystemExit(
            1
        )


    print(
        "\nUSER QUESTION QA: PASSED"
    )


if __name__ == "__main__":
    main()