from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)


def main():

    print(
        "\n========================================"
    )

    print(
        "AgDA EXTENSION / YIELD COMPARISON"
    )

    print(
        "========================================"
    )


    with TestClient(
        app
    ) as client:

        conversation_id = (
            "extension_yield_comparison"
        )


        # ====================================================
        # 1. Natural comparison question
        # ====================================================

        first = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "Are farmers who receive "
                        "extension advice getting "
                        "better yields?"
                    ),

                "conversation_id":
                    conversation_id,

                "max_rank_items":
                    5,
            },
        )


        assert (
            first.status_code
            == 200
        )


        payload = (
            first.json()
        )


        print(
            "\nFIRST RESPONSE:"
        )

        print(
            payload
        )


        assert (
            payload[
                "status"
            ]
            == "answered"
        )


        spec = (
            payload[
                "question_specification"
            ]
        )


        assert (
            spec[
                "metric_id"
            ]
            == "median_completed_yield"
        )

        assert (
            spec[
                "operation"
            ]
            == "group"
        )

        assert (
            spec[
                "group_by"
            ]
            == "planting_extension"
        )


        rows = (
            payload[
                "result"
            ]
        )


        assert (
            len(rows)
            == 2
        )


        by_group = {
            row[
                "planting_extension"
            ]:
                row
            for row in rows
        }


        received = (
            by_group[
                "Received planting extension"
            ]
        )

        not_received = (
            by_group[
                "No planting extension"
            ]
        )


        assert (
            abs(
                received[
                    "value"
                ]
                - 1790.547598
            )
            < 0.01
        )

        assert (
            received[
                "records"
            ]
            == 1102
        )

        assert (
            received[
                "households"
            ]
            == 424
        )


        assert (
            abs(
                not_received[
                    "value"
                ]
                - 1588.455542
            )
            < 0.01
        )

        assert (
            not_received[
                "records"
            ]
            == 5792
        )

        assert (
            not_received[
                "households"
            ]
            == 2277
        )


        assert (
            "unadjusted descriptive comparison"
            in payload[
                "answer_text"
            ].lower()
        )

        assert (
            "causal effect"
            in payload[
                "answer_text"
            ].lower()
        )


        # ====================================================
        # 2. Explicit safe follow-up
        # ====================================================

        second = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "Can you compare them "
                        "without saying extension "
                        "caused the difference?"
                    ),

                "conversation_id":
                    conversation_id,

                "max_rank_items":
                    5,
            },
        )


        assert (
            second.status_code
            == 200
        )


        second_payload = (
            second.json()
        )


        print(
            "\nFOLLOW-UP RESPONSE:"
        )

        print(
            second_payload[
                "question_specification"
            ]
        )


        assert (
            second_payload[
                "status"
            ]
            == "answered"
        )


        second_spec = (
            second_payload[
                "question_specification"
            ]
        )


        assert (
            second_spec[
                "metric_id"
            ]
            == "median_completed_yield"
        )

        assert (
            second_spec[
                "operation"
            ]
            == "group"
        )

        assert (
            second_spec[
                "group_by"
            ]
            == "planting_extension"
        )


    print(
        "\nEXTENSION / YIELD COMPARISON TEST: PASSED"
    )


if __name__ == "__main__":
    main()