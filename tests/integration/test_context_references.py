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
        "AgDA CONTEXT REFERENCES"
    )

    print(
        "========================================"
    )


    with TestClient(
        app
    ) as client:

        # ====================================================
        # FARMER JOURNEY
        # ====================================================

        farmer_conversation = (
            "context_reference_farmer"
        )


        base = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "What are farmers mostly "
                        "growing in Kaduna?"
                    ),

                "conversation_id":
                    farmer_conversation,
            },
        )


        assert (
            base.status_code
            == 200
        )

        assert (
            base.json()[
                "status"
            ]
            == "answered"
        )


        rice = client.post(
            "/v1/questions",

            json={
                "question":
                    "What about rice?",

                "conversation_id":
                    farmer_conversation,
            },
        )


        assert (
            rice.status_code
            == 200
        )


        rice_spec = (
            rice.json()[
                "question_specification"
            ]
        )

        print(
            "\nRICE FOLLOW-UP SPEC:"
        )
        
        print(
            rice_spec
        )
        
        print(
            "\nRICE FULL RESPONSE:"
        )
        
        print(
            rice.json()
        )

        
        assert (
            rice_spec[
                "metric_id"
            ]
            == "crop_grower_share"
        )

        assert (
            rice_spec[
                "operation"
            ]
            == "value"
        )

        assert (
            rice_spec[
                "filters"
            ]
            == {
                "state":
                    "Kaduna",

                "crop":
                    "RICE",
            }
        )


        commercialization = (
            client.post(
                "/v1/questions",

                json={
                    "question":
                        (
                            "How much of it do "
                            "farmers usually sell?"
                        ),

                    "conversation_id":
                        farmer_conversation,
                },
            )
        )


        assert (
            commercialization.status_code
            == 200
        )


        commercial_payload = (
            commercialization.json()
        )


        print(
            "\nFARMER REFERENTIAL FOLLOW-UP:"
        )

        print(
            commercial_payload[
                "question_specification"
            ]
        )


        commercial_spec = (
            commercial_payload[
                "question_specification"
            ]
        )


        assert (
            commercial_payload[
                "status"
            ]
            == "answered"
        )

        assert (
            commercial_spec[
                "metric_id"
            ]
            == "median_commercialization_share"
        )

        assert (
            commercial_spec[
                "operation"
            ]
            == "value"
        )

        assert (
            commercial_spec[
                "group_by"
            ]
            is None
        )

        assert (
            commercial_spec[
                "filters"
            ]
            == {
                "state":
                    "Kaduna",

                "crop":
                    "RICE",
            }
        )


        # ====================================================
        # GOVERNMENT JOURNEY
        # ====================================================

        government_conversation = (
            "context_reference_government"
        )


        first = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "Where is rice grown "
                        "most commonly?"
                    ),

                "conversation_id":
                    government_conversation,
            },
        )


        assert (
            first.status_code
            == 200
        )


        first_spec = (
            first.json()[
                "question_specification"
            ]
        )


        assert (
            first_spec[
                "metric_id"
            ]
            == "crop_grower_share"
        )

        assert (
            first_spec[
                "operation"
            ]
            == "rank"
        )

        assert (
            first_spec[
                "group_by"
            ]
            == "state"
        )

        assert (
            first_spec[
                "filters"
            ]
            == {
                "crop":
                    "RICE"
            }
        )


        yields = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "Which of those states gets "
                        "the best rice yields?"
                    ),

                "conversation_id":
                    government_conversation,
            },
        )


        assert (
            yields.status_code
            == 200
        )


        yield_spec = (
            yields.json()[
                "question_specification"
            ]
        )


        print(
            "\nTHOSE STATES FOLLOW-UP:"
        )

        print(
            yield_spec
        )


        assert (
            yield_spec[
                "metric_id"
            ]
            == "median_completed_yield"
        )

        assert (
            yield_spec[
                "operation"
            ]
            == "rank"
        )

        assert (
            yield_spec[
                "group_by"
            ]
            == "state"
        )

        assert (
            yield_spec[
                "filters"
            ]
            == {
                "crop":
                    "RICE"
            }
        )


        seller = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "Show seller participation "
                        "instead."
                    ),

                "conversation_id":
                    government_conversation,
            },
        )


        assert (
            seller.status_code
            == 200
        )


        seller_spec = (
            seller.json()[
                "question_specification"
            ]
        )


        assert (
            seller_spec[
                "metric_id"
            ]
            == "crop_seller_rate"
        )

        assert (
            seller_spec[
                "operation"
            ]
            == "rank"
        )

        assert (
            seller_spec[
                "group_by"
            ]
            == "state"
        )

        assert (
            seller_spec[
                "filters"
            ]
            == {
                "crop":
                    "RICE"
            }
        )


    print(
        "\nCONTEXT REFERENCES TEST: PASSED"
    )


if __name__ == "__main__":
    main()