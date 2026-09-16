from packages.data_release.loader import (
    AgDAReleaseLoader,
)

from packages.analytics.registry import (
    MetricRegistry,
)

from packages.analytics.executor import (
    AnalyticsExecutor,
    ScalarMetricResult,
    TableMetricResult,
)

from packages.analytics.question_executor import (
    QuestionSpecificationExecutor,
)

from packages.question_router.router import (
    QuestionRouter,
)

from packages.answering.pipeline import (
    QuestionPipeline,
)


def main():

    # ========================================================
    # PRODUCTION RUNTIME
    # ========================================================

    loader = (
        AgDAReleaseLoader()
    )

    connection = (
        loader.open()
    )

    release_info = (
        loader.release_info()
    )


    registry = (
        MetricRegistry.from_connection(
            connection
        )
    )


    analytics_executor = (
        AnalyticsExecutor(
            connection=
                connection,

            registry=
                registry,
        )
    )


    specification_executor = (
        QuestionSpecificationExecutor(
            executor=
                analytics_executor,

            registry=
                registry,

            metric_version=
                release_info[
                    "metric_version"
                ],
        )
    )


    router = (
        QuestionRouter(
            connection=
                connection,

            registry=
                registry,

            metric_version=
                release_info[
                    "metric_version"
                ],
        )
    )


    pipeline = (
        QuestionPipeline(
            router=
                router,

            specification_executor=
                specification_executor,
        )
    )


    print(
        "\n========================================"
    )

    print(
        "AgDA QUESTION → ANALYTICS PIPELINE"
    )

    print(
        "========================================"
    )


    # ========================================================
    # 1. North West Flood
    # ========================================================

    flood = pipeline.run(
        "How risky is flooding in the North West?"
    )


    print(
        "\nQUESTION:",
        flood.question
    )

    print(
        "STATUS:",
        flood.status
    )

    print(
        "RESULT:",
        flood.result
    )


    assert (
        flood.status
        == "answered"
    )

    assert isinstance(
        flood.result,
        ScalarMetricResult
    )

    assert (
        flood.result.metric_id
        == "climate_likely_share"
    )

    assert (
        abs(
            flood.result.value
            - 0.125
        )
        < 0.000001
    )

    assert (
        flood.result.evidence.records
        == 80
    )


    # ========================================================
    # 2. MAIZE commercialization
    # ========================================================

    maize_sales = pipeline.run(
        "How much maize do farmers sell?"
    )


    print(
        "\nQUESTION:",
        maize_sales.question
    )

    print(
        "STATUS:",
        maize_sales.status
    )

    print(
        "RESULT:",
        maize_sales.result
    )


    assert (
        maize_sales.status
        == "answered"
    )

    assert isinstance(
        maize_sales.result,
        ScalarMetricResult
    )

    assert (
        maize_sales.result.metric_id
        == "median_commercialization_share"
    )

    assert (
        maize_sales.result.filters
        == {
            "crop":
                "MAIZE"
        }
    )

    assert (
        abs(
            maize_sales.result.value
            - 25.0
        )
        < 0.000001
    )

    assert (
        maize_sales.result
        .evidence.records
        == 1502
    )


    # ========================================================
    # 3. National crop yield ranking
    # ========================================================

    crop_yields = pipeline.run(
        "Which crops have the highest yields in Nigeria?"
    )


    print(
        "\nQUESTION:",
        crop_yields.question
    )

    print(
        "STATUS:",
        crop_yields.status
    )

    print(
        "TOP RESULT:",
        crop_yields.result.rows[0]
    )


    assert (
        crop_yields.status
        == "answered"
    )

    assert isinstance(
        crop_yields.result,
        TableMetricResult
    )

    assert (
        crop_yields.result.metric_id
        == "median_completed_yield"
    )

    assert (
        crop_yields.result.group_by
        == "crop"
    )

    assert (
        crop_yields.result.rows[
            0
        ]["crop"]
        == "YAM, THREE LEAVED"
    )

    assert (
        crop_yields.result.rows[
            0
        ]["records"]
        == 39
    )


    # ========================================================
    # 4. Kaduna crop prevalence
    # ========================================================

    kaduna_crops = pipeline.run(
        "What crops do people farm most in Kaduna?"
    )


    print(
        "\nQUESTION:",
        kaduna_crops.question
    )

    print(
        "STATUS:",
        kaduna_crops.status
    )

    print(
        "TOP RESULT:",
        kaduna_crops.result.rows[0]
    )


    assert (
        kaduna_crops.status
        == "answered"
    )

    assert isinstance(
        kaduna_crops.result,
        TableMetricResult
    )

    assert (
        kaduna_crops.result.metric_id
        == "crop_grower_share"
    )

    assert (
        kaduna_crops.result.rows[
            0
        ]["crop"]
        == "MAIZE"
    )

    # Production evidence denominator correction
    assert (
        kaduna_crops.result.rows[
            0
        ]["records"]
        == 129
    )

    assert (
        kaduna_crops.result.rows[
            0
        ][
            "denominator_households"
        ]
        == 169
    )


    # ========================================================
    # 5. Food-security change
    # ========================================================

    food_security = pipeline.run(
        "Is food security better after harvest?"
    )


    assert (
        food_security.status
        == "answered"
    )

    assert isinstance(
        food_security.result,
        ScalarMetricResult
    )

    assert (
        food_security.result.metric_id
        == "food_insecurity_change"
    )

    assert (
        abs(
            food_security.result.value
            - (-0.29724130404015003)
        )
        < 0.000001
    )


    # ========================================================
    # 6. Recommendation must NOT execute
    # ========================================================

    recommendation = pipeline.run(
        "Should I farm maize in Katsina?"
    )


    print(
        "\nQUESTION:",
        recommendation.question
    )

    print(
        "STATUS:",
        recommendation.status
    )

    print(
        "RESULT:",
        recommendation.result
    )


    assert (
        recommendation.status
        == "reframe_required"
    )

    assert (
        recommendation.result
        is None
    )


    # ========================================================
    # 7. Causal question must NOT execute
    # ========================================================

    causal = pipeline.run(
        "Does extension improve yield?"
    )


    assert (
        causal.status
        == "reframe_required"
    )

    assert (
        causal.result
        is None
    )


    # ========================================================
    # 8. Profitability must NOT execute
    # ========================================================

    profitability = pipeline.run(
        "What is the most profitable crop?"
    )


    assert (
        profitability.status
        == "unsupported"
    )

    assert (
        profitability.result
        is None
    )


    # ========================================================
    # 9. Ambiguity must NOT execute
    # ========================================================

    ambiguity = pipeline.run(
        "Which state looks strongest for rice?"
    )


    assert (
        ambiguity.status
        == "needs_clarification"
    )

    assert (
        ambiguity.result
        is None
    )


    # ========================================================
    # 10. Metric version mismatch must fail closed
    # ========================================================

    specification = (
        flood.interpretation
        .question_specification
        .model_copy(
            update={
                "metric_version":
                    "999.0.0"
            }
        )
    )


    version_rejected = False


    try:

        specification_executor.execute(
            specification
        )

    except ValueError:

        version_rejected = True


    assert (
        version_rejected
        is True
    )


    print(
        "\nMetric-version mismatch rejected:",
        version_rejected
    )


    loader.close()


    print(
        "\nQUESTION PIPELINE TEST: PASSED"
    )


if __name__ == "__main__":
    main()