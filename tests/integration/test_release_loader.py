from packages.data_release.loader import (
    AgDAReleaseLoader
)


def main():

    loader = (
        AgDAReleaseLoader()
    )

    connection = (
        loader.open()
    )


    print(
        "\n========================================"
    )

    print(
        "AgDA STABLE RELEASE LOADER"
    )

    print(
        "========================================"
    )


    print(
        "\nRelease info:"
    )

    print(
        loader.release_info()
    )


    objects = (
        loader.list_registered_objects()
    )


    print(
        "\nRegistered DuckDB objects:"
    )

    print(
        objects.to_string(
            index=False
        )
    )


    print(
        "\nRegistered object count:",
        len(objects)
    )


    # --------------------------------------------------------
    # Core row-count smoke tests
    # --------------------------------------------------------

    household_rows = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM households_wave5
            """
        ).fetchone()[0]
    )


    production_rows = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM field_crop_production_wave5
            """
        ).fetchone()[0]
    )


    state_crop_rows = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM state_crop_context_view
            """
        ).fetchone()[0]
    )


    metric_count = (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM analytical_metric_registry
            """
        ).fetchone()[0]
    )


    print(
        "\nSmoke-test counts:"
    )

    print(
        "households_wave5:",
        household_rows
    )

    print(
        "field_crop_production_wave5:",
        production_rows
    )

    print(
        "state_crop_context_view:",
        state_crop_rows
    )

    print(
        "analytical_metric_registry:",
        metric_count
    )


    assert (
        household_rows == 4715
    )

    assert (
        production_rows == 10071
    )

    assert (
        state_crop_rows == 424
    )

    assert (
        metric_count == 18
    )


    # --------------------------------------------------------
    # Analytical benchmark smoke test
    # --------------------------------------------------------

    maize_completed_yield = (
        connection.execute(
            """
            SELECT MEDIAN(
                observed_yield_kg_per_ha
            )
            FROM field_crop_production_wave5
            WHERE
                completed_yield_eligible = TRUE
                AND UPPER(crop_name) = 'MAIZE'
            """
        ).fetchone()[0]
    )


    print(
        "\nMAIZE completed-harvest median yield:",
        maize_completed_yield
    )


    assert (
        abs(
            maize_completed_yield
            - 1666.6666
        )
        < 0.01
    )


    loader.close()


    print(
        "\nRELEASE LOADER SMOKE TEST: PASSED"
    )


if __name__ == "__main__":
    main()