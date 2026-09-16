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
        "AgDA METHODOLOGICAL FOLLOW-UPS"
    )

    print(
        "========================================"
    )


    with TestClient(
        app
    ) as client:

        conversation_id = (
            "methodological_climate_test"
        )


        # ====================================================
        # 1. Analytical climate question
        # ====================================================

        first = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "How worried are communities "
                        "in the North West about "
                        "flooding?"
                    ),

                "conversation_id":
                    conversation_id,
            },
        )


        assert (
            first.status_code
            == 200
        )


        first_payload = (
            first.json()
        )


        print(
            "\nFIRST RESPONSE:"
        )

        print(
            first_payload
        )


        assert (
            first_payload[
                "status"
            ]
            == "answered"
        )


        first_spec = (
            first_payload[
                "question_specification"
            ]
        )


        assert (
            first_spec[
                "metric_id"
            ]
            == "climate_likely_share"
        )


        assert (
            first_spec[
                "filters"
            ][
                "zone"
            ]
            == "North West"
        )


        assert (
            first_spec[
                "filters"
            ][
                "climate_event"
            ]
            == "Flood"
        )


        # ====================================================
        # 2. Methodological follow-up
        # ====================================================

        second = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "Is that an actual "
                        "weather forecast?"
                    ),

                "conversation_id":
                    conversation_id,
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
            "\nMETHODOLOGICAL FOLLOW-UP:"
        )

        print(
            second_payload
        )


        assert (
            second_payload[
                "status"
            ]
            == "answered"
        )


        assert (
            second_payload[
                "result"
            ]
            is None
        )


        assert (
            second_payload[
                "question_specification"
            ]
            is None
        )


        answer_text = (
            second_payload[
                "answer_text"
            ]
            .lower()
        )


        assert (
            "not a meteorological forecast"
            in answer_text
            or
            "not an actual weather forecast"
            in answer_text
        )


        # It must not pretend to run another analysis.
        assert (
            second_payload[
                "evidence"
            ]
            is None
        )


    print(
        "\nMETHODOLOGICAL FOLLOW-UP TEST: PASSED"
    )


if __name__ == "__main__":

    main()