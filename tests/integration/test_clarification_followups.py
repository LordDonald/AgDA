from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)


def main():

    cases = [
        {
            "question":
                "Which states have the highest yields for RICE?",

            "metric_id":
                "median_completed_yield",
        },

        {
            "question":
                "Which states have the highest grower share for RICE?",

            "metric_id":
                "crop_grower_share",
        },

        {
            "question":
                "Which states have the highest seller participation for RICE?",

            "metric_id":
                "crop_seller_rate",
        },

        {
            "question":
                "Which states have the highest commercialization share for RICE?",

            "metric_id":
                "median_commercialization_share",
        },
    ]


    print(
        "\n========================================"
    )

    print(
        "AgDA CLARIFICATION FOLLOW-UPS"
    )

    print(
        "========================================"
    )


    with TestClient(
        app
    ) as client:

        for case in cases:

            response = client.post(
                "/v1/questions",

                json={
                    "question":
                        case[
                            "question"
                        ],

                    "max_rank_items":
                        5,

                    "include_visualization":
                        True,

                    "locale":
                        "en-NG",
                },
            )


            assert (
                response.status_code
                == 200
            )


            payload = (
                response.json()
            )


            print(
                "\nQUESTION:",
                case["question"]
            )

            print(
                "STATUS:",
                payload[
                    "status"
                ]
            )

            print(
                "METRIC:",
                payload[
                    "question_specification"
                ][
                    "metric_id"
                ]
            )

            print(
                "TOP RESULT:",
                (
                    payload[
                        "result"
                    ][0]
                    if payload[
                        "result"
                    ]
                    else None
                )
            )


            assert (
                payload[
                    "status"
                ]
                == "answered"
            )


            specification = (
                payload[
                    "question_specification"
                ]
            )


            assert (
                specification[
                    "metric_id"
                ]
                == case[
                    "metric_id"
                ]
            )

            assert (
                specification[
                    "operation"
                ]
                == "rank"
            )

            assert (
                specification[
                    "group_by"
                ]
                == "state"
            )

            assert (
                specification[
                    "filters"
                ]
                == {
                    "crop":
                        "RICE"
                }
            )

            assert (
                isinstance(
                    payload[
                        "result"
                    ],
                    list
                )
            )

            assert (
                len(
                    payload[
                        "result"
                    ]
                )
                > 0
            )


    print(
        "\nCLARIFICATION FOLLOW-UP TEST: PASSED"
    )


if __name__ == "__main__":
    main()