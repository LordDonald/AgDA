from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)

from apps.api.app.core.settings import (
    settings,
)


def main():

    print(
        "\n========================================"
    )

    print(
        "AgDA API LIMITS"
    )

    print(
        "========================================"
    )


    with TestClient(
        app
    ) as client:

        # ====================================================
        # 1. Question whitespace normalized
        # ====================================================

        normalized = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "   How much maize "
                        "do farmers sell?   "
                    )
            },
        )


        assert (
            normalized.status_code
            == 200
        )


        assert (
            normalized.json()[
                "question"
            ]
            ==
            "How much maize do farmers sell?"
        )


        print(
            "Question normalization:",
            "PASSED"
        )


        # ====================================================
        # 2. Whitespace-only question rejected
        # ====================================================

        blank = client.post(
            "/v1/questions",

            json={
                "question":
                    "      "
            },
        )


        assert (
            blank.status_code
            == 422
        )


        # ====================================================
        # 3. Question length protected
        # ====================================================

        too_long = client.post(
            "/v1/questions",

            json={
                "question":
                    "x" * 2001
            },
        )


        assert (
            too_long.status_code
            == 422
        )


        # ====================================================
        # 4. Conversation ID length protected
        # ====================================================

        long_conversation_id = (
            client.post(
                "/v1/questions",

                json={
                    "question":
                        (
                            "How much maize "
                            "do farmers sell?"
                        ),

                    "conversation_id":
                        "c" * 129,
                },
            )
        )


        assert (
            long_conversation_id
            .status_code
            == 422
        )


        # ====================================================
        # 5. Invalid locale rejected
        # ====================================================

        invalid_locale = (
            client.post(
                "/v1/questions",

                json={
                    "question":
                        (
                            "How much maize "
                            "do farmers sell?"
                        ),

                    "locale":
                        "not a locale!",
                },
            )
        )


        assert (
            invalid_locale.status_code
            == 422
        )


        # ====================================================
        # 6. Oversized HTTP body rejected before parsing
        # ====================================================

        oversized = client.post(
            "/v1/questions",

            content=(
                b"x"
                * (
                    settings
                    .max_request_bytes
                    + 1
                )
            ),

            headers={
                "Content-Type":
                    "application/json",
            },
        )


        print(
            "\nOversized response:",
            oversized.json()
        )


        assert (
            oversized.status_code
            == 413
        )


        assert (
            oversized.json()[
                "status"
            ]
            == "request_too_large"
        )


        assert (
            oversized.headers.get(
                "X-Request-ID"
            )
            is not None
        )


        # ====================================================
        # 7. Invalid external request ID is replaced
        # ====================================================

        invalid_request_id = (
            "invalid request id with spaces"
        )


        request_id_response = (
            client.get(
                "/v1/live",

                headers={
                    "X-Request-ID":
                        invalid_request_id
                },
            )
        )


        returned_id = (
            request_id_response
            .headers[
                "X-Request-ID"
            ]
        )


        print(
            "Invalid external request ID replaced:",
            returned_id
        )


        assert (
            returned_id
            != invalid_request_id
        )


        assert (
            returned_id.startswith(
                "req_"
            )
        )


        # ====================================================
        # 8. Valid external request ID preserved
        # ====================================================

        valid_request_id = (
            "req_external_limit_test_001"
        )


        valid_id_response = (
            client.get(
                "/v1/live",

                headers={
                    "X-Request-ID":
                        valid_request_id
                },
            )
        )


        assert (
            valid_id_response.headers[
                "X-Request-ID"
            ]
            == valid_request_id
        )


        # ====================================================
        # 9. Rank size already constrained
        # ====================================================

        invalid_rank_size = (
            client.post(
                "/v1/questions",

                json={
                    "question":
                        (
                            "Which crops have the "
                            "highest yields in Nigeria?"
                        ),

                    "max_rank_items":
                        11,
                },
            )
        )


        assert (
            invalid_rank_size
            .status_code
            == 422
        )


    print(
        "\nAPI LIMITS TEST: PASSED"
    )


if __name__ == "__main__":
    main()