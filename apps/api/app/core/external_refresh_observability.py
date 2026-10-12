"""Privacy-safe operational events for external refreshes."""

from __future__ import annotations

import json
import logging

from packages.data_sources.external_refresh import (
    ExternalRefreshOutcome,
)


logger = logging.getLogger(
    "agda.external_refresh"
)

# Keep these operational INFO events visible even when the
# application root logger is configured conservatively.
logger.setLevel(
    logging.INFO
)


_EVENT_LEVELS = {
    "agda_external_refresh_success":
        logging.INFO,

    "agda_external_refresh_retained":
        logging.WARNING,

    "agda_external_refresh_adoption_failed":
        logging.ERROR,
}


def emit_external_refresh_event(
    *,
    event: str,
    source: str,
    outcome: ExternalRefreshOutcome,
    core_ready: bool,
    restore_status: str | None = None,
    runtime_snapshot_id: str | None = None,
    changed: bool | None = None,
) -> None:
    """Emit one non-secret operational refresh event.

    Intentionally excluded:
    - authorization tokens
    - request headers
    - filesystem paths
    - provider response bodies
    - refresh error messages
    """

    payload: dict[str, object | None] = {
        "event":
            event,

        "source":
            source,

        "source_id":
            outcome.source_id,

        "refresh_status":
            outcome.status.value,

        "previous_snapshot_id":
            outcome.previous_snapshot_id,

        "active_snapshot_id":
            outcome.active_snapshot_id,

        "record_count":
            outcome.record_count,

        "retrieved_at": (
            outcome.retrieved_at.isoformat()
            if outcome.retrieved_at
            is not None
            else None
        ),

        "core_ready":
            core_ready,
    }

    if outcome.error_type is not None:
        payload[
            "error_type"
        ] = outcome.error_type

    if restore_status is not None:
        payload[
            "restore_status"
        ] = restore_status

    if runtime_snapshot_id is not None:
        payload[
            "runtime_snapshot_id"
        ] = runtime_snapshot_id

    if changed is not None:
        payload[
            "changed"
        ] = changed

    level = _EVENT_LEVELS.get(
        event,
        logging.INFO,
    )

    # Monitoring must never interfere with refresh/adoption.
    try:
        logger.log(
            level,
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    except Exception:
        return
