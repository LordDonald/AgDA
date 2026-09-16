from packages.data_release.loader import (
    AgDAReleaseLoader
)

from packages.analytics.registry import (
    MetricRegistry
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


    print(
        "\n========================================"
    )

    print(
        "AgDA METRIC REGISTRY"
    )

    print(
        "========================================"
    )


    print(
        "Metric count:",
        registry.count()
    )


    assert (
        registry.count()
        == 18
    )


    metric_ids = (
        registry.list_metric_ids()
    )


    print(
        "\nMetric IDs:"
    )

    for metric_id in metric_ids:

        print(
            metric_id
        )


    # --------------------------------------------------------
    # Benchmark key metric definitions
    # --------------------------------------------------------

    yield_metric = (
        registry.get(
            "median_completed_yield"
        )
    )


    print(
        "\nCompleted-yield definition:"
    )

    print(
        yield_metric
    )


    assert (
        yield_metric.table_name
        == "field_crop_production_wave5"
    )

    assert (
        yield_metric.value_column
        == "observed_yield_kg_per_ha"
    )

    assert (
        yield_metric.aggregation
        == "median"
    )

    assert (
        yield_metric.evidence_filters
        == {
            "completed_yield_eligible":
                True
        }
    )

    assert (
        yield_metric.unit
        == "kg/ha"
    )

    assert (
        yield_metric
        .causal_interpretation_allowed
        is False
    )


    climate_metric = (
        registry.get(
            "climate_likely_share"
        )
    )


    assert (
        climate_metric.table_name
        == "climate_context_wave5"
    )

    assert (
        climate_metric.indicator_column
        == "likely_or_extremely_likely"
    )

    assert (
        climate_metric.unit
        == "proportion"
    )


    seller_metric = (
        registry.get(
            "crop_seller_rate"
        )
    )


    assert (
        seller_metric.aggregation
        == "weighted_proportion"
    )


    unknown_metric_rejected = False


    try:

        registry.get(
            "made_up_metric"
        )

    except KeyError:

        unknown_metric_rejected = True


    assert (
        unknown_metric_rejected
        is True
    )


    print(
        "\nUnknown metric rejected:",
        unknown_metric_rejected
    )


    loader.close()


    print(
        "\nMETRIC REGISTRY TEST: PASSED"
    )


if __name__ == "__main__":
    main()