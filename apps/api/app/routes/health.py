from fastapi import (
    APIRouter,
    HTTPException,
)

from apps.api.app.core.runtime import (
    runtime,
)

from apps.api.app.core.settings import (
    settings,
)


router = APIRouter(
    prefix="/v1",
    tags=["health"],
)


# ============================================================
# LIVENESS
# ============================================================

@router.get(
    "/live"
)
def live():

    return {
        "status":
            "alive",

        "service":
            settings.service_name,

        "version":
            settings.service_version,

        "environment":
            settings.environment,
    }


# ============================================================
# READINESS
# ============================================================

@router.get(
    "/ready"
)
def ready():

    health_payload = (
        runtime.health()
    )


    if not health_payload[
        "ready"
    ]:

        raise HTTPException(
            status_code=503,

            detail={
                "status":
                    "not_ready",

                "message":
                    (
                        "AgDA analytical runtime "
                        "is not ready."
                    ),
            },
        )


    return health_payload


# ============================================================
# BACKWARD-COMPATIBLE HEALTH ENDPOINT
# ============================================================

@router.get(
    "/health"
)
def health():

    return ready()