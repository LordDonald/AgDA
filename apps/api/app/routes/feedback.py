from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    HTTPException,
)

from apps.api.app.core.product_feedback import (
    save_feedback,
)

from apps.api.app.core.settings import (
    settings,
)

from packages.contracts.feedback import (
    FeedbackRequest,
    FeedbackResponse,
)


logger = logging.getLogger(
    "agda.feedback"
)


router = APIRouter(
    prefix="/v1",
    tags=["feedback"],
)


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
)
def submit_feedback(
    request: FeedbackRequest,
) -> FeedbackResponse:

    database_url = (
        settings.analytics_database_url
    )

    if not database_url:

        raise HTTPException(
            status_code=503,
            detail=(
                "Feedback storage is "
                "currently unavailable."
            ),
        )

    try:

        save_feedback(
            database_url=
                database_url,

            request_id=
                request.request_id,

            rating=
                request.rating,

            reason_code=
                request.reason_code,
        )

    except LookupError as error:

        raise HTTPException(
            status_code=404,
            detail=(
                "The AgDA answer associated "
                "with this feedback could not "
                "be found."
            ),
        ) from error

    except Exception as error:

        logger.warning(
            "Feedback persistence failed (%s).",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "AgDA could not save "
                "feedback right now."
            ),
        ) from error

    return FeedbackResponse(
        status=
            "saved",

        request_id=
            request.request_id,

        rating=
            request.rating,

        reason_code=
            request.reason_code,
    )
