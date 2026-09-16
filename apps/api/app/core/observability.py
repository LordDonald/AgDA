from __future__ import annotations

import re
import json
import logging
import time

from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from starlette.requests import (
    Request,
)

from starlette.responses import (
    JSONResponse,
)


# ============================================================
# REQUEST CONTEXT
# ============================================================

request_id_context: ContextVar[
    str | None
] = ContextVar(
    "request_id",
    default=None,
)


def get_request_id() -> str | None:
    return request_id_context.get()


REQUEST_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9]"
    r"[A-Za-z0-9._-]{0,127}$"
)


def _safe_request_id(
    supplied_request_id:
        str | None,
) -> str:

    if supplied_request_id:

        candidate = (
            supplied_request_id
            .strip()
        )


        if (
            REQUEST_ID_PATTERN
            .fullmatch(
                candidate
            )
        ):

            return candidate


    return (
        f"req_{uuid4().hex}"
    )


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(
    "agda.api"
)


# ============================================================
# REQUEST MIDDLEWARE
# ============================================================

class RequestContextMiddleware(
    BaseHTTPMiddleware
):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):

        supplied_request_id = (
            request.headers.get(
                "X-Request-ID"
            )
        )

        request_id = (
            _safe_request_id(
                supplied_request_id
            )
        )
        

        request.state.request_id = (
            request_id
        )
        
        
        token = (
            request_id_context.set(
                request_id
            )
        )


        started_at = (
            time.perf_counter()
        )


        try:

            response = (
                await call_next(
                    request
                )
            )


            duration_ms = round(
                (
                    time.perf_counter()
                    - started_at
                )
                * 1000,
                2,
            )


            response.headers[
                "X-Request-ID"
            ] = request_id


            logger.info(
                json.dumps(
                    {
                        "event":
                            "http_request",

                        "request_id":
                            request_id,

                        "method":
                            request.method,

                        "path":
                            request.url.path,

                        "status_code":
                            response.status_code,

                        "duration_ms":
                            duration_ms,
                    }
                )
            )


            return response


        except Exception:

            duration_ms = round(
                (
                    time.perf_counter()
                    - started_at
                )
                * 1000,
                2,
            )


            logger.exception(
                json.dumps(
                    {
                        "event":
                            "http_request_failed",

                        "request_id":
                            request_id,

                        "method":
                            request.method,

                        "path":
                            request.url.path,

                        "duration_ms":
                            duration_ms,
                    }
                )
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
                },
            )


        finally:

            request_id_context.reset(
                token
            )