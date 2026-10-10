from uuid import uuid4

import time

from fastapi import (
    APIRouter,
    BackgroundTasks,
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

from packages.data_sources.external_executor import (
    ExternalExecutionStatus,
)
from packages.data_sources.external_router import (
    ExternalRouteStatus,
)

from apps.api.app.core.observability import (
    get_request_id,
)

from apps.api.app.core.product_analytics import (
    emit_question_event,
    persist_question_event,
)

from apps.api.app.core.settings import (
    settings,
)

router = APIRouter(
    prefix="/v1",
    tags=["questions"],
)


def _external_answer_text(
    external_route,
    execution,
) -> str:

    if execution.reason:
        return execution.reason

    rows = execution.rows

    if (
        execution.metric_id
        == "market_price_ngn_per_kg"
    ):
        if execution.operation == "rank":
            direction = (
                "lowest"
                if any(
                    term
                    in external_route.normalized_question
                    for term in (
                        "lowest",
                        "cheapest",
                        "least expensive",
                        "bottom",
                    )
                )
                else "highest"
            )

            details = "; ".join(
                (
                    f"{row['rank']}. "
                    f"{row['market']}"
                    + (
                        f", {row['admin_1']}"
                        if row.get("admin_1")
                        else ""
                    )
                    + f": {row['value']} {row['unit']}"
                )
                for row in rows
            )

            period = (
                rows[0]["period_date"]
                if rows
                else "the saved period"
            )

            return (
                f"Using the saved FEWS NET market-price "
                f"snapshot for {period}, the {direction} "
                f"observed retail maize prices are: "
                f"{details}. These are historical observed "
                f"prices, not live prices."
            )

        row = rows[0]

        return (
            f"The saved FEWS NET observation for "
            f"{row['market']} on {row['period_date']} "
            f"is {row['value']} {row['unit']} for "
            f"{row['product']}. This is a historical "
            f"observed market price, not a live price."
        )

    if (
        execution.metric_id
        == "forecast_precipitation_mm"
    ):
        row = rows[0]

        if execution.operation == "sum":
            return (
                f"Total forecast precipitation across the "
                f"saved forecast window is {row['total']} "
                f"{row['unit']}. This is forecast weather, "
                f"not measured rainfall."
            )

        if row["rain_expected"]:
            return (
                f"Yes. The saved Open-Meteo/ECMWF forecast "
                f"shows precipitation above 0 mm in "
                f"{row['rainy_hours']} of "
                f"{row['hours_with_values']} forecast hours. "
                f"This is a forecast, not an observation."
            )

        return (
            f"No precipitation above 0 mm appears in the "
            f"{row['hours_with_values']} forecast hours "
            f"with available values. This is a forecast, "
            f"not an observation."
        )

    row = rows[0]

    if (
        execution.metric_id
        == "forecast_temperature_2m_c"
    ):
        measure = "temperature"
    else:
        measure = "relative humidity"

    return (
        f"The saved Open-Meteo/ECMWF forecast {measure} "
        f"ranges from {row['minimum']} {row['unit']} at "
        f"{row['minimum_valid_at']} to "
        f"{row['maximum']} {row['unit']} at "
        f"{row['maximum_valid_at']}. These are forecast "
        f"values, not observations."
    )


def _external_answer(
    question: str,
    external_route,
    execution,
) -> AgDAAnswer:

    source = next(
        (
            item
            for item
            in runtime.external_source_manifest()
            if item["source_id"]
            == execution.source_id
        ),
        None,
    )

    result = {
        "metric_id":
            execution.metric_id,
        "source_id":
            execution.source_id,
        "operation":
            execution.operation,
        "source":
            source,
        "rows": [
            dict(row)
            for row
            in execution.rows
        ],
    }

    if (
        execution.status
        == ExternalExecutionStatus.ANSWERED
    ):
        status = "answered"

    elif (
        execution.status
        == ExternalExecutionStatus.NEEDS_CLARIFICATION
    ):
        status = "needs_clarification"

    else:
        status = "unsupported"

    data_version = (
        source.get("dataset_version")
        if source is not None
        else None
    )

    return AgDAAnswer(
        status=status,
        question=question,
        answer_text=_external_answer_text(
            external_route,
            execution,
        ),
        question_specification=None,
        result=result,
        evidence=None,
        visualization=None,
        data_version=(
            data_version
            or f"external:{execution.source_id}"
        ),
        metric_version=None,
    )


@router.post(
    "/questions",
    response_model=AgDAAnswer,
)
def ask_question(
    request: QuestionRequest,
    background_tasks: BackgroundTasks,
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

    started_at = (
        time.perf_counter()
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


        external_route = (
            runtime
            .external_question_router
            .route(
                request.question
            )
        )


        if (
            external_route.status
            == ExternalRouteStatus.AMBIGUOUS
        ):

            answer = AgDAAnswer(
                status="reframe_required",
                question=request.question,
                answer_text=(
                    external_route.reason
                    or
                    "Ask about one external measure at a time."
                ),
                question_specification=None,
                result=None,
                evidence=None,
                visualization=None,
                data_version="external_mixed",
                metric_version=None,
            )


        elif (
            external_route.status
            == ExternalRouteStatus.ROUTED
        ):

            execution = (
                runtime
                .external_metric_executor
                .execute(
                    external_route,

                    market_snapshot=
                        runtime
                        .market_price_snapshot(),

                    weather_snapshot=
                        runtime
                        .weather_forecast_snapshot(),

                    max_items=
                        request.max_rank_items,
                )
            )

            answer = _external_answer(
                request.question,
                external_route,
                execution,
            )


        else:

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

        processing_duration_ms = round(
            (
                time.perf_counter()
                - started_at
            )
            * 1000,
            2,
        )


        event_payload = emit_question_event(
            request_id=
                get_request_id(),

            environment=
                settings.environment,

            answer=
                answer,

            was_follow_up=
                context is not None,

            question_length=
                len(
                    request.question
                ),

            processing_duration_ms=
                processing_duration_ms,
        )


        if (
            settings.analytics_database_url
            and event_payload is not None
        ):

            background_tasks.add_task(
                persist_question_event,
                database_url=
                    settings.analytics_database_url,
                payload=
                    event_payload,
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