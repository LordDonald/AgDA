from __future__ import annotations

from contextlib import (
    asynccontextmanager,
)

from fastapi import (
    FastAPI,
    Request,
)

from fastapi.responses import (
    JSONResponse,
)

from starlette.middleware.trustedhost import (
    TrustedHostMiddleware,
)

from apps.api.app.core.runtime import (
    runtime,
)

from apps.api.app.routes.health import (
    router as health_router,
)

from apps.api.app.routes.questions import (
    router as questions_router,
)

from apps.api.app.routes.entities import (
    router as entities_router,
)

from apps.api.app.routes.metrics import (
    router as metrics_router,
)

from apps.api.app.core.observability import (
    RequestContextMiddleware,
    get_request_id,
)

from apps.api.app.core.settings import (
    settings,
)

from apps.api.app.core.limits import (
    RequestSizeLimitMiddleware,
)

import logging


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):

    runtime.start()

    yield

    runtime.stop()

logging.basicConfig(
    level=getattr(
        logging,
        settings.log_level,
    ),

    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    ),
)


logging.getLogger(
    "agda.api"
).setLevel(
    getattr(
        logging,
        settings.log_level,
    )
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=
        settings.service_name,

    version=
        settings.service_version,

    description=(
        "Evidence-backed agricultural "
        "question-answering API."
    ),

    lifespan=
        lifespan,

    docs_url=(
        "/docs"
        if settings.docs_enabled
        else None
    ),

    redoc_url=(
        "/redoc"
        if settings.docs_enabled
        else None
    ),

    openapi_url=(
        "/openapi.json"
        if settings.docs_enabled
        else None
    ),
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=
        list(
            settings.allowed_hosts
        ),
)


app.add_middleware(
    RequestSizeLimitMiddleware,
    max_bytes=
        settings.max_request_bytes,
)


app.add_middleware(
    RequestContextMiddleware
)

app.include_router(
    health_router
)

app.include_router(
    questions_router
)

app.include_router(
    metrics_router
)

app.include_router(
    entities_router
)


@app.exception_handler(
    Exception
)
async def unhandled_exception_handler(
    request: Request,
    error: Exception,
):

    request_id = (
        getattr(
            request.state,
            "request_id",
            None,
        )
        or
        get_request_id()
    )


    return JSONResponse(
        status_code=500,

        content={
            "status":
                "system_error",

            "message":
                (
                    "AgDA encountered an "
                    "unexpected server error."
                ),

            "request_id":
                request_id,
        },

        headers={
            "X-Request-ID":
                request_id
                or "unavailable"
        },
    )


@app.get("/")
def root():

    return {
        "service":
            settings.service_name,

        "version":
            settings.service_version,

        "environment":
            settings.environment,

        "status":
            "online",

        "docs":
            (
                "/docs"
                if settings.docs_enabled
                else None
            ),

        "liveness":
            "/v1/live",

        "readiness":
            "/v1/ready",

        "health":
            "/v1/health",
    }