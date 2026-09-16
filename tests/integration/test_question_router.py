from packages.data_release.loader import (
    AgDAReleaseLoader
)

from packages.analytics.registry import (
    MetricRegistry
)

from packages.question_router.router import (
    QuestionRouter
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


    cases = [
        {
            "question":
                "What crops do people farm most in Kaduna?",

            "status":
                "interpreted",

            "metric_id":
                "crop_grower_share",

            "operation":
                "rank",

            "group_by":
                "crop",

            "filters": {
                "state":
                    "Kaduna"
            },
        },

        {
            "question":
                "Which crops have the highest yields in Nigeria?",

            "status":
                "interpreted",

            "metric_id":
                "median_completed_yield",

            "operation":
                "rank",

            "group_by":
                "crop",

            "filters":
                {},
        },

        {
            "question":
                "How much maize do farmers sell?",

            "status":
                "interpreted",

            "metric_id":
                "median_commercialization_share",

            "operation":
                "value",

            "group_by":
                None,

            "filters": {
                "crop":
                    "MAIZE"
            },
        },

        {
            "question":
                "Is food security better after harvest?",

            "status":
                "interpreted",

            "metric_id":
                "food_insecurity_change",

            "operation":
                "value",

            "group_by":
                None,

            "filters":
                {},
        },

        {
            "question":
                "What climate risk is highest?",

            "status":
                "interpreted",

            "metric_id":
                "climate_likely_share",

            "operation":
                "rank",

            "group_by":
                "climate_event",

            "filters":
                {},
        },

        {
            "question":
                "How risky is flooding in the North West?",

            "status":
                "interpreted",

            "metric_id":
                "climate_likely_share",

            "operation":
                "value",

            "group_by":
                None,

            "filters": {
                "zone":
                    "North West",

                "climate_event":
                    "Flood",
            },
        },
        
        {
            "question":
                "Which states have the highest grower share for rice?",

            "status":
                "interpreted",

            "metric_id":
                "crop_grower_share",

            "operation":
                "rank",

            "group_by":
                "state",

            "filters": {
                "crop":
                    "RICE"
            },
        },

        {
            "question":
                "Should I farm maize in Katsina?",

            "status":
                "reframe_required",
        },

        {
            "question":
                "Which state looks strongest for rice?",

            "status":
                "needs_clarification",
        },

        {
            "question":
                "Does extension improve yield?",

            "status":
                "reframe_required",
        },

        {
            "question":
                "What is the most profitable crop?",

            "status":
                "unsupported",
        },

        {
            "question":
                "What are farmers mostly growing in Kaduna?",

            "status":
                "interpreted",

            "metric_id":
                "crop_grower_share",

            "operation":
                "rank",

            "group_by":
                "crop",

            "filters": {
                "state":
                    "Kaduna"
            },
        },

        {
            "question":
                "Where is rice grown most commonly?",
        
            "status":
                "interpreted",
        
            "metric_id":
                "crop_grower_share",
        
            "operation":
                "rank",
        
            "group_by":
                "state",
        
            "filters": {
                "crop":
                    "RICE"
            },
        },

        {
            "question":
                "Which of those states gets the best rice yields?",
        
            "status":
                "interpreted",
        
            "metric_id":
                "median_completed_yield",
        
            "operation":
                "rank",
        
            "group_by":
                "state",
        
            "filters": {
                "crop":
                    "RICE"
            },
        },
        
        {
            "question":
                "Where are rice farmers selling the largest share of their harvest?",
        
            "status":
                "interpreted",
        
            "metric_id":
                "median_commercialization_share",
        
            "operation":
                "rank",
        
            "group_by":
                "state",
        
            "filters": {
                "crop":
                    "RICE"
            },
        },
        
        {
            "question":
                "How worried are communities in the North West about flooding?",
        
            "status":
                "interpreted",
        
            "metric_id":
                "climate_likely_share",
        
            "operation":
                "value",
        
            "group_by":
                None,
        
            "filters": {
                "zone":
                    "North West",
        
                "climate_event":
                    "Flood"
            },
        },
        
        {
            "question":
                "Which climate threat is viewed as the biggest overall?",
        
            "status":
                "interpreted",
        
            "metric_id":
                "climate_likely_share",
        
            "operation":
                "rank",
        
            "group_by":
                "climate_event",
        
            "filters": {},
        },

        {
            "question":
                (
                    "Would rice be a good crop "
                    "for me to plant there?"
                ),
        
            "status":
                "reframe_required",
        
            "metric_id":
                None,
        
            "operation":
                None,
        
            "group_by":
                None,
        
            "filters": {},
        },
        
        {
            "question":
                (
                    "Does that mean rice is "
                    "more profitable there?"
                ),
        
            "status":
                "unsupported",
        
            "metric_id":
                None,
        
            "operation":
                None,
        
            "group_by":
                None,
        
            "filters": {},
        },
            ]


    passed = 0


    print(
        "\n========================================"
    )

    print(
        "AgDA QUESTION ROUTER"
    )

    print(
        "========================================"
    )


    for case in cases:

        result = router.interpret(
            case[
                "question"
            ]
        )


        print(
            "\nQUESTION:",
            case["question"]
        )

        print(
            "STATUS:",
            result.status.value
        )

        print(
            "METRIC:",
            result.metric_id
        )

        print(
            "OPERATION:",
            (
                result.operation.value
                if result.operation
                else None
            )
        )

        print(
            "GROUP BY:",
            result.group_by
        )

        print(
            "FILTERS:",
            result.filters
        )


        assert (
            result.status.value
            == case["status"]
        )


        if (
            case["status"]
            == "interpreted"
        ):

            assert (
                result.metric_id
                == case["metric_id"]
            )

            assert (
                result.operation.value
                == case["operation"]
            )

            assert (
                result.group_by
                == case["group_by"]
            )

            assert (
                result.filters
                == case["filters"]
            )

            assert (
                result.question_specification
                is not None
            )

            assert (
                result
                .question_specification
                .metric_version
                == "1.0.0"
            )


        passed += 1


    print(
        "\nRouter tests passed:",
        passed,
        "/",
        len(cases)
    )


    assert (
        passed == len(cases)
    )


    loader.close()


    print(
        "\nQUESTION ROUTER TEST: PASSED"
    )


if __name__ == "__main__":
    main()