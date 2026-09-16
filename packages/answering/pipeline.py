from __future__ import annotations

from dataclasses import dataclass

from packages.analytics.executor import (
    ScalarMetricResult,
    TableMetricResult,
)

from packages.analytics.question_executor import (
    QuestionSpecificationExecutor,
)

from packages.contracts.question import (
    InterpretationStatus,
    QuestionInterpretation,
)

from packages.question_router.router import (
    QuestionRouter,
)

from packages.question_router.conversation import (
    ConversationContext,
    ContextualQuestionResolver,
)


# ============================================================
# PIPELINE RESULT
# ============================================================

@dataclass(frozen=True)
class QuestionPipelineResult:

    question: str

    status: str

    interpretation: QuestionInterpretation

    result: ScalarMetricResult | TableMetricResult | None


# ============================================================
# QUESTION PIPELINE
# ============================================================

class QuestionPipeline:

    def __init__(
        self,
        router: QuestionRouter,
        specification_executor: QuestionSpecificationExecutor,
        contextual_resolver: ContextualQuestionResolver | None = None,
    ):

        self.router = router

        self.specification_executor = (
            specification_executor
        )

        self.contextual_resolver = (
            contextual_resolver
        )


    def run(
        self,
        question: str,
        context: ConversationContext | None = None,
    ) -> QuestionPipelineResult:

        interpretation = None


        if (
            self.contextual_resolver
            is not None
            and context is not None
        ):

            interpretation = (
                self.contextual_resolver.resolve(
                    question=
                        question,

                    context=
                        context,
                )
            )


        if interpretation is None:

            interpretation = (
                self.router.interpret(
                    question
                )
            )


        # ----------------------------------------------------
        # Do not execute questions that were not approved
        # for deterministic analytics.
        # ----------------------------------------------------

        if (
            interpretation.status
            != InterpretationStatus.INTERPRETED
        ):

            return QuestionPipelineResult(
                question=
                    question,

                status=
                    interpretation.status.value,

                interpretation=
                    interpretation,

                result=
                    None,
            )


        specification = (
            interpretation
            .question_specification
        )


        if specification is None:

            raise RuntimeError(
                "Interpreted question did not produce "
                "a QuestionSpecification."
            )


        result = (
            self.specification_executor.execute(
                specification
            )
        )


        return QuestionPipelineResult(
            question=
                question,

            status=
                "answered",

            interpretation=
                interpretation,

            result=
                result,
        )