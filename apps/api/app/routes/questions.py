from uuid import uuid4

from fastapi import (
    APIRouter,
    HTTPException,
)

from packages.contracts.answer import (
    AgDAAnswer,
)

from packages.contracts.api import (
    QuestionRequest,
)

from apps.api.app.core.runtime import (
    runtime,
)

from packages.contracts.question import (
    InterpretationStatus,
)

router = APIRouter(
    prefix="/v1",
    tags=["questions"],
)


@router.post(
    "/questions",
    response_model=AgDAAnswer,
)
def ask_question(
    request: QuestionRequest,
):

    if (
        not runtime.ready
        or runtime.answer_service
        is None
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "AgDA analytical runtime "
                "is not ready."
            ),
        )


    try:

        conversation_id = (
            request.conversation_id
            or
            f"conv_{uuid4().hex}"
        )


        context = (
            runtime
            .conversation_store
            .get(
                conversation_id
            )
            if runtime.conversation_store
            is not None
            else None
        )


        answer, pipeline_result = (
            runtime
            .answer_service
            .answer_with_pipeline_result(
                question=
                    request.question,

                max_rank_items=
                    request.max_rank_items,

                context=
                    context,
            )
        )


        interpretation = (
            pipeline_result
            .interpretation
        )


        if (
            runtime.conversation_store
            is not None
            and interpretation.status
            == InterpretationStatus.INTERPRETED
            and interpretation
            .question_specification
            is not None
            ):

            runtime.conversation_store.put(
                conversation_id=
                    conversation_id,

                interpretation=
                    interpretation,
            )


        answer = answer.model_copy(
            update={
                "conversation_id":
                    conversation_id
            }
        )


        # Client may explicitly suppress the visual.
        if (
            request.include_visualization
            is False
        ):

            answer = answer.model_copy(
                update={
                    "visualization":
                        None
                }
            )


        return answer


    except (
        KeyError,
        ValueError,
    ) as error:

        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error