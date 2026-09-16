from __future__ import annotations

from starlette.responses import (
    JSONResponse,
)

from apps.api.app.core.observability import (
    get_request_id,
)


class RequestBodyTooLarge(
    Exception
):
    pass


class RequestSizeLimitMiddleware:

    def __init__(
        self,
        app,
        max_bytes: int,
    ):

        if max_bytes < 1:

            raise ValueError(
                "max_bytes must be >= 1."
            )


        self.app = app

        self.max_bytes = (
            max_bytes
        )


    async def __call__(
        self,
        scope,
        receive,
        send,
    ):

        if (
            scope["type"]
            != "http"
        ):

            await self.app(
                scope,
                receive,
                send,
            )

            return


        # ----------------------------------------------------
        # Reject oversized requests immediately when
        # Content-Length is available.
        # ----------------------------------------------------

        headers = dict(
            scope.get(
                "headers",
                []
            )
        )


        content_length = (
            headers.get(
                b"content-length"
            )
        )


        if content_length is not None:

            try:

                declared_size = int(
                    content_length
                )

            except ValueError:

                declared_size = None


            if (
                declared_size
                is not None
                and declared_size
                > self.max_bytes
            ):

                await self._send_too_large(
                    scope,
                    receive,
                    send,
                )

                return


        # ----------------------------------------------------
        # Also enforce the limit while reading the stream.
        # This protects requests without Content-Length.
        # ----------------------------------------------------

        bytes_received = 0


        async def limited_receive():

            nonlocal bytes_received


            message = (
                await receive()
            )


            if (
                message["type"]
                == "http.request"
            ):

                body = (
                    message.get(
                        "body",
                        b"",
                    )
                )


                bytes_received += len(
                    body
                )


                if (
                    bytes_received
                    > self.max_bytes
                ):

                    raise (
                        RequestBodyTooLarge()
                    )


            return message


        try:

            await self.app(
                scope,
                limited_receive,
                send,
            )


        except RequestBodyTooLarge:

            await self._send_too_large(
                scope,
                receive,
                send,
            )


    async def _send_too_large(
        self,
        scope,
        receive,
        send,
    ):

        request_id = (
            get_request_id()
        )


        response = JSONResponse(
            status_code=413,

            content={
                "status":
                    "request_too_large",

                "message":
                    (
                        "The request body exceeds "
                        "the maximum allowed size."
                    ),

                "request_id":
                    request_id,
            },

            headers=(
                {
                    "X-Request-ID":
                        request_id
                }
                if request_id
                else {}
            ),
        )


        await response(
            scope,
            receive,
            send,
        )