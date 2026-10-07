from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


FeedbackRating = Literal[
    "helpful",
    "not_helpful",
]

FeedbackReason = Literal[
    "incorrect",
    "unclear",
    "not_relevant",
    "insufficient_evidence",
    "other",
]


class FeedbackRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    request_id: str = Field(
        min_length=1,
        max_length=128,
    )

    rating: FeedbackRating

    reason_code: FeedbackReason | None = None


    @model_validator(
        mode="after"
    )
    def validate_reason(
        self,
    ) -> "FeedbackRequest":

        if (
            self.rating == "helpful"
            and self.reason_code is not None
        ):

            raise ValueError(
                "reason_code must be null "
                "when rating is helpful."
            )

        return self


class FeedbackResponse(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    status: Literal["saved"]

    request_id: str

    rating: FeedbackRating

    reason_code: FeedbackReason | None = None
