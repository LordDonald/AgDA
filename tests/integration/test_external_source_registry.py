from datetime import (
    datetime,
    timezone,
)

from packages.data_sources import (
    FreshnessStatus,
    SourceDefinition,
    SourceRegistry,
    SourceSnapshot,
    SourceType,
)


def main():

    registry = (
        SourceRegistry()
    )


    market_definition = (
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
                    "for registry testing."
                ),

            attribution=
                "Test Market Provider",

            stale_after_hours=
                24,

            expected_refresh_hours=
                12,
        )
    )


    weather_definition = (
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
                    "Synthetic weather source "
                    "for registry testing."
                ),

            attribution=
                "Test Weather Provider",

            stale_after_hours=
                6,

            expected_refresh_hours=
                3,
        )
    )


    assert not registry.contains(
        "market_prices"
    )


    registry.register(
        market_definition
    )

    registry.register(
        weather_definition
    )


    assert registry.contains(
        "market_prices"
    )

    assert registry.contains(
        "weather_forecast"
    )


    assert (
        registry.get_definition(
            "market_prices"
        )
        == market_definition
    )


    definitions = (
        registry.list_definitions()
    )

    assert [
        definition.source_id
        for definition in definitions
    ] == [
        "market_prices",
        "weather_forecast",
    ]


    duplicate_detected = False

    try:

        registry.register(
            market_definition
        )

    except ValueError:

        duplicate_detected = True


    assert duplicate_detected


    empty_state = (
        registry.get_state(
            "weather_forecast"
        )
    )

    assert (
        empty_state.snapshot
        is None
    )

    assert (
        empty_state.freshness
        == FreshnessStatus.UNKNOWN
    )


    market_snapshot = (
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


    registry.record_snapshot(
        market_snapshot
    )


    assert (
        registry.get_snapshot(
            "market_prices"
        )
        == market_snapshot
    )


    fresh_state = (
        registry.get_state(
            "market_prices",
            now=datetime(
                2026,
                10,
                9,
                20,
                0,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert (
        fresh_state.freshness
        == FreshnessStatus.FRESH
    )


    stale_state = (
        registry.get_state(
            "market_prices",
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
        stale_state.freshness
        == FreshnessStatus.STALE
    )


    unknown_lookup_detected = False

    try:

        registry.get_definition(
            "missing_source"
        )

    except KeyError:

        unknown_lookup_detected = True


    assert unknown_lookup_detected


    unknown_snapshot_detected = False

    try:

        registry.record_snapshot(
            SourceSnapshot(
                source_id=
                    "missing_source",

                dataset_version=
                    "v1",

                observed_from=
                    datetime(
                        2026,
                        10,
                        9,
                        tzinfo=timezone.utc,
                    ),

                observed_to=
                    datetime(
                        2026,
                        10,
                        9,
                        tzinfo=timezone.utc,
                    ),

                refreshed_at=
                    datetime(
                        2026,
                        10,
                        9,
                        tzinfo=timezone.utc,
                    ),

                retrieved_at=
                    datetime(
                        2026,
                        10,
                        9,
                        tzinfo=timezone.utc,
                    ),

                record_count=
                    1,
            )
        )

    except KeyError:

        unknown_snapshot_detected = True


    assert unknown_snapshot_detected


    states = (
        registry.list_states(
            now=datetime(
                2026,
                10,
                9,
                20,
                0,
                tzinfo=timezone.utc,
            )
        )
    )

    assert len(states) == 2

    assert (
        states[0]
        .definition
        .source_id
        == "market_prices"
    )

    assert (
        states[1]
        .definition
        .source_id
        == "weather_forecast"
    )


    print(
        "External source registration: PASSED"
    )

    print(
        "External source duplicate protection: PASSED"
    )

    print(
        "External source snapshot tracking: PASSED"
    )

    print(
        "External source registry freshness: PASSED"
    )

    print(
        "External source unknown handling: PASSED"
    )

    print(
        "EXTERNAL SOURCE REGISTRY TEST: PASSED"
    )


if __name__ == "__main__":

    main()
