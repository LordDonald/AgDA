from datetime import (
    datetime,
    timezone,
)

from packages.data_sources import (
    FreshnessStatus,
    SourceDefinition,
    SourceSnapshot,
    SourceType,
    evaluate_freshness,
)


def main():

    definition = (
        SourceDefinition(
            source_id=
                "test_market_prices",

            display_name=
                "Test Market Prices",

            source_type=
                SourceType.MARKET_PRICE,

            provider=
                "Test Provider",

            geographic_scope=
                "Nigeria",

            methodology_note=
                (
                    "Synthetic source used only "
                    "for contract validation."
                ),

            attribution=
                "Test Provider",

            stale_after_hours=
                24,

            expected_refresh_hours=
                12,
        )
    )


    snapshot = (
        SourceSnapshot(
            source_id=
                "test_market_prices",

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
                100,
        )
    )


    assert (
        evaluate_freshness(
            definition,
            snapshot,
            now=datetime(
                2026,
                10,
                9,
                20,
                0,
                tzinfo=timezone.utc,
            ),
        )
        == FreshnessStatus.FRESH
    )


    assert (
        evaluate_freshness(
            definition,
            snapshot,
            now=datetime(
                2026,
                10,
                11,
                0,
                1,
                tzinfo=timezone.utc,
            ),
        )
        == FreshnessStatus.STALE
    )


    unknown_definition = (
        SourceDefinition(
            source_id=
                "unknown_schedule",

            display_name=
                "Unknown Schedule",

            source_type=
                SourceType.OTHER_EXTERNAL,

            provider=
                "Test Provider",

            geographic_scope=
                "Nigeria",

            methodology_note=
                "Synthetic validation source.",

            attribution=
                "Test Provider",

            stale_after_hours=
                None,
        )
    )


    unknown_snapshot = (
        SourceSnapshot(
            source_id=
                "unknown_schedule",

            dataset_version=
                "v1",

            observed_from=
                datetime(
                    2026,
                    10,
                    1,
                    tzinfo=timezone.utc,
                ),

            observed_to=
                datetime(
                    2026,
                    10,
                    1,
                    tzinfo=timezone.utc,
                ),

            refreshed_at=
                datetime(
                    2026,
                    10,
                    1,
                    tzinfo=timezone.utc,
                ),

            retrieved_at=
                datetime(
                    2026,
                    10,
                    1,
                    tzinfo=timezone.utc,
                ),

            record_count=
                0,
        )
    )


    assert (
        evaluate_freshness(
            unknown_definition,
            unknown_snapshot,
        )
        == FreshnessStatus.UNKNOWN
    )


    mismatch_detected = False

    try:

        evaluate_freshness(
            definition,
            unknown_snapshot,
        )

    except ValueError:

        mismatch_detected = True


    assert mismatch_detected


    invalid_time_detected = False

    try:

        SourceSnapshot(
            source_id=
                "bad_source",

            dataset_version=
                "v1",

            observed_from=
                datetime(
                    2026,
                    10,
                    10,
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

    except ValueError:

        invalid_time_detected = True


    assert invalid_time_detected


    print(
        "External source definition: PASSED"
    )

    print(
        "External source snapshot: PASSED"
    )

    print(
        "External source freshness: PASSED"
    )

    print(
        "EXTERNAL SOURCE CONTRACT TEST: PASSED"
    )


if __name__ == "__main__":

    main()
