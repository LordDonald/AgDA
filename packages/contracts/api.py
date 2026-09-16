from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


# ============================================================
# QUESTION REQUEST
# ============================================================

class QuestionRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(
        min_length=1,
        max_length=2000,
    )

    conversation_id: str | None = Field(
        default=None,
        max_length=128,
    )

    user_id: str | None = Field(
        default=None,
        max_length=128,
    )

    max_rank_items: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    include_visualization: bool = True

    locale: str = Field(
        default="en-NG",
        min_length=2,
        max_length=20,
        pattern=(
            r"^[A-Za-z]{2,3}"
            r"(?:-[A-Za-z0-9]{2,8})*$"
        ),
    )


    @field_validator(
        "question"
    )
    @classmethod
    def validate_question(
        cls,
        value: str,
    ) -> str:

        if not value:

            raise ValueError(
                "question cannot be blank."
            )

        return value


    @field_validator(
        "conversation_id",
        "user_id",
    )
    @classmethod
    def normalize_optional_identifier(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:

            return None


        if not value:

            return None


        return value

    @field_validator(
        "locale"
    )
    @classmethod
    def normalize_locale(
        cls,
        value: str,
    ) -> str:

        return value.strip()