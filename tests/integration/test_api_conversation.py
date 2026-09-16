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
        "AgDA API CONVERSATION MEMORY"
    )

    print(
        "========================================"
    )


    with TestClient(
        app
    ) as client:

        # ====================================================
        # 1. Geography continuation
        # ====================================================

        conversation_id = (
            "conv_test_geography"
        )


        base = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Which states have the highest "
                        "grower share for RICE?"
                    ),

                "conversation_id":
                    conversation_id,
            },
        )


        assert (
            base.status_code
            == 200
        )


        assert (
            base.json()[
                "conversation_id"
            ]
            == conversation_id
        )


        follow_up = client.post(
            "/v1/questions",
            json={
                "question":
                    "What about Kaduna?",

                "conversation_id":
                    conversation_id,
            },
        )


        assert (
            follow_up.status_code
            == 200
        )


        payload = (
            follow_up.json()
        )


        print(
            "\nFOLLOW-UP: What about Kaduna?"
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


        specification = (
            payload[
                "question_specification"
            ]
        )


        assert (
            specification[
                "metric_id"
            ]
            == "crop_grower_share"
        )


        assert (
            specification[
                "operation"
            ]
            == "value"
        )


        assert (
            specification[
                "group_by"
            ]
            is None
        )


        assert (
            specification[
                "filters"
            ]
            == {
                "crop":
                    "RICE",

                "state":
                    "Kaduna",
            }
        )


        assert (
            0.31
            <
            payload[
                "result"
            ][
                "value"
            ]
            <
            0.32
        )


        # ====================================================
        # 2. Metric switch while retaining comparison
        # ====================================================

        metric_conversation = (
            "conv_test_metric_switch"
        )


        client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Which states have the highest "
                        "grower share for RICE?"
                    ),

                "conversation_id":
                    metric_conversation,
            },
        )


        switched = client.post(
            "/v1/questions",
            json={
                "question":
                    "Show commercialization instead",

                "conversation_id":
                    metric_conversation,
            },
        )


        switched_payload = (
            switched.json()
        )


        print(
            "\nFOLLOW-UP: Show commercialization instead"
        )

        print(
            switched_payload[
                "question_specification"
            ]
        )


        assert (
            switched_payload[
                "status"
            ]
            == "answered"
        )


        switched_spec = (
            switched_payload[
                "question_specification"
            ]
        )


        assert (
            switched_spec[
                "metric_id"
            ]
            == "median_commercialization_share"
        )


        assert (
            switched_spec[
                "operation"
            ]
            == "rank"
        )


        assert (
            switched_spec[
                "group_by"
            ]
            == "state"
        )


        assert (
            switched_spec[
                "filters"
            ]
            == {
                "crop":
                    "RICE"
            }
        )


        # ====================================================
        # 3. Crop replacement
        # ====================================================

        crop_conversation = (
            "conv_test_crop_switch"
        )


        client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Which states have the highest "
                        "grower share for RICE?"
                    ),

                "conversation_id":
                    crop_conversation,
            },
        )


        maize = client.post(
            "/v1/questions",
            json={
                "question":
                    "What about maize?",

                "conversation_id":
                    crop_conversation,
            },
        ).json()


        maize_spec = (
            maize[
                "question_specification"
            ]
        )


        assert (
            maize_spec[
                "filters"
            ]
            == {
                "crop":
                    "MAIZE"
            }
        )


        assert (
            maize_spec[
                "group_by"
            ]
            == "state"
        )


        # ====================================================
        # 4. Standalone question overrides context
        # ====================================================

        standalone = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "How risky is flooding "
                        "in the North West?"
                    ),

                "conversation_id":
                    crop_conversation,
            },
        ).json()


        assert (
            standalone[
                "question_specification"
            ][
                "metric_id"
            ]
            == "climate_likely_share"
        )


        assert (
            standalone[
                "question_specification"
            ][
                "filters"
            ]
            == {
                "zone":
                    "North West",

                "climate_event":
                    "Flood",
            }
        )


        # ====================================================
        # 5. Server generates conversation ID when absent
        # ====================================================

        generated = client.post(
            "/v1/questions",
            json={
                "question":
                    "How much maize do farmers sell?"
            },
        ).json()


        assert (
            generated[
                "conversation_id"
            ]
            is not None
        )


        assert (
            generated[
                "conversation_id"
            ].startswith(
                "conv_"
            )
        )


        print(
            "\nGenerated conversation ID:",
            generated[
                "conversation_id"
            ]
        )


    print(
        "\nAPI CONVERSATION MEMORY TEST: PASSED"
    )


if __name__ == "__main__":
    main()