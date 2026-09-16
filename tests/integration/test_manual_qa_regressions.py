from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)


def ask(
    client,
    conversation_id,
    question,
):

    response = client.post(
        "/v1/questions",
        json={
            "question":
                question,

            "conversation_id":
                conversation_id,
        },
    )

    assert (
        response.status_code
        == 200
    )

    return response.json()


def main():

    print(
        "\n========================================"
    )

    print(
        "AgDA MANUAL QA REGRESSIONS"
    )

    print(
        "========================================"
    )


    with TestClient(
        app
    ) as client:

        # ====================================================
        # 1. FARMER JOURNEY
        # ====================================================

        conversation = "qa_reg_farmer"


        first = ask(
            client,
            conversation,
            (
                "What are farmers mostly "
                "growing in Kaduna?"
            ),
        )


        spec = first[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            == "crop_grower_share"
        )

        assert (
            spec["operation"]
            == "rank"
        )

        assert (
            spec["group_by"]
            == "crop"
        )

        assert (
            spec["filters"]["state"]
            == "Kaduna"
        )


        rice = ask(
            client,
            conversation,
            "What about rice?",
        )


        spec = rice[
            "question_specification"
        ]

        assert (
            spec["operation"]
            == "value"
        )

        assert (
            spec["filters"]
            == {
                "state":
                    "Kaduna",

                "crop":
                    "RICE",
            }
        )


        sold = ask(
            client,
            conversation,
            (
                "How much of it do "
                "farmers usually sell?"
            ),
        )


        spec = sold[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            ==
            "median_commercialization_share"
        )

        assert (
            spec["filters"]
            == {
                "state":
                    "Kaduna",

                "crop":
                    "RICE",
            }
        )


        recommendation = ask(
            client,
            conversation,
            (
                "Would rice be a good crop "
                "for me to plant there?"
            ),
        )


        assert (
            recommendation["status"]
            == "reframe_required"
        )


        print(
            "Farmer journey: PASSED"
        )


        # ====================================================
        # 2. GOVERNMENT JOURNEY
        # ====================================================

        conversation = "qa_reg_government"


        grown = ask(
            client,
            conversation,
            "Where is rice grown most commonly?",
        )


        spec = grown[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            == "crop_grower_share"
        )

        assert (
            spec["operation"]
            == "rank"
        )

        assert (
            spec["group_by"]
            == "state"
        )

        assert (
            spec["filters"]
            == {
                "crop":
                    "RICE"
            }
        )


        yields = ask(
            client,
            conversation,
            (
                "Which of those states gets "
                "the best rice yields?"
            ),
        )


        spec = yields[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            == "median_completed_yield"
        )

        assert (
            spec["operation"]
            == "rank"
        )

        assert (
            spec["group_by"]
            == "state"
        )


        seller = ask(
            client,
            conversation,
            "Show seller participation instead.",
        )


        spec = seller[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            == "crop_seller_rate"
        )

        assert (
            spec["operation"]
            == "rank"
        )

        assert (
            spec["group_by"]
            == "state"
        )


        kaduna = ask(
            client,
            conversation,
            "What about Kaduna?",
        )


        spec = kaduna[
            "question_specification"
        ]

        assert (
            spec["operation"]
            == "value"
        )

        assert (
            spec["filters"]["state"]
            == "Kaduna"
        )

        assert (
            spec["filters"]["crop"]
            == "RICE"
        )


        print(
            "Government journey: PASSED"
        )


        # ====================================================
        # 3. RESEARCHER JOURNEY
        # ====================================================

        conversation = "qa_reg_researcher"


        extension = ask(
            client,
            conversation,
            (
                "Are farmers who receive "
                "extension advice getting "
                "better yields?"
            ),
        )


        spec = extension[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            == "median_completed_yield"
        )

        assert (
            spec["operation"]
            == "group"
        )

        assert (
            spec["group_by"]
            == "planting_extension"
        )

        assert (
            len(extension["result"])
            == 2
        )


        safe_compare = ask(
            client,
            conversation,
            (
                "Can you compare them without "
                "saying extension caused "
                "the difference?"
            ),
        )


        spec = safe_compare[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            == "median_completed_yield"
        )

        assert (
            spec["group_by"]
            == "planting_extension"
        )

        assert (
            "unadjusted descriptive comparison"
            in safe_compare[
                "answer_text"
            ].lower()
        )


        food_security = ask(
            client,
            conversation,
            (
                "Did food security improve "
                "after harvest?"
            ),
        )


        assert (
            food_security[
                "question_specification"
            ][
                "metric_id"
            ]
            == "food_insecurity_change"
        )

        assert (
            "does not by itself"
            in food_security[
                "answer_text"
            ].lower()
            or
            "does not"
            in food_security[
                "answer_text"
            ].lower()
        )


        print(
            "Researcher journey: PASSED"
        )


        # ====================================================
        # 4. INVESTOR JOURNEY
        # ====================================================

        conversation = "qa_reg_investor"


        selling_share = ask(
            client,
            conversation,
            (
                "Where are rice farmers selling "
                "the largest share of their harvest?"
            ),
        )


        spec = selling_share[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            ==
            "median_commercialization_share"
        )

        assert (
            spec["operation"]
            == "rank"
        )

        assert (
            spec["group_by"]
            == "state"
        )


        kwara = ask(
            client,
            conversation,
            "What about Kwara?",
        )


        spec = kwara[
            "question_specification"
        ]

        assert (
            spec["operation"]
            == "value"
        )

        assert (
            spec["filters"]["state"]
            == "Kwara"
        )

        assert (
            spec["filters"]["crop"]
            == "RICE"
        )


        profitability = ask(
            client,
            conversation,
            (
                "Does that mean rice is "
                "more profitable there?"
            ),
        )


        assert (
            profitability["status"]
            == "unsupported"
        )

        assert (
            "production-cost"
            in profitability[
                "answer_text"
            ].lower()
            or
            "profitability"
            in profitability[
                "answer_text"
            ].lower()
        )


        print(
            "Investor journey: PASSED"
        )


        # ====================================================
        # 5. CLIMATE JOURNEY
        # ====================================================

        conversation = "qa_reg_climate"


        flooding = ask(
            client,
            conversation,
            (
                "How worried are communities "
                "in the North West about flooding?"
            ),
        )


        spec = flooding[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            == "climate_likely_share"
        )

        assert (
            spec["filters"]
            == {
                "zone":
                    "North West",

                "climate_event":
                    "Flood",
            }
        )


        forecast = ask(
            client,
            conversation,
            (
                "Is that an actual "
                "weather forecast?"
            ),
        )


        assert (
            forecast["status"]
            == "answered"
        )

        assert (
            forecast[
                "question_specification"
            ]
            is None
        )

        assert (
            forecast["result"]
            is None
        )

        assert (
            "not a meteorological forecast"
            in forecast[
                "answer_text"
            ].lower()
        )


        threat = ask(
            client,
            conversation,
            (
                "Which climate threat is "
                "viewed as the biggest overall?"
            ),
        )


        spec = threat[
            "question_specification"
        ]

        assert (
            spec["metric_id"]
            == "climate_likely_share"
        )

        assert (
            spec["operation"]
            == "rank"
        )

        assert (
            spec["group_by"]
            == "climate_event"
        )


        print(
            "Climate journey: PASSED"
        )


    print(
        "\nMANUAL QA REGRESSIONS: PASSED"
    )


if __name__ == "__main__":

    main()