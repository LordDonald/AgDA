from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


# ============================================================
# ENUMS
# ============================================================

class Operation(
    str,
    Enum,
):

    VALUE = "value"
    GROUP = "group"
    RANK = "rank"


class InterpretationStatus(
    str,
    Enum,
):

    INTERPRETED = "interpreted"

    CONTEXTUAL_INFO = (
        "contextual_info"
    )

    NEEDS_CLARIFICATION = (
        "needs_clarification"
    )

    REFRAME_REQUIRED = (
        "reframe_required"
    )

    UNSUPPORTED = "unsupported"


# ============================================================
# QUESTION SPECIFICATION
# ============================================================

class QuestionSpecification(
    BaseModel,
):

    model_config = ConfigDict(
        extra="forbid"
    )

    metric_id: str

    operation: Operation

    filters: dict[
        str,
        Any
    ] = Field(
        default_factory=dict
    )

    group_by: str | None = None

    ascending: bool = False

    top_n: int | None = None

    minimum_records: int | None = None

    metric_version: str


    @model_validator(
        mode="after"
    )
    def validate_operation_fields(
        self,
    ):

        if (
            self.operation
            in {
                Operation.GROUP,
                Operation.RANK,
            }
            and self.group_by is None
        ):

            raise ValueError(
                f"{self.operation.value} "
                "requires group_by."
            )


        if (
            self.top_n is not None
            and (
                self.top_n < 1
                or self.top_n > 50
            )
        ):

            raise ValueError(
                "top_n must be between "
                "1 and 50."
            )


        if (
            self.minimum_records
            is not None
            and self.minimum_records < 1
        ):

            raise ValueError(
                "minimum_records must "
                "be >= 1."
            )


        return self


# ============================================================
# ROUTER INTERPRETATION
# ============================================================

class QuestionInterpretation(
    BaseModel,
):

    model_config = ConfigDict(
        extra="forbid"
    )

    question: str

    normalized_question: str

    status: InterpretationStatus

    metric_id: str | None = None

    operation: Operation | None = None

    group_by: str | None = None

    filters: dict[
        str,
        Any
    ] = Field(
        default_factory=dict
    )

    entities: dict[
        str,
        list[str]
    ] = Field(
        default_factory=dict
    )

    metric_candidates: list[
        str
    ] = Field(
        default_factory=list
    )

    support_flags: list[
        str
    ] = Field(
        default_factory=list
    )

    reason: str | None = None

    suggested_reframe: str | None = None

    question_specification: QuestionSpecification | None = None