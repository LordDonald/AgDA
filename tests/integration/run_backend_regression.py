from __future__ import annotations

import subprocess
import sys

from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)


INTEGRATION_DIR = (
    ROOT_DIR
    / "tests"
    / "integration"
)


# ============================================================
# BACKEND REGRESSION SUITE
# ============================================================

TEST_FILES = [
    "test_release_loader.py",
    "test_metric_registry.py",
    "test_analytics_executor.py",
    "test_question_router.py",
    "test_question_pipeline.py",
    "test_answer_service.py",
    "test_api.py",
    "test_clarification_followups.py",
    "test_conversation_context.py",
    "test_redis_conversation_store.py",
    "test_api_conversation.py",
    "test_product_analytics.py",
    "test_product_analytics_persistence.py",
    "test_product_feedback.py",
    "test_internal_analytics_api.py",
    "test_internal_external_sources_api.py",
    "test_pilot_routing_regressions.py",
    "test_external_source_contract.py",
    "test_external_source_registry.py",
    "test_external_source_catalog.py",
    "test_external_source_api.py",
    "test_external_metric_registry.py",
    "test_external_question_router.py",
    "test_external_metric_executor.py",
    "test_external_question_api.py",
    "test_external_refresh.py",
    "test_external_refresh_command.py",
    "test_fews_market_price_adapter.py",
    "test_fews_market_price_client.py",
    "test_fews_snapshot_store.py",
    "test_fews_snapshot_runtime.py",
    "test_fews_ingestion_command.py",
    "test_market_prices_api.py",
    "test_weather_forecast_client.py",
    "test_weather_snapshot_store.py",
    "test_weather_snapshot_runtime.py",
    "test_weather_forecast_api.py",
    "test_weather_ingestion_command.py",
    "test_api_observability.py",
    "test_api_health_config.py",
    "test_api_limits.py",
    "test_context_references.py",
    "test_extension_yield_comparison.py",
    "test_methodological_followups.py",
]


def main():

    print(
        "\n========================================"
    )

    print(
        "AgDA BACKEND HARDENING REGRESSION"
    )

    print(
        "========================================"
    )


    passed = []


    for index, filename in enumerate(
        TEST_FILES,
        start=1,
    ):

        test_path = (
            INTEGRATION_DIR
            / filename
        )


        if not test_path.exists():

            raise FileNotFoundError(
                f"Missing regression test: "
                f"{test_path}"
            )


        print(
            "\n----------------------------------------"
        )

        print(
            f"[{index}/{len(TEST_FILES)}] "
            f"{filename}"
        )

        print(
            "----------------------------------------"
        )


        result = subprocess.run(
            [
                sys.executable,
                str(test_path),
            ],

            cwd=
                ROOT_DIR,

            check=False,
        )


        if result.returncode != 0:

            print(
                "\nBACKEND REGRESSION: FAILED"
            )

            print(
                "Failed test:",
                filename
            )

            print(
                "Exit code:",
                result.returncode
            )


            raise SystemExit(
                result.returncode
            )


        passed.append(
            filename
        )


    print(
        "\n========================================"
    )

    print(
        "BACKEND REGRESSION SUMMARY"
    )

    print(
        "========================================"
    )


    for filename in passed:

        print(
            "PASS:",
            filename
        )


    print(
        "\nTests passed:",
        len(passed),
        "/",
        len(TEST_FILES),
    )


    print(
        "\nBACKEND HARDENING REGRESSION: PASSED"
    )


if __name__ == "__main__":
    main()
