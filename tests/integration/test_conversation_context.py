from packages.data_release.loader import (
    AgDAReleaseLoader,
)

from packages.analytics.registry import (
    MetricRegistry,
)

from packages.question_router.router import (
    QuestionRouter,
)

from packages.question_router.conversation import (
    ConversationContext,
    ContextualQuestionResolver,
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


    router = (
        QuestionRouter(
            connection=
                connection,

            registry=
                registry,

            metric_version=
                loader.release_info()[
                    "metric_version"
                ],
        )
    )


    resolver = (
        ContextualQuestionResolver(
            router
        )
    )


    print(
        "\n========================================"
    )

    print(
        "AgDA CONVERSATION CONTEXT"
    )

    print(
        "========================================"
    )


    # ========================================================
    # BASE CONTEXT
    # ========================================================

    base = router.interpret(
        "Which states have the highest grower share for RICE?"
    )


    assert (
        base.status.value
        == "interpreted"
    )


    context = (
        ConversationContext(
            last_interpretation=
                base
        )
    )


    # ========================================================
    # 1. Geography follow-up
    # ========================================================

    kaduna = resolver.resolve(
        "What about Kaduna?",
        context,
    )


    print(
        "\nFOLLOW-UP: What about Kaduna?"
    )

    print(
        kaduna
    )


    assert (
        kaduna is not None
    )

    assert (
        kaduna.metric_id
        == "crop_grower_share"
    )

    assert (
        kaduna.operation.value
        == "value"
    )

    assert (
        kaduna.group_by
        is None
    )

    assert (
        kaduna.filters
        == {
            "crop":
                "RICE",

            "state":
                "Kaduna",
        }
    )


    # ========================================================
    # 2. Metric-switch follow-up
    # ========================================================

    commercialization = (
        resolver.resolve(
            "Show commercialization instead",
            context,
        )
    )


    print(
        "\nFOLLOW-UP: Show commercialization instead"
    )

    print(
        commercialization
    )


    assert (
        commercialization
        is not None
    )

    assert (
        commercialization.metric_id
        == "median_commercialization_share"
    )

    assert (
        commercialization.operation.value
        == "rank"
    )

    assert (
        commercialization.group_by
        == "state"
    )

    assert (
        commercialization.filters
        == {
            "crop":
                "RICE"
        }
    )


    # ========================================================
    # 3. Crop replacement follow-up
    # ========================================================

    maize = resolver.resolve(
        "What about maize?",
        context,
    )


    print(
        "\nFOLLOW-UP: What about maize?"
    )

    print(
        maize
    )


    assert (
        maize is not None
    )

    assert (
        maize.metric_id
        == "crop_grower_share"
    )

    assert (
        maize.operation.value
        == "rank"
    )

    assert (
        maize.group_by
        == "state"
    )

    assert (
        maize.filters
        == {
            "crop":
                "MAIZE"
        }
    )


    # ========================================================
    # 4. Scalar crop continuation
    # ========================================================

    sales_base = router.interpret(
        "How much maize do farmers sell?"
    )


    sales_context = (
        ConversationContext(
            last_interpretation=
                sales_base
        )
    )


    rice_sales = resolver.resolve(
        "What about rice?",
        sales_context,
    )


    assert (
        rice_sales is not None
    )

    assert (
        rice_sales.metric_id
        == "median_commercialization_share"
    )

    assert (
        rice_sales.operation.value
        == "value"
    )

    assert (
        rice_sales.filters
        == {
            "crop":
                "RICE"
        }
    )


    # ========================================================
    # 5. Full standalone question must NOT hijack context
    # ========================================================

    standalone = resolver.resolve(
        "How risky is flooding in the North West?",
        context,
    )


    assert (
        standalone is None
    )


    print(
        "\nStandalone question correctly ignored by context resolver:",
        standalone is None
    )


    loader.close()


    print(
        "\nCONVERSATION CONTEXT TEST: PASSED"
    )


if __name__ == "__main__":
    main()