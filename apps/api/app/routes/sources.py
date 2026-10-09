from fastapi import (
    APIRouter,
)

from apps.api.app.core.runtime import (
    runtime,
)


router = APIRouter(
    prefix="/v1",
    tags=["sources"],
)


@router.get(
    "/sources"
)
def sources():

    return {
        "external_sources":
            runtime
            .external_source_health(),

        "sources":
            list(
                runtime
                .external_source_manifest()
            ),
    }
