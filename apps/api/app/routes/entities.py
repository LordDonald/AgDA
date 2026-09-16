from fastapi import (
    APIRouter,
    HTTPException,
)

from apps.api.app.core.runtime import (
    runtime,
)


router = APIRouter(
    prefix="/v1",
    tags=["entities"],
)


ENTITY_CONFIG = {
    "states": {
        "table":
            "state_entity_catalog",

        "candidates": [
            "state_name",
            "state_label",
        ],
    },

    "zones": {
        "table":
            "zone_entity_catalog",

        "candidates": [
            "zone_name",
            "zone_label",
        ],
    },

    "crops": {
        "table":
            "crop_entity_catalog",

        "candidates": [
            "crop_name",
        ],
    },

    "items": {
        "table":
            "item_entity_catalog",

        "candidates": [
            "item_name",
        ],
    },

    "climate-events": {
        "table":
            "climate_event_catalog",

        "candidates": [
            "climate_event",
        ],
    },
}


@router.get(
    "/entities/{entity_type}"
)
def list_entities(
    entity_type: str,
):

    if (
        not runtime.ready
        or runtime.connection is None
    ):

        raise HTTPException(
            status_code=503,
            detail=(
                "AgDA analytical runtime "
                "is not ready."
            ),
        )


    if entity_type not in ENTITY_CONFIG:

        raise HTTPException(
            status_code=404,
            detail=(
                "Unknown entity type. "
                "Supported values: "
                + ", ".join(
                    ENTITY_CONFIG.keys()
                )
            ),
        )


    config = (
        ENTITY_CONFIG[
            entity_type
        ]
    )


    table_name = (
        config[
            "table"
        ]
    )


    columns = (
        runtime.connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE
                table_schema = 'main'
                AND table_name = ?
            ORDER BY ordinal_position
            """,
            [table_name],
        ).fetchdf()[
            "column_name"
        ].tolist()
    )


    value_column = None


    for candidate in (
        config[
            "candidates"
        ]
    ):

        if candidate in columns:

            value_column = candidate

            break


    if value_column is None:

        raise HTTPException(
            status_code=500,
            detail=(
                f"No public label field found "
                f"for {entity_type}."
            ),
        )


    # Table/column names come only from the
    # server-controlled ENTITY_CONFIG above.
    dataframe = (
        runtime.connection.execute(
            f"""
            SELECT DISTINCT
                "{value_column}"
                    AS value
            FROM "{table_name}"
            WHERE
                "{value_column}"
                IS NOT NULL
            ORDER BY value
            """
        ).fetchdf()
    )


    values = (
        dataframe[
            "value"
        ]
        .astype(str)
        .tolist()
    )


    return {
        "data_version":
            runtime.release_info[
                "data_version"
            ],

        "entity_type":
            entity_type,

        "count":
            len(values),

        "values":
            values,
    }