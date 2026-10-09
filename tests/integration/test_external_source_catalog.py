from datetime import (
    datetime,
    timezone,
)

from packages.data_sources import (
    SourceDefinition,
    SourceRegistry,
    SourceSnapshot,
    SourceType,
    build_source_health_summary,
    build_source_manifest,
)


def main():

    registry = (
        SourceRegistry()
    )


    empty_health = (
        build_source_health_summary(
            registry
        )
    )

    assert (
        empty_health["status"]
        == "not_configured"
    )

    assert (
        empty_health[
            "affects_core_readiness"
        ]
        is False
    )

    assert (
        empty_health[
            "registered_sources"
        ]
        == 0
    )


    market = (
        SourceDefinition(
            source_id=
                "market_prices",

            display_name=
                "Market Prices",

            source_type=
                SourceType.MARKET_PRICE,

            provider=
                "Test Market Provider",

            geographic_scope=
                "Nigeria",

            methodology_note=
                (
                    "Synthetic market source "
                    "used for catalog testing."
                ),

            attribution=
                "Test Market Provider",

            stale_after_hours=
                24,

            expected_refresh_hours=
                12,

            license_name=
                "Test License",

            source_url=
                "https://example.invalid/market",
        )
    )


    weather = (
        SourceDefinition(
            source_id=
                "weather_forecast",

            display_name=
                "Weather Forecast",

            source_type=
                SourceType.WEATHER_FORECAST,

            provider=
                "Test Weather Provider",

            geographic_scope=
                "Nigeria",

            methodology_note=
                (
                    "Synthetic forecast source "
                    "used for catalog testing."
                ),

            attribution=
                "Test Weather Provider",

            stale_after_hours=
                6,

            expected_refresh_hours=
                3,
        )
    )


    registry.register(
        market
    )

    registry.register(
        weather
    )


    registry.record_snapshot(
        SourceSnapshot(
            source_id=
                "market_prices",

            dataset_version=
                "2026-10-09",

            observed_from=
                datetime(
                    2026,
                    10,
                    9,
                    0,
                    0,
                    tzinfo=timezone.utc,
                ),

            observed_to=
                datetime(
                    2026,
                    10,
                    9,
                    12,
                    0,
                    tzinfo=timezone.utc,
                ),

            refreshed_at=
                datetime(
                    2026,
                    10,
                    9,
                    12,
                    0,
                    tzinfo=timezone.utc,
                ),

            retrieved_at=
                datetime(
                    2026,
                    10,
                    9,
                    12,
                    5,
                    tzinfo=timezone.utc,
                ),

            record_count=
                250,
        )
    )


    now = datetime(
        2026,
        10,
        9,
        20,
        0,
        tzinfo=timezone.utc,
    )


    manifest = (
        build_source_manifest(
            registry,
            now=now,
        )
    )

    assert len(
        manifest
    ) == 2


    market_manifest = (
        manifest[0]
    )

    weather_manifest = (
        manifest[1]
    )


    assert (
        market_manifest[
            "source_id"
        ]
        == "market_prices"
    )

    assert (
        market_manifest[
            "source_type"
        ]
        == "market_price"
    )

    assert (
        market_manifest[
            "freshness"
        ]
        == "fresh"
    )

    assert (
        market_manifest[
            "dataset_version"
        ]
        == "2026-10-09"
    )

    assert (
        market_manifest[
            "record_count"
        ]
        == 250
    )

    assert (
        market_manifest[
            "refreshed_at"
        ]
        is not None
    )


    assert (
        weather_manifest[
            "source_id"
        ]
        == "weather_forecast"
    )

    assert (
        weather_manifest[
            "freshness"
        ]
        == "unknown"
    )

    assert (
        weather_manifest[
            "dataset_version"
        ]
        is None
    )


    health = (
        build_source_health_summary(
            registry,
            now=now,
        )
    )

    assert (
        health["status"]
        == "available"
    )

    assert (
        health[
            "affects_core_readiness"
        ]
        is False
    )

    assert (
        health[
            "registered_sources"
        ]
        == 2
    )

    assert (
        health[
            "sources_with_snapshots"
        ]
        == 1
    )

    assert (
        health[
            "fresh_sources"
        ]
        == 1
    )

    assert (
        health[
            "stale_sources"
        ]
        == 0
    )

    assert (
        health[
            "unknown_sources"
        ]
        == 1
    )


    stale_health = (
        build_source_health_summary(
            registry,
            now=datetime(
                2026,
                10,
                11,
                0,
                1,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert (
        stale_health["status"]
        == "degraded"
    )

    assert (
        stale_health[
            "affects_core_readiness"
        ]
        is False
    )

    assert (
        stale_health[
            "stale_sources"
        ]
        == 1
    )


    forbidden_keys = {
        "password",
        "secret",
        "token",
        "api_key",
        "connection_string",
    }


    for entry in manifest:

        assert (
            forbidden_keys
            .isdisjoint(
                entry.keys()
            )
        )


    print(
        "External source manifest: PASSED"
    )

    print(
        "External source provenance: PASSED"
    )

    print(
        "External source health summary: PASSED"
    )

    print(
        "External source readiness isolation: PASSED"
    )

    print(
        "EXTERNAL SOURCE CATALOG TEST: PASSED"
    )


if __name__ == "__main__":

    main()
