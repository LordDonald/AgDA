from fastapi import (
    APIRouter,
    HTTPException,
)

from apps.api.app.core.runtime import (
    runtime,
)


router = APIRouter(
    prefix="/v1",
    tags=["metrics"],
)


@router.get(
    "/metrics"
)
def list_metrics():

    if (
        not runtime.ready
        or runtime.registry is None
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "AgDA analytical runtime "
                "is not ready."
            ),
        )


    dataframe = (
        runtime.registry
        .to_dataframe()
    )


    public_columns = [
        "metric_id",
        "display_name",
        "question_family",
        "unit",
        "claim_type",
        "causal_interpretation_allowed",
        "headline_safe",
        "caution",
    ]


    records = (
        dataframe[
            public_columns
        ]
        .where(
            dataframe[
                public_columns
            ].notna(),
            None,
        )
        .to_dict(
            orient="records"
        )
    )


    return {
        "data_version":
            runtime.release_info[
                "data_version"
            ],

        "metric_version":
            runtime.release_info[
                "metric_version"
            ],

        "count":
            len(records),

        "metrics":
            records,
    }