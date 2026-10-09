from datetime import (
    datetime,
    timezone,
)

from fastapi.testclient import (
    TestClient,
)

from apps.api.app.core.runtime import (
    runtime,
)

from apps.api.app.main import (
    app,
)

from packages.data_sources import (
    SourceDefinition,
    SourceSnapshot,
    SourceType,
)


def main():

    with TestClient(
        app
    ) as client:

        # ====================================================
        # 1. Existing health remains authoritative
        # ====================================================

        health = client.get(
            "/v1/health"
        )

        assert (
            health.status_code
            == 200
        )

        health_payload = (
            health.json()
        )


        assert (
            health_payload["ready"]
            is True
        )

        assert (
            health_payload[
                "data_version"
            ]
            == "wave5_v1"
        )

        assert (
            health_payload[
                "release_state"
            ]
            == "stable"
        )


        external_health = (
            health_payload[
                "external_sources"
            ]
        )


        assert (
            external_health[
                "status"
            ]
            == "not_configured"
        )

        assert (
            external_health[
                "affects_core_readiness"
            ]
            is False
        )

        assert (
            external_health[
                "registered_sources"
            ]
            == 0
        )


        # ====================================================
        # 2. Empty source catalog
        # ====================================================

        sources_response = (
            client.get(
                "/v1/sources"
            )
        )

        assert (
            sources_response.status_code
            == 200
        )

        sources_payload = (
            sources_response.json()
        )


        assert (
            sources_payload[
                "sources"
            ]
            == []
        )

        assert (
            sources_payload[
                "external_sources"
            ][
                "status"
            ]
            == "not_configured"
        )


        # ====================================================
        # 3. Register a synthetic provider
        # ====================================================

        runtime.source_registry.register(
            SourceDefinition(
                source_id=
                    "stale_weather_test",

                display_name=
                    "Stale Weather Test",

                source_type=
                    SourceType
                    .WEATHER_FORECAST,

                provider=
                    "Synthetic Provider",

                geographic_scope=
                    "Nigeria",

                methodology_note=
                    (
                        "Synthetic source used "
                        "for readiness-isolation testing."
                    ),

                attribution=
                    "Synthetic Provider",

                stale_after_hours=
                    6,

                expected_refresh_hours=
                    3,

                source_url=
                    "https://example.invalid/weather",
            )
        )


        runtime.source_registry.record_snapshot(
            SourceSnapshot(
                source_id=
                    "stale_weather_test",

                dataset_version=
                    "test-v1",

                observed_from=
                    datetime(
                        2026,
                        1,
                        1,
                        tzinfo=timezone.utc,
                    ),

                observed_to=
                    datetime(
                        2026,
                        1,
                        1,
                        6,
                        tzinfo=timezone.utc,
                    ),

                refreshed_at=
                    datetime(
                        2026,
                        1,
                        1,
                        6,
                        tzinfo=timezone.utc,
                    ),

                retrieved_at=
                    datetime(
                        2026,
                        1,
                        1,
                        6,
                        1,
                        tzinfo=timezone.utc,
                    ),

                record_count=
                    25,
            )
        )


        # ====================================================
        # 4. Stale source must NOT break core readiness
        # ====================================================

        degraded_health = (
            client.get(
                "/v1/health"
            )
        )

        assert (
            degraded_health.status_code
            == 200
        )

        degraded_payload = (
            degraded_health.json()
        )


        assert (
            degraded_payload[
                "ready"
            ]
            is True
        )

        assert (
            degraded_payload[
                "status"
            ]
            == "ready"
        )


        external_health = (
            degraded_payload[
                "external_sources"
            ]
        )


        assert (
            external_health[
                "status"
            ]
            == "degraded"
        )

        assert (
            external_health[
                "affects_core_readiness"
            ]
            is False
        )

        assert (
            external_health[
                "registered_sources"
            ]
            == 1
        )

        assert (
            external_health[
                "stale_sources"
            ]
            == 1
        )


        # ====================================================
        # 5. Provenance endpoint
        # ====================================================

        sources_response = (
            client.get(
                "/v1/sources"
            )
        )

        assert (
            sources_response.status_code
            == 200
        )


        sources_payload = (
            sources_response.json()
        )

        assert (
            len(
                sources_payload[
                    "sources"
                ]
            )
            == 1
        )


        source = (
            sources_payload[
                "sources"
            ][0]
        )


        assert (
            source[
                "source_id"
            ]
            == "stale_weather_test"
        )

        assert (
            source[
                "source_type"
            ]
            == "weather_forecast"
        )

        assert (
            source[
                "freshness"
            ]
            == "stale"
        )

        assert (
            source[
                "record_count"
            ]
            == 25
        )


        forbidden_keys = {
            "password",
            "secret",
            "token",
            "api_key",
            "connection_string",
        }


        assert (
            forbidden_keys
            .isdisjoint(
                source.keys()
            )
        )


    print(
        "External source API catalog: PASSED"
    )

    print(
        "External source health reporting: PASSED"
    )

    print(
        "External source readiness isolation: PASSED"
    )

    print(
        "External source privacy boundary: PASSED"
    )

    print(
        "EXTERNAL SOURCE API TEST: PASSED"
    )


if __name__ == "__main__":

    main()
