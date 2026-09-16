from packages.data_release.loader import (
    AgDAReleaseLoader
)

from packages.analytics.registry import (
    MetricRegistry
)

from packages.analytics.executor import (
    AnalyticsExecutor
)


def main():

    loader = (
        AgDAReleaseLoader()
    )

    connection = (
        loader.open()
    )

    registry = (
        MetricRegistry.from_connection(
            connection
        )
    )

    executor = (
        AnalyticsExecutor(
            connection,
            registry,
        )
    )


    print(
        "\n========================================"
    )

    print(
        "AgDA ANALYTICS EXECUTOR"
    )

    print(
        "========================================"
    )


    # ========================================================
    # 1. National completed-harvest yield
    # ========================================================

    completed_yield = executor.execute(
        metric_id=
            "median_completed_yield"
    )


    print(
        "\nCompleted-harvest yield:"
    )

    print(
        completed_yield
    )


    assert (
        abs(
            completed_yield.value
            - 1616.445947
        )
        < 0.01
    )

    assert (
        completed_yield.evidence.records
        == 6894
    )


    # ========================================================
    # 2. High-confidence yield
    # ========================================================

    high_confidence = executor.execute(
        metric_id=
            "median_high_confidence_yield"
    )


    assert (
        abs(
            high_confidence.value
            - 2209.940107
        )
        < 0.01
    )

    assert (
        high_confidence.evidence.records
        == 1686
    )


    # ========================================================
    # 3. MAIZE commercialization share
    # ========================================================

    maize_sales = executor.execute(
        metric_id=
            "median_commercialization_share",

        filters={
            "crop":
                "MAIZE"
        }
    )


    print(
        "\nMAIZE commercialization:"
    )

    print(
        maize_sales
    )


    assert (
        abs(
            maize_sales.value
            - 25.0
        )
        < 0.000001
    )

    assert (
        maize_sales.evidence.records
        == 1502
    )


    # ========================================================
    # 4. North West Flood likelihood
    # ========================================================

    flood_risk = executor.execute(
        metric_id=
            "climate_likely_share",

        filters={
            "zone":
                "North West",

            "climate_event":
                "Flood"
        }
    )


    print(
        "\nNorth West Flood likelihood:"
    )

    print(
        flood_risk
    )


    assert (
        abs(
            flood_risk.value
            - 0.125
        )
        < 0.000001
    )

    assert (
        flood_risk.evidence.records
        == 80
    )


    # ========================================================
    # 5. Food-security change
    # ========================================================

    food_security_change = (
        executor.execute(
            metric_id=
                "food_insecurity_change"
        )
    )


    print(
        "\nFood-security change:"
    )

    print(
        food_security_change
    )


    assert (
        abs(
            food_security_change.value
            - (-0.29724130404015003)
        )
        < 0.000001
    )

    assert (
        food_security_change
        .evidence.records
        == 4715
    )


    # ========================================================
    # 6. Yield ranking by crop
    # ========================================================

    crop_yield_ranking = (
        executor.execute(
            metric_id=
                "median_completed_yield",

            operation=
                "rank",

            group_by=
                "crop",

            top_n=
                10,
        )
    )


    print(
        "\nTop crop yields:"
    )

    for row in (
        crop_yield_ranking.rows
    ):

        print(row)


    assert (
        len(
            crop_yield_ranking.rows
        )
        == 10
    )

    assert (
        crop_yield_ranking.rows[
            0
        ]["crop"]
        == "YAM, THREE LEAVED"
    )

    assert (
        crop_yield_ranking.rows[
            0
        ]["records"]
        == 39
    )


    # ========================================================
    # 7. National MAIZE grower share
    # ========================================================

    maize_grower_share = (
        executor.execute(
            metric_id=
                "crop_grower_share",

            filters={
                "crop":
                    "MAIZE"
            }
        )
    )


    print(
        "\nNational MAIZE grower share:"
    )

    print(
        maize_grower_share
    )


    assert (
        abs(
            maize_grower_share.value
            - 0.42202768543923624
        )
        < 0.000001
    )

    # 1,579 household IDs appear in MAIZE planting records,
    # but 11 are outside the ag1=YES crop-growing denominator.
    # Evidence therefore reflects the 1,568 eligible MAIZE growers
    # actually participating in this metric's denominator.
    assert (
        maize_grower_share
        .evidence.households
        == 1568
    )

    assert (
        maize_grower_share
        .evidence.denominator_households
        == 3383
    )


    # ========================================================
    # 8. Kaduna crop-grower ranking
    # ========================================================

    kaduna_crop_ranking = (
        executor.execute(
            metric_id=
                "crop_grower_share",

            operation=
                "rank",

            filters={
                "state":
                    "Kaduna"
            },

            group_by=
                "crop",

            top_n=
                10,
        )
    )


    print(
        "\nKaduna crop-grower ranking:"
    )

    for row in (
        kaduna_crop_ranking.rows
    ):

        print(row)


    assert (
        kaduna_crop_ranking.rows[
            0
        ]["crop"]
        == "MAIZE"
    )

    assert (
        abs(
            kaduna_crop_ranking.rows[
                0
            ]["value"]
            - 0.742342
        )
        < 0.001
    )

    # 133 Kaduna household IDs appear in MAIZE planting records,
    # but 4 are outside the ag1=YES crop-growing denominator.
    # Evidence therefore uses the 129 eligible MAIZE growers.
    assert (
        kaduna_crop_ranking.rows[
            0
        ]["records"]
        == 129
    )

    assert (
        kaduna_crop_ranking.rows[
            0
        ][
            "denominator_households"
        ]
        == 169
    )


        # ========================================================
    # 9. RICE grower share ranked by state
    # ========================================================

    rice_state_grower_ranking = (
        executor.execute(
            metric_id=
                "crop_grower_share",

            operation=
                "rank",

            filters={
                "crop":
                    "RICE"
            },

            group_by=
                "state",

            top_n=
                5,
        )
    )


    print(
        "\nRICE grower share by state:"
    )


    for row in (
        rice_state_grower_ranking.rows
    ):

        print(row)


    assert (
        len(
            rice_state_grower_ranking.rows
        )
        > 0
    )


    assert all(
        row["records"] >= 30
        for row
        in rice_state_grower_ranking.rows
    )


    assert all(
        row[
            "denominator_households"
        ] > 0
        for row
        in rice_state_grower_ranking.rows
    )


    assert all(
        rice_state_grower_ranking.rows[
            index
        ]["value"]
        >=
        rice_state_grower_ranking.rows[
            index + 1
        ]["value"]

        for index
        in range(
            len(
                rice_state_grower_ranking.rows
            )
            - 1
        )
    )
    
    
    # ========================================================
    # 9. Protected evidence threshold cannot be weakened
    # ========================================================

    threshold_test = (
        executor.execute(
            metric_id=
                "median_completed_yield",

            operation=
                "rank",

            group_by=
                "crop",

            minimum_records=
                1,

            top_n=
                50,
        )
    )


    assert all(
        row["records"] >= 20
        for row
        in threshold_test.rows
    )


    # ========================================================
    # 10. Unknown metric rejected
    # ========================================================

    unknown_rejected = False


    try:

        executor.execute(
            metric_id=
                "invented_metric"
        )

    except KeyError:

        unknown_rejected = True


    assert (
        unknown_rejected
        is True
    )


    print(
        "\nUnknown metric rejected:",
        unknown_rejected
    )


    loader.close()


    print(
        "\nANALYTICS EXECUTOR TEST: PASSED"
    )


if __name__ == "__main__":
    main()