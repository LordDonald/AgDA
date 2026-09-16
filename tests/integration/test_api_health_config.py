import os

from unittest.mock import (
    patch,
)

from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)

from apps.api.app.core.runtime import (
    runtime,
)

from apps.api.app.core.settings import (
    AppSettings,
)


def main():

    print(
        "\n========================================"
    )

    print(
        "AgDA HEALTH + CONFIGURATION"
    )

    print(
        "========================================"
    )


    # ========================================================
    # 1. Environment configuration parsing
    # ========================================================

    with patch.dict(
        os.environ,
        {
            "AGDA_ENV":
                "staging",

            "AGDA_LOG_LEVEL":
                "ERROR",

            "AGDA_MAX_CONVERSATIONS":
                "125",

            "AGDA_DOCS_ENABLED":
                "false",
        },
        clear=False,
    ):

        test_settings = (
            AppSettings.from_env()
        )


    assert (
        test_settings.environment
        == "staging"
    )

    assert (
        test_settings.log_level
        == "ERROR"
    )

    assert (
        test_settings.max_conversations
        == 125
    )

    assert (
        test_settings.docs_enabled
        is False
    )


    print(
        "Environment configuration:",
        "PASSED"
    )


    # ========================================================
    # 2. Invalid environment rejected
    # ========================================================

    invalid_environment_rejected = (
        False
    )


    with patch.dict(
        os.environ,
        {
            "AGDA_ENV":
                "invalid-environment"
        },
        clear=False,
    ):

        try:

            AppSettings.from_env()

        except ValueError:

            invalid_environment_rejected = (
                True
            )


    assert (
        invalid_environment_rejected
        is True
    )


    # ========================================================
    # HTTP checks
    # ========================================================

    with TestClient(
        app
    ) as client:

        # ====================================================
        # 3. Liveness
        # ====================================================

        live = client.get(
            "/v1/live"
        )


        assert (
            live.status_code
            == 200
        )


        live_payload = (
            live.json()
        )


        print(
            "\nLIVENESS:"
        )

        print(
            live_payload
        )


        assert (
            live_payload[
                "status"
            ]
            == "alive"
        )


        # ====================================================
        # 4. Readiness
        # ====================================================

        ready = client.get(
            "/v1/ready"
        )


        assert (
            ready.status_code
            == 200
        )


        ready_payload = (
            ready.json()
        )


        print(
            "\nREADINESS:"
        )

        print(
            ready_payload
        )


        assert (
            ready_payload[
                "ready"
            ]
            is True
        )

        assert (
            ready_payload[
                "release_state"
            ]
            == "stable"
        )

        assert (
            ready_payload[
                "data_version"
            ]
            == "wave5_v1"
        )

        assert (
            ready_payload[
                "registered_metrics"
            ]
            == 18
        )


        # ====================================================
        # 5. Health remains backward compatible
        # ====================================================

        health = client.get(
            "/v1/health"
        )


        assert (
            health.status_code
            == 200
        )


        assert (
            health.json()[
                "ready"
            ]
            is True
        )


        # ====================================================
        # 6. Not-ready behavior
        # ====================================================

        previous_ready = (
            runtime.ready
        )


        runtime.ready = False


        try:

            not_ready = client.get(
                "/v1/ready"
            )


            assert (
                not_ready.status_code
                == 503
            )


            # Process itself is still alive.
            still_live = client.get(
                "/v1/live"
            )


            assert (
                still_live.status_code
                == 200
            )


            assert (
                still_live.json()[
                    "status"
                ]
                == "alive"
            )


        finally:

            runtime.ready = (
                previous_ready
            )


    print(
        "\nHEALTH + CONFIGURATION TEST: PASSED"
    )


if __name__ == "__main__":
    main()