from packages.data_release.loader import (
    AgDAReleaseLoader,
)

from packages.analytics.registry import (
    MetricRegistry,
)

from packages.analytics.executor import (
    AnalyticsExecutor,
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

from packages.answering.service import (
    AnswerService,
)


def main():

    # ========================================================
    # RUNTIME
    # ========================================================

    loader = AgDAReleaseLoader()

    connection = loader.open()

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


    service = (
        AnswerService(
            pipeline=
                pipeline,

            data_version=
                release_info[
                    "data_version"
                ],

            metric_version=
                release_info[
                    "metric_version"
                ],
        )
    )


    print(
        "\n========================================"
    )

    print(
        "AgDA ANSWER SERVICE"
    )

    print(
        "========================================"
    )


    # ========================================================
    # 1. Flood
    # ========================================================

    flood = service.answer(
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
        "ANSWER:",
        flood.answer_text
    )


    assert (
        flood.status
        == "answered"
    )

    assert (
        flood.result[
            "value"
        ]
        == 0.125
    )

    assert (
        "12.5%"
        in flood.answer_text
    )

    assert (
        flood.evidence.records
        == 80
    )

    assert (
        flood.evidence.evidence_grade
        == "Strong"
    )

    assert (
        flood.data_version
        == "wave5_v1"
    )

    assert (
        flood.metric_version
        == "1.0.0"
    )


    # ========================================================
    # 2. MAIZE commercialization
    # ========================================================

    maize_sales = service.answer(
        "How much maize do farmers sell?"
    )


    print(
        "\nQUESTION:",
        maize_sales.question
    )

    print(
        "ANSWER:",
        maize_sales.answer_text
    )


    assert (
        maize_sales.status
        == "answered"
    )

    assert (
        "25.0%"
        in maize_sales.answer_text
    )

    assert (
        "median share"
        in maize_sales.answer_text.lower()
    )

    assert (
        maize_sales.evidence.records
        == 1502
    )


    # ========================================================
    # 3. Yield ranking
    # ========================================================

    yields = service.answer(
        "Which crops have the highest yields in Nigeria?"
    )


    print(
        "\nQUESTION:",
        yields.question
    )

    print(
        "ANSWER:",
        yields.answer_text
    )


    assert (
        yields.status
        == "answered"
    )

    assert (
        yields.result[
            0
        ]["crop"]
        == "YAM, THREE LEAVED"
    )

    assert (
        "YAM, THREE LEAVED"
        in yields.answer_text
    )

    assert (
        "9,091.0 kg/ha"
        in yields.answer_text
    )

    assert (
        yields.visualization
        is not None
    )

    assert (
        yields.visualization
        .recommended
        is True
    )

    assert (
        yields.visualization
        .visual_type
        == "horizontal_bar"
    )


    # ========================================================
    # 4. Kaduna crop ranking
    # ========================================================

    kaduna = service.answer(
        "What crops do people farm most in Kaduna?"
    )


    print(
        "\nQUESTION:",
        kaduna.question
    )

    print(
        "ANSWER:",
        kaduna.answer_text
    )


    assert (
        kaduna.status
        == "answered"
    )

    assert (
        "MAIZE"
        in kaduna.answer_text
    )

    assert (
        "74.2%"
        in kaduna.answer_text
    )

    assert (
        kaduna.result[
            0
        ]["records"]
        == 129
    )


    # ========================================================
    # 5. Food security
    # ========================================================

    food_security = service.answer(
        "Is food security better after harvest?"
    )


    print(
        "\nQUESTION:",
        food_security.question
    )

    print(
        "ANSWER:",
        food_security.answer_text
    )


    assert (
        food_security.status
        == "answered"
    )

    assert (
        "0.30 points lower"
        in food_security.answer_text
    )

    assert (
        food_security.evidence.records
        == 4715
    )


    # ========================================================
    # 6. Clarification
    # ========================================================

    clarification = service.answer(
        "Which state looks strongest for rice?"
    )


    print(
        "\nQUESTION:",
        clarification.question
    )

    print(
        "STATUS:",
        clarification.status
    )

    print(
        "ANSWER:",
        clarification.answer_text
    )


    assert (
        clarification.status
        == "needs_clarification"
    )

    assert (
        clarification.clarification
        is not None
    )

    assert (
        "observed yield"
        in clarification.answer_text
    )

    assert (
        "commercialization share"
        in clarification.answer_text
    )


    # ========================================================
    # 7. Causal reframe
    # ========================================================

    causal = service.answer(
        "Does extension improve yield?"
    )


    assert (
        causal.status
        == "reframe_required"
    )

    assert (
        causal.reframe
        is not None
    )

    assert (
        "not causal claims"
        in causal.answer_text
    )


    # ========================================================
    # 8. Recommendation reframe
    # ========================================================

    recommendation = service.answer(
        "Should I farm maize in Katsina?"
    )


    assert (
        recommendation.status
        == "reframe_required"
    )

    assert (
        recommendation.reframe
        is not None
    )


    # ========================================================
    # 9. Profitability
    # ========================================================

    profitability = service.answer(
        "What is the most profitable crop?"
    )


    assert (
        profitability.status
        == "unsupported"
    )

    assert (
        "production-cost"
        in profitability.answer_text
    )


    # ========================================================
    # 10. JSON-serializable production payload
    # ========================================================

    payload = (
        flood.model_dump(
            mode="json"
        )
    )


    assert (
        payload[
            "status"
        ]
        == "answered"
    )

    assert (
        payload[
            "question_specification"
        ][
            "metric_id"
        ]
        == "climate_likely_share"
    )


    print(
        "\nExample serialized payload:"
    )

    print(
        payload
    )


    loader.close()


    print(
        "\nANSWER SERVICE TEST: PASSED"
    )


if __name__ == "__main__":
    main()