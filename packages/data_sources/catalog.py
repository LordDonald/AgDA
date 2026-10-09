from datetime import (
    datetime,
)
from typing import (
    Any,
)

from packages.data_sources.registry import (
    SourceRegistry,
    SourceState,
)


def _isoformat_or_none(
    value: datetime | None,
) -> str | None:

    if value is None:

        return None

    return value.isoformat()


def source_state_manifest(
    state: SourceState,
) -> dict[str, Any]:

    definition = (
        state.definition
    )

    snapshot = (
        state.snapshot
    )


    return {
        "source_id":
            definition.source_id,

        "display_name":
            definition.display_name,

        "source_type":
            definition.source_type.value,

        "provider":
            definition.provider,

        "geographic_scope":
            definition.geographic_scope,

        "methodology_note":
            definition.methodology_note,

        "attribution":
            definition.attribution,

        "license_name":
            definition.license_name,

        "source_url":
            definition.source_url,

        "expected_refresh_hours":
            definition.expected_refresh_hours,

        "stale_after_hours":
            definition.stale_after_hours,

        "freshness":
            state.freshness.value,

        "dataset_version":
            (
                snapshot.dataset_version
                if snapshot
                else None
            ),

        "observed_from":
            _isoformat_or_none(
                snapshot.observed_from
                if snapshot
                else None
            ),

        "observed_to":
            _isoformat_or_none(
                snapshot.observed_to
                if snapshot
                else None
            ),

        "refreshed_at":
            _isoformat_or_none(
                snapshot.refreshed_at
                if snapshot
                else None
            ),

        "retrieved_at":
            _isoformat_or_none(
                snapshot.retrieved_at
                if snapshot
                else None
            ),

        "record_count":
            (
                snapshot.record_count
                if snapshot
                else None
            ),
    }


def build_source_manifest(
    registry: SourceRegistry,
    *,
    now: datetime | None = None,
) -> tuple[
    dict[str, Any],
    ...
]:

    return tuple(
        source_state_manifest(
            state
        )
        for state
        in registry.list_states(
            now=now
        )
    )


def build_source_health_summary(
    registry: SourceRegistry,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:

    states = (
        registry.list_states(
            now=now
        )
    )


    registered_sources = (
        len(states)
    )

    sources_with_snapshots = sum(
        1
        for state in states
        if state.snapshot
        is not None
    )

    fresh_sources = sum(
        1
        for state in states
        if state.freshness.value
        == "fresh"
    )

    stale_sources = sum(
        1
        for state in states
        if state.freshness.value
        == "stale"
    )

    unknown_sources = sum(
        1
        for state in states
        if state.freshness.value
        == "unknown"
    )


    if registered_sources == 0:

        status = (
            "not_configured"
        )

    elif stale_sources > 0:

        status = (
            "degraded"
        )

    else:

        status = (
            "available"
        )


    return {
        "status":
            status,

        # External freshness must not determine
        # whether the core Wave 5 application
        # is considered ready.
        "affects_core_readiness":
            False,

        "registered_sources":
            registered_sources,

        "sources_with_snapshots":
            sources_with_snapshots,

        "fresh_sources":
            fresh_sources,

        "stale_sources":
            stale_sources,

        "unknown_sources":
            unknown_sources,
    }
