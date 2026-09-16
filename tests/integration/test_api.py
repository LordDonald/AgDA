from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)


def main():

    print(
        "\n========================================"
    )

    print(
        "AgDA FASTAPI"
    )

    print(
        "========================================"
    )


    with TestClient(
        app
    ) as client:

        # ====================================================
        # 1. Root
        # ====================================================

        root = client.get(
            "/"
        )


        assert (
            root.status_code
            == 200
        )

        print(
            "\nROOT:"
        )

        print(
            root.json()
        )


        # ====================================================
        # 2. Health
        # ====================================================

        health = client.get(
            "/v1/health"
        )


        assert (
            health.status_code
            == 200
        )


        health_payload = (
            health.json()
        )


        print(
            "\nHEALTH:"
        )

        print(
            health_payload
        )


        assert (
            health_payload[
                "ready"
            ]
            is True
        )

        assert (
            health_payload[
                "status"
            ]
            == "ready"
        )

        assert (
            health_payload[
                "data_version"
            ]
            == "wave5_v1"
        )

        assert (
            health_payload[
                "release_state"
            ]
            == "stable"
        )

        assert (
            health_payload[
                "metric_version"
            ]
            == "1.0.0"
        )

        assert (
            health_payload[
                "registered_metrics"
            ]
            == 18
        )


        # ====================================================
        # 3. Flood question
        # ====================================================

        flood = client.post(
            "/v1/questions",

            json={
                "question":
                    "How risky is flooding in the North West?"
            },
        )


        assert (
            flood.status_code
            == 200
        )


        flood_payload = (
            flood.json()
        )


        print(
            "\nFLOOD RESPONSE:"
        )

        print(
            flood_payload
        )


        assert (
            flood_payload[
                "status"
            ]
            == "answered"
        )

        assert (
            flood_payload[
                "result"
            ][
                "value"
            ]
            == 0.125
        )

        assert (
            flood_payload[
                "evidence"
            ][
                "records"
            ]
            == 80
        )

        assert (
            "12.5%"
            in flood_payload[
                "answer_text"
            ]
        )


        # ====================================================
        # 4. Ranked crop question
        # ====================================================

        crops = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "What crops do people "
                        "farm most in Kaduna?"
                    ),

                "max_rank_items":
                    3,
            },
        )


        assert (
            crops.status_code
            == 200
        )


        crop_payload = (
            crops.json()
        )


        print(
            "\nKADUNA RESPONSE:"
        )

        print(
            crop_payload
        )


        assert (
            crop_payload[
                "status"
            ]
            == "answered"
        )

        assert (
            len(
                crop_payload[
                    "result"
                ]
            )
            == 3
        )

        assert (
            crop_payload[
                "result"
            ][0][
                "crop"
            ]
            == "MAIZE"
        )

        assert (
            crop_payload[
                "result"
            ][0][
                "records"
            ]
            == 129
        )


        # ====================================================
        # 5. Clarification
        # ====================================================

        clarification = (
            client.post(
                "/v1/questions",

                json={
                    "question":
                        (
                            "Which state looks "
                            "strongest for rice?"
                        )
                },
            )
        )


        assert (
            clarification.status_code
            == 200
        )


        clarification_payload = (
            clarification.json()
        )


        assert (
            clarification_payload[
                "status"
            ]
            == "needs_clarification"
        )

        assert (
            clarification_payload[
                "clarification"
            ]
            is not None
        )


        # ====================================================
        # 6. Causal request
        # ====================================================

        causal = client.post(
            "/v1/questions",

            json={
                "question":
                    "Does extension improve yield?"
            },
        )


        assert (
            causal.status_code
            == 200
        )

        assert (
            causal.json()[
                "status"
            ]
            == "reframe_required"
        )


        # ====================================================
        # 7. Profitability
        # ====================================================

        profitability = (
            client.post(
                "/v1/questions",

                json={
                    "question":
                        (
                            "What is the most "
                            "profitable crop?"
                        )
                },
            )
        )


        assert (
            profitability.status_code
            == 200
        )

        assert (
            profitability.json()[
                "status"
            ]
            == "unsupported"
        )


        # ====================================================
        # 8. Unknown client field rejected
        # ====================================================

        bad_request = client.post(
            "/v1/questions",

            json={
                "question":
                    "What is maize yield?",

                "table_name":
                    "households_wave5",
            },
        )


        assert (
            bad_request.status_code
            == 422
        )


        # ====================================================
        # 9. Empty question rejected
        # ====================================================

        empty_request = client.post(
            "/v1/questions",

            json={
                "question":
                    ""
            },
        )


        assert (
            empty_request.status_code
            == 422
        )


        # ====================================================
        # 10. Visualization suppression
        # ====================================================

        no_visual = client.post(
            "/v1/questions",

            json={
                "question":
                    (
                        "Which crops have the "
                        "highest yields in Nigeria?"
                    ),

                "include_visualization":
                    False,
            },
        )


        assert (
            no_visual.status_code
            == 200
        )

        assert (
            no_visual.json()[
                "visualization"
            ]
            is None
        )

        # ====================================================
        # 11. Metric catalog
        # ====================================================

        metrics = client.get(
            "/v1/metrics"
        )

        assert (
            metrics.status_code
            == 200
        )

        metrics_payload = (
            metrics.json()
        )

        assert (
            metrics_payload[
                "count"
            ]
            == 18
        )

        assert (
            any(
                item[
                    "metric_id"
                ]
                == "median_completed_yield"
                for item
                in metrics_payload[
                    "metrics"
                ]
            )
        )


        # ====================================================
        # 12. Entity catalogs
        # ====================================================

        expected_entity_counts = {
            "states": 37,
            "zones": 6,
            "crops": 52,
            "items": 111,
            "climate-events": 4,
        }


        for (
            entity_type,
            expected_count
        ) in expected_entity_counts.items():

            response = client.get(
                f"/v1/entities/{entity_type}"
            )

            assert (
                response.status_code
                == 200
            )

            payload = response.json()

            assert (
                payload[
                    "count"
                ]
                == expected_count
            )


        # ====================================================
        # 13. Unknown entity type
        # ====================================================

        unknown_entity = client.get(
            "/v1/entities/unknown"
        )

        assert (
            unknown_entity.status_code
            == 404
        )


    print(
        "\nFASTAPI INTEGRATION TEST: PASSED"
    )


if __name__ == "__main__":
    main()