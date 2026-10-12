"""Refresh one external source and adopt it into a running AgDA API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
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


RELOADABLE_STATUSES = {
    "updated",
    "unchanged",
}

NO_RELOAD_STATUSES = {
    "no_data",
    "no_data_retained",
    "failed_retained",
    "failed_no_snapshot",
}

EXIT_SUCCESS = 0
EXIT_REFRESH_FAILURE = 2
EXIT_NO_DATA = 3
EXIT_INVARIANT = 4
EXIT_ADOPTION_FAILURE = 5

MAX_RELOAD_RESPONSE_BYTES = 64 * 1024


class OrchestrationError(RuntimeError):
    """Operational orchestration failure."""


class AdoptionInvariantError(RuntimeError):
    """Runtime adoption violated the refresh contract."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh an external source and, "
            "when safe, ask a running AgDA API "
            "to adopt the persisted snapshot."
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
        "--reload-url",
        default=None,
        help=(
            "Full internal reload endpoint URL. "
            "Defaults to "
            "AGDA_OPERATIONS_RELOAD_URL."
        ),
    )

    parser.add_argument(
        "--reload-timeout-seconds",
        type=float,
        default=20.0,
    )

    return parser


def _compact_json(
    payload: dict[str, Any],
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )


def _emit(
    payload: dict[str, Any],
) -> None:
    print(
        _compact_json(
            payload
        )
    )


def _operations_token() -> str:
    token = (
        os.getenv(
            "AGDA_OPERATIONS_TOKEN"
        )
        or ""
    ).strip()

    if not token:
        raise OrchestrationError(
            "AGDA_OPERATIONS_TOKEN "
            "is not configured."
        )

    return token


def _reload_url(
    cli_value: str | None,
) -> str:
    value = (
        cli_value
        or os.getenv(
            "AGDA_OPERATIONS_RELOAD_URL"
        )
        or ""
    ).strip()

    if not value:
        raise OrchestrationError(
            "Reload URL is not configured."
        )

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
        raise OrchestrationError(
            "Reload URL must be an "
            "absolute HTTP(S) URL."
        )

    return value


def _run_refresh(
    source: str,
    refresh_arguments: list[str],
) -> tuple[int, dict[str, Any]]:
    command = [
        sys.executable,
        str(
            Path(__file__).with_name(
                "refresh_external_source.py"
            )
        ),
        source,
        *refresh_arguments,
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = (
        completed.stdout
        or ""
    ).strip()

    if not stdout:
        raise OrchestrationError(
            "Refresh command returned "
            "no JSON output."
        )

    try:
        payload = json.loads(
            stdout
        )
    except json.JSONDecodeError as error:
        raise OrchestrationError(
            "Refresh command returned "
            "invalid JSON."
        ) from error

    if not isinstance(
        payload,
        dict,
    ):
        raise OrchestrationError(
            "Refresh command JSON "
            "must be an object."
        )

    return (
        completed.returncode,
        payload,
    )


def _read_response(
    response,
) -> bytes:
    body = response.read(
        MAX_RELOAD_RESPONSE_BYTES + 1
    )

    if (
        len(body)
        > MAX_RELOAD_RESPONSE_BYTES
    ):
        raise OrchestrationError(
            "Reload response exceeded "
            "the allowed size."
        )

    return body


def _post_reload(
    *,
    url: str,
    source: str,
    token: str,
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

            body = _read_response(
                response
            )

    except HTTPError as error:
        status_code = error.code

        body = error.read(
            MAX_RELOAD_RESPONSE_BYTES
            + 1
        )

        if (
            len(body)
            > MAX_RELOAD_RESPONSE_BYTES
        ):
            raise OrchestrationError(
                "Reload error response "
                "exceeded the allowed size."
            ) from error

    except URLError as error:
        raise OrchestrationError(
            "Runtime reload request failed."
        ) from error

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
        raise OrchestrationError(
            "Runtime reload returned "
            "invalid JSON."
        ) from error

    if not isinstance(
        payload,
        dict,
    ):
        raise OrchestrationError(
            "Runtime reload JSON "
            "must be an object."
        )

    return (
        status_code,
        payload,
    )


def _validate_adoption(
    *,
    source: str,
    refresh: dict[str, Any],
    reload_payload: dict[str, Any],
) -> None:
    expected_snapshot_id = (
        refresh.get(
            "active_snapshot_id"
        )
    )

    if (
        not isinstance(
            expected_snapshot_id,
            str,
        )
        or len(
            expected_snapshot_id
        )
        != 64
    ):
        raise AdoptionInvariantError(
            "Refresh result has no "
            "valid active snapshot ID."
        )

    if (
        reload_payload.get(
            "status"
        )
        != "reloaded"
    ):
        raise OrchestrationError(
            "Runtime did not report "
            "successful adoption."
        )

    if (
        reload_payload.get(
            "source"
        )
        != source
    ):
        raise AdoptionInvariantError(
            "Reload response source "
            "does not match refresh source."
        )

    source_state = (
        reload_payload.get(
            source
        )
    )

    if not isinstance(
        source_state,
        dict,
    ):
        raise AdoptionInvariantError(
            "Reload response is missing "
            "the requested source state."
        )

    if (
        source_state.get(
            "restore_status"
        )
        != "loaded"
    ):
        raise OrchestrationError(
            "Runtime did not load "
            "the requested snapshot."
        )

    if (
        source_state.get(
            "after_snapshot_id"
        )
        != expected_snapshot_id
    ):
        raise AdoptionInvariantError(
            "Runtime adopted a snapshot "
            "different from the refreshed "
            "active snapshot."
        )


def main(
    argv: list[str] | None = None,
) -> int:
    parser = _parser()

    args, refresh_arguments = (
        parser.parse_known_args(
            argv
        )
    )

    if (
        args.reload_timeout_seconds
        <= 0
    ):
        parser.error(
            "--reload-timeout-seconds "
            "must be greater than zero."
        )

    # Preflight privileged adoption config
    # BEFORE changing the snapshot store.
    try:
        token = _operations_token()

        reload_url = _reload_url(
            args.reload_url
        )

    except OrchestrationError as error:
        _emit(
            {
                "status":
                    "configuration_error",
                "source":
                    args.source,
                "refresh":
                    None,
                "reload":
                    None,
                "error_type":
                    type(error).__name__,
                "error_message":
                    str(error),
            }
        )

        return (
            EXIT_ADOPTION_FAILURE
        )

    try:
        (
            refresh_exit,
            refresh_payload,
        ) = _run_refresh(
            args.source,
            refresh_arguments,
        )

    except OrchestrationError as error:
        _emit(
            {
                "status":
                    "refresh_command_error",
                "source":
                    args.source,
                "refresh":
                    None,
                "reload":
                    None,
                "error_type":
                    type(error).__name__,
                "error_message":
                    str(error),
            }
        )

        return (
            EXIT_REFRESH_FAILURE
        )

    refresh_status = (
        refresh_payload.get(
            "status"
        )
    )

    if refresh_exit != 0:
        _emit(
            {
                "status":
                    "refresh_not_adopted",
                "source":
                    args.source,
                "refresh":
                    refresh_payload,
                "reload":
                    None,
            }
        )

        return refresh_exit

    if (
        refresh_status
        not in RELOADABLE_STATUSES
    ):
        _emit(
            {
                "status":
                    "refresh_contract_error",
                "source":
                    args.source,
                "refresh":
                    refresh_payload,
                "reload":
                    None,
                "error_type":
                    "AdoptionInvariantError",
                "error_message":
                    (
                        "Zero-exit refresh "
                        "returned a non-reloadable "
                        "status."
                    ),
            }
        )

        return EXIT_INVARIANT

    try:
        (
            reload_status_code,
            reload_payload,
        ) = _post_reload(
            url=reload_url,
            source=args.source,
            token=token,
            timeout_seconds=
                args.reload_timeout_seconds,
        )

        if (
            reload_status_code
            != 200
        ):
            raise OrchestrationError(
                "Runtime reload returned "
                f"HTTP {reload_status_code}."
            )

        _validate_adoption(
            source=args.source,
            refresh=refresh_payload,
            reload_payload=
                reload_payload,
        )

    except AdoptionInvariantError as error:
        _emit(
            {
                "status":
                    "adoption_invariant_error",
                "source":
                    args.source,
                "refresh":
                    refresh_payload,
                "reload":
                    (
                        reload_payload
                        if "reload_payload"
                        in locals()
                        else None
                    ),
                "error_type":
                    type(error).__name__,
                "error_message":
                    str(error),
            }
        )

        return EXIT_INVARIANT

    except OrchestrationError as error:
        _emit(
            {
                "status":
                    "adoption_failed",
                "source":
                    args.source,
                "refresh":
                    refresh_payload,
                "reload":
                    (
                        reload_payload
                        if "reload_payload"
                        in locals()
                        else None
                    ),
                "error_type":
                    type(error).__name__,
                "error_message":
                    str(error),
            }
        )

        return (
            EXIT_ADOPTION_FAILURE
        )

    _emit(
        {
            "status":
                "refreshed_and_adopted",
            "source":
                args.source,
            "refresh":
                refresh_payload,
            "reload":
                reload_payload,
        }
    )

    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
