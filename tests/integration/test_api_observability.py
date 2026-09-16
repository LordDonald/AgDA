from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)

from apps.api.app.core.runtime import (
    runtime,
)


def main():

    print(
        "\n========================================"
    )

    print(
        "AgDA API OBSERVABILITY"
    )

    print(
        "========================================"
    )


    with TestClient(
        app,
        raise_server_exceptions=False,
    ) as client:

        # ====================================================
        # 1. Automatically generated request ID
        # ====================================================

        health = client.get(
            "/v1/health"
        )


        assert (
            health.status_code
            == 200
        )


        generated_request_id = (
            health.headers.get(
                "X-Request-ID"
            )
        )


        print(
            "\nGenerated request ID:",
            generated_request_id
        )


        assert (
            generated_request_id
            is not None
        )


        assert (
            generated_request_id.startswith(
                "req_"
            )
        )


        # ====================================================
        # 2. Client request ID preserved
        # ====================================================

        supplied_id = (
            "req_external_test_001"
        )


        response = client.get(
            "/v1/health",

            headers={
                "X-Request-ID":
                    supplied_id
            },
        )


        assert (
            response.status_code
            == 200
        )


        assert (
            response.headers[
                "X-Request-ID"
            ]
            == supplied_id
        )


        print(
            "Supplied request ID preserved:",
            True
        )


        # ====================================================
        # 3. Question endpoint receives request ID
        # ====================================================

        question = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "How risky is flooding "
                        "in the North West?"
                    )
            },
        )


        assert (
            question.status_code
            == 200
        )


        assert (
            question.headers.get(
                "X-Request-ID"
            )
            is not None
        )


        # ====================================================
        # 4. Validation failures still receive request IDs
        # ====================================================

        invalid = client.post(
            "/v1/questions",

            json={
                "question":
                    ""
            },
        )


        assert (
            invalid.status_code
            == 422
        )


        assert (
            invalid.headers.get(
                "X-Request-ID"
            )
            is not None
        )


        # ====================================================
        # 5. Unexpected server errors fail safely
        # ====================================================

        original_method = (
            runtime
            .answer_service
            .answer_with_pipeline_result
        )


        def force_failure(
            *args,
            **kwargs,
        ):

            raise RuntimeError(
                "internal diagnostic failure"
            )


        runtime.answer_service.answer_with_pipeline_result = (
            force_failure
        )


        try:

            failed = client.post(
                "/v1/questions",

                json={
                    "question":
                        (
                            "How much maize "
                            "do farmers sell?"
                        )
                },
            )


            print(
                "\nSafe failure response:"
            )

            print(
                failed.json()
            )


            assert (
                failed.status_code
                == 500
            )


            payload = (
                failed.json()
            )


            assert (
                payload[
                    "status"
                ]
                == "system_error"
            )


            assert (
                payload[
                    "request_id"
                ]
                is not None
            )


            assert (
                failed.headers[
                    "X-Request-ID"
                ]
                == payload[
                    "request_id"
                ]
            )


            serialized = str(
                payload
            ).lower()


            assert (
                "traceback"
                not in serialized
            )


            assert (
                "internal diagnostic failure"
                not in serialized
            )


        finally:

            runtime.answer_service.answer_with_pipeline_result = (
                original_method
            )


    print(
        "\nAPI OBSERVABILITY TEST: PASSED"
    )


if __name__ == "__main__":
    main()