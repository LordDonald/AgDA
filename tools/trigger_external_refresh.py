"""Trigger one authenticated external refresh on the API service."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.parse import urlparse
from urllib.request import (
    Request,
    urlopen,
)


MAX_RESPONSE_BYTES = 64 * 1024


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Trigger one AgDA external-source "
            "refresh through the privileged "
            "internal API."
        )
    )

    parser.add_argument(
        "source",
        choices=(
            "fews",
            "weather",
        ),
    )

    parser.add_argument(
        "--refresh-url",
        default=None,
    )

    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=90.0,
    )

    return parser


def _emit(
    payload: dict[str, Any],
) -> None:
    print(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _token() -> str:
    token = (
        os.getenv(
            "AGDA_OPERATIONS_TOKEN"
        )
        or ""
    ).strip()

    if not token:
        raise ValueError(
            "AGDA_OPERATIONS_TOKEN "
            "is not configured."
        )

    return token


def _url(
    cli_value: str | None,
) -> str:
    value = (
        cli_value
        or os.getenv(
            "AGDA_OPERATIONS_REFRESH_URL"
        )
        or ""
    ).strip()

    parsed = urlparse(
        value
    )

    if (
        parsed.scheme
        not in {
            "http",
            "https",
        }
        or not parsed.netloc
    ):
        raise ValueError(
            "Refresh URL must be an "
            "absolute HTTP(S) URL."
        )

    return value


def _request(
    *,
    url: str,
    token: str,
    source: str,
    timeout_seconds: float,
) -> tuple[int, dict[str, Any]]:
    request = Request(
        url,
        data=json.dumps(
            {
                "source": source,
            }
        ).encode(
            "utf-8"
        ),
        headers={
            "Content-Type":
                "application/json",
            "X-AgDA-Operations-Token":
                token,
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            status_code = (
                response.getcode()
            )

            body = response.read(
                MAX_RESPONSE_BYTES + 1
            )

    except HTTPError as error:
        status_code = error.code

        body = error.read(
            MAX_RESPONSE_BYTES + 1
        )

    except URLError as error:
        raise RuntimeError(
            "Refresh request failed."
        ) from error

    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError(
            "Refresh response exceeded "
            "the allowed size."
        )

    try:
        payload = json.loads(
            body.decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeError(
            "Refresh endpoint returned "
            "invalid JSON."
        ) from error

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Refresh endpoint JSON "
            "must be an object."
        )

    return (
        status_code,
        payload,
    )


def main(
    argv: list[str] | None = None,
) -> int:
    args = _parser().parse_args(
        argv
    )

    if args.timeout_seconds <= 0:
        raise SystemExit(
            "--timeout-seconds must "
            "be greater than zero."
        )

    try:
        token = _token()

        url = _url(
            args.refresh_url
        )

        status_code, payload = (
            _request(
                url=url,
                token=token,
                source=args.source,
                timeout_seconds=
                    args.timeout_seconds,
            )
        )

    except (
        ValueError,
        RuntimeError,
    ) as error:
        _emit(
            {
                "status":
                    "trigger_error",
                "source":
                    args.source,
                "error_type":
                    type(error).__name__,
                "error_message":
                    str(error),
            }
        )

        return 5

    _emit(
        payload
    )

    status = payload.get(
        "status"
    )

    if (
        status_code == 200
        and status
        == "refreshed_and_adopted"
    ):
        return 0

    refresh = payload.get(
        "refresh"
    )

    refresh_status = (
        refresh.get(
            "status"
        )
        if isinstance(
            refresh,
            dict,
        )
        else None
    )

    if refresh_status in {
        "no_data",
        "no_data_retained",
    }:
        return 3

    if refresh_status in {
        "failed_retained",
        "failed_no_snapshot",
    }:
        return 2

    return 5


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
