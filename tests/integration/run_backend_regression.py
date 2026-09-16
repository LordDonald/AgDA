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
    "test_api_conversation.py",
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