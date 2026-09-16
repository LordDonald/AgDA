from __future__ import annotations

from packages.analytics.executor import (
    AnalyticsExecutor,
    ScalarMetricResult,
    TableMetricResult,
)

from packages.analytics.registry import (
    MetricRegistry,
)

from packages.contracts.question import (
    QuestionSpecification,
)


# ============================================================
# QUESTION SPECIFICATION EXECUTOR
# ============================================================

class QuestionSpecificationExecutor:
    """
    Controlled bridge between a validated
    QuestionSpecification and the deterministic
    AnalyticsExecutor.
    """

    def __init__(
        self,
        executor: AnalyticsExecutor,
        registry: MetricRegistry,
        metric_version: str,
    ):

        self.executor = executor
        self.registry = registry

        self.metric_version = (
            metric_version
        )


    # --------------------------------------------------------
    # Validate server-side analytical contract
    # --------------------------------------------------------

    def validate(
        self,
        specification:
            QuestionSpecification,
    ) -> None:

        # Metric must exist in authoritative registry
        if not self.registry.contains(
            specification.metric_id
        ):

            raise ValueError(
                f"Unknown metric_id: "
                f"{specification.metric_id}"
            )


        # Question Specification must target the
        # metric version loaded with this release.
        if (
            specification.metric_version
            != self.metric_version
        ):

            raise ValueError(
                "Question Specification metric_version "
                "does not match the loaded release."
            )


        # Special crop-grower scalar requirement
        if (
            specification.metric_id
            == "crop_grower_share"
            and specification.operation.value
            == "value"
            and "crop"
            not in specification.filters
        ):

            raise ValueError(
                "crop_grower_share value operation "
                "requires a crop filter."
            )


    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    def execute(
        self,
        specification:
            QuestionSpecification,
    ) -> (
        ScalarMetricResult
        | TableMetricResult
    ):

        self.validate(
            specification
        )


        return self.executor.execute(
            metric_id=
                specification.metric_id,

            operation=
                specification.operation.value,

            filters=
                specification.filters,

            group_by=
                specification.group_by,

            ascending=
                specification.ascending,

            top_n=
                specification.top_n,

            minimum_records=
                specification.minimum_records,
        )