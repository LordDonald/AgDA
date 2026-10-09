from __future__ import annotations

from fastapi.testclient import (
    TestClient,
)

from apps.api.app.main import (
    app,
)


def main():

    with TestClient(
        app
    ) as client:

        # ====================================================
        # 1. LOW PRODUCTIVITY MUST MEAN ASCENDING YIELD
        # ====================================================

        low_productivity = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Which states should I pay "
                        "the most attention to for "
                        "low agricultural productivity?"
                    )
            },
        )

        assert (
            low_productivity.status_code
            == 200
        )

        low_spec = (
            low_productivity.json()[
                "question_specification"
            ]
        )

        assert (
            low_spec["metric_id"]
            == "median_completed_yield"
        )

        assert (
            low_spec["operation"]
            == "rank"
        )

        assert (
            low_spec["group_by"]
            == "state"
        )

        assert (
            low_spec["ascending"]
            is True
        )


        # ====================================================
        # 2. HIGHEST -> LOWEST FOLLOW-UP
        # ====================================================

        direction_conversation = (
            "pilot_direction_regression"
        )

        highest = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Which states have the "
                        "highest observed crop yields?"
                    ),
                "conversation_id":
                    direction_conversation,
            },
        )

        assert (
            highest.status_code
            == 200
        )


        lowest = client.post(
            "/v1/questions",
            json={
                "question":
                    "And which have the lowest?",
                "conversation_id":
                    direction_conversation,
            },
        )

        assert (
            lowest.status_code
            == 200
        )

        lowest_payload = (
            lowest.json()
        )

        assert (
            lowest_payload["status"]
            == "answered"
        )

        lowest_spec = (
            lowest_payload[
                "question_specification"
            ]
        )

        assert (
            lowest_spec["metric_id"]
            == "median_completed_yield"
        )

        assert (
            lowest_spec["operation"]
            == "rank"
        )

        assert (
            lowest_spec["group_by"]
            == "state"
        )

        assert (
            lowest_spec["ascending"]
            is True
        )


        # ====================================================
        # 3. FLOOD RANKING LANGUAGE
        # ====================================================

        flood_rank = client.post(
            "/v1/questions",
            json={
                "question":
                    "Where is flooding most common?"
            },
        )

        assert (
            flood_rank.status_code
            == 200
        )

        flood_payload = (
            flood_rank.json()
        )

        assert (
            flood_payload["status"]
            == "answered"
        )

        flood_spec = (
            flood_payload[
                "question_specification"
            ]
        )

        assert (
            flood_spec["metric_id"]
            == "climate_likely_share"
        )

        assert (
            flood_spec["operation"]
            == "rank"
        )

        assert (
            flood_spec["group_by"]
            == "zone"
        )

        assert (
            flood_spec["filters"][
                "climate_event"
            ]
            == "Flood"
        )


        flood_answer_text = (
            flood_payload[
                "answer_text"
            ].lower()
        )

        assert (
            "among zones"
            in flood_answer_text
        )

        assert (
            "flood"
            in flood_answer_text
        )

        assert (
            "among assessed climate events"
            not in flood_answer_text
        )


        # ====================================================
        # 4. FLOOD CONTEXT -> REGION RANK
        # ====================================================

        flood_conversation = (
            "pilot_flood_regression"
        )

        flood_base = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "How risky is flooding "
                        "in the North West?"
                    ),
                "conversation_id":
                    flood_conversation,
            },
        )

        assert (
            flood_base.status_code
            == 200
        )


        flood_followup = client.post(
            "/v1/questions",
            json={
                "question":
                    "Which region is most affected?",
                "conversation_id":
                    flood_conversation,
            },
        )

        assert (
            flood_followup.status_code
            == 200
        )

        flood_followup_payload = (
            flood_followup.json()
        )

        assert (
            flood_followup_payload[
                "status"
            ]
            == "answered"
        )

        followup_spec = (
            flood_followup_payload[
                "question_specification"
            ]
        )

        assert (
            followup_spec["metric_id"]
            == "climate_likely_share"
        )

        assert (
            followup_spec["operation"]
            == "rank"
        )

        assert (
            followup_spec["group_by"]
            == "zone"
        )

        assert (
            "zone"
            not in followup_spec["filters"]
        )

        assert (
            followup_spec["filters"][
                "climate_event"
            ]
            == "Flood"
        )


        # ====================================================
        # 5. GENERIC FOOD INSECURITY MUST NOT BECOME CHANGE
        # ====================================================

        food = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "How common is food "
                        "insecurity overall?"
                    )
            },
        )

        assert (
            food.status_code
            == 200
        )

        food_payload = (
            food.json()
        )

        assert (
            food_payload["status"]
            == "needs_clarification"
        )

        assert (
            "food_insecurity_change"
            not in (
                food_payload.get(
                    "metric_candidates"
                )
                or []
            )
        )


        # ====================================================
        # 6. COMMERCIAL ORIENTATION MUST BE RECOGNIZED
        # ====================================================

        commercial = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Where are farmers most "
                        "commercially oriented?"
                    )
            },
        )

        assert (
            commercial.status_code
            == 200
        )

        commercial_payload = (
            commercial.json()
        )

        assert (
            commercial_payload["status"]
            == "answered"
        )

        commercial_spec = (
            commercial_payload[
                "question_specification"
            ]
        )

        assert (
            commercial_spec["metric_id"]
            == "median_commercialization_share"
        )

        assert (
            commercial_spec["operation"]
            == "rank"
        )

        assert (
            commercial_spec["group_by"]
            == "state"
        )

        assert (
            commercial_spec["ascending"]
            is False
        )


        # ====================================================
        # 7. YIELD RANKING WORDING MUST MATCH FILTER + DIRECTION
        # ====================================================

        highest_maize = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Which states have the "
                        "highest maize yields?"
                    )
            },
        )

        assert (
            highest_maize.status_code
            == 200
        )

        highest_maize_payload = (
            highest_maize.json()
        )

        assert (
            highest_maize_payload["status"]
            == "answered"
        )

        highest_text = (
            highest_maize_payload[
                "answer_text"
            ].lower()
        )

        assert (
            "for maize"
            in highest_text
        )

        assert (
            "states"
            in highest_text
        )

        assert (
            "highest observed median yields"
            in highest_text
        )

        assert (
            "among crops"
            not in highest_text
        )


        lowest_maize = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Which states have the "
                        "lowest maize yields?"
                    )
            },
        )

        assert (
            lowest_maize.status_code
            == 200
        )

        lowest_maize_payload = (
            lowest_maize.json()
        )

        assert (
            lowest_maize_payload["status"]
            == "answered"
        )

        lowest_maize_spec = (
            lowest_maize_payload[
                "question_specification"
            ]
        )

        assert (
            lowest_maize_spec["ascending"]
            is True
        )

        lowest_text = (
            lowest_maize_payload[
                "answer_text"
            ].lower()
        )

        assert (
            "lowest observed median yields"
            in lowest_text
        )

        assert (
            "highest observed median yields"
            not in lowest_text
        )


        # ====================================================
        # 8. PRODUCTION POTENTIAL MUST REFRAME TO OBSERVED YIELD
        # ====================================================

        potential = client.post(
            "/v1/questions",
            json={
                "question":
                    (
                        "Which crops appear to have "
                        "the strongest production potential?"
                    )
            },
        )

        assert (
            potential.status_code
            == 200
        )

        potential_payload = (
            potential.json()
        )

        assert (
            potential_payload["status"]
            == "reframe_required"
        )

        assert (
            potential_payload["reframe"]
            is not None
        )

        reframe_text = (
            (
                potential_payload[
                    "answer_text"
                ]
                + " "
                + potential_payload[
                    "reframe"
                ][
                    "reason"
                ]
                + " "
                + (
                    potential_payload[
                        "reframe"
                    ][
                        "supported_alternative"
                    ]
                    or ""
                )
            )
            .lower()
        )

        assert (
            "potential"
            in reframe_text
        )

        assert (
            "observed"
            in reframe_text
        )

        assert (
            "yield"
            in reframe_text
        )


    print(
        "Pilot low-direction regression: PASSED"
    )

    print(
        "Pilot conversational direction: PASSED"
    )

    print(
        "Pilot flood ranking: PASSED"
    )

    print(
        "Pilot food-security ambiguity: PASSED"
    )

    print(
        "Pilot commercialization language: PASSED"
    )

    print(
        "Pilot yield wording: PASSED"
    )

    print(
        "Pilot production-potential reframe: PASSED"
    )

    print(
        "PILOT ROUTING REGRESSION TEST: PASSED"
    )


if __name__ == "__main__":

    main()
