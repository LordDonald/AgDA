"""Explicit weather refresh and local restore using the Phase 26A registry."""

from threading import RLock

from packages.data_sources.contracts import (
    SourceDefinition,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    OpenMeteoFetchResult,
    OpenMeteoForecastClient,
    OpenMeteoForecastQuery,
    build_open_meteo_source_definition,
)
from packages.data_sources.registry import (
    SourceRegistry,
)
from packages.data_sources.weather_snapshot_store import (
    StoredWeatherSnapshot,
    WeatherSnapshotScopeError,
    WeatherSnapshotStore,
    effective_open_meteo_query,
)


_REGISTRY_LOCK = RLock()


class WeatherIngestionError(RuntimeError):
    """The registry has a conflicting weather definition or snapshot."""


def _weather_definition(
    stale_after_hours: int = 6,
) -> SourceDefinition:

    if (
        type(stale_after_hours) is not int
        or stale_after_hours < 1
    ):
        raise ValueError(
            "stale_after_hours must be a positive integer."
        )

    definition = (
        build_open_meteo_source_definition()
    )

    if (
        definition.stale_after_hours
        == stale_after_hours
    ):
        return definition

    return SourceDefinition(
        source_id=
            definition.source_id,
        display_name=
            definition.display_name,
        source_type=
            definition.source_type,
        provider=
            definition.provider,
        geographic_scope=
            definition.geographic_scope,
        methodology_note=
            definition.methodology_note,
        attribution=
            definition.attribution,
        stale_after_hours=
            stale_after_hours,
        expected_refresh_hours=
            definition.expected_refresh_hours,
        license_name=
            definition.license_name,
        source_url=
            definition.source_url,
    )


def _check_definition(
    registry: SourceRegistry,
    definition: SourceDefinition,
) -> None:

    if (
        registry.contains(
            definition.source_id
        )
        and registry.get_definition(
            definition.source_id
        )
        != definition
    ):
        raise WeatherIngestionError(
            "The registry already has a different "
            "weather source definition."
        )


def _publish(
    registry: SourceRegistry,
    stored: StoredWeatherSnapshot,
    definition: SourceDefinition,
) -> None:

    with _REGISTRY_LOCK:
        _check_definition(
            registry,
            definition,
        )

        if not registry.contains(
            definition.source_id
        ):
            registry.register(
                definition
            )

        current = registry.get_snapshot(
            definition.source_id
        )

        incoming = (
            stored.result.snapshot
        )

        if current is not None:
            if (
                current.retrieved_at
                > incoming.retrieved_at
            ):
                return

            if (
                current.retrieved_at
                == incoming.retrieved_at
                and current != incoming
            ):
                raise WeatherIngestionError(
                    "The registry has a conflicting "
                    "weather snapshot at this "
                    "retrieval time."
                )

        registry.record_snapshot(
            incoming
        )


def restore_weather_forecast(
    *,
    store: WeatherSnapshotStore,
    registry: SourceRegistry,
    stale_after_hours: int = 6,
) -> StoredWeatherSnapshot | None:

    definition = _weather_definition(
        stale_after_hours
    )

    with _REGISTRY_LOCK:
        _check_definition(
            registry,
            definition,
        )

        if not registry.contains(
            definition.source_id
        ):
            registry.register(
                definition
            )

    stored = store.latest()

    if stored is not None:
        _publish(
            registry,
            stored,
            definition,
        )

    return stored


def refresh_weather_forecast(
    query: OpenMeteoForecastQuery,
    *,
    store: WeatherSnapshotStore,
    registry: SourceRegistry,
    client: OpenMeteoForecastClient | None = None,
    stale_after_hours: int = 6,
) -> OpenMeteoFetchResult:

    definition = _weather_definition(
        stale_after_hours
    )

    if (
        definition.source_id
        != OPEN_METEO_FORECAST_SOURCE_ID
    ):
        raise WeatherIngestionError(
            "Unexpected weather source definition."
        )

    _check_definition(
        registry,
        definition,
    )

    previous = store.latest()

    if (
        previous is not None
        and effective_open_meteo_query(
            previous.query
        )
        != effective_open_meteo_query(
            query
        )
    ):
        raise WeatherSnapshotScopeError(
            "This weather store belongs to another "
            "query; use a separate database."
        )

    result = (
        client
        if client is not None
        else OpenMeteoForecastClient()
    ).fetch(
        query
    )

    with _REGISTRY_LOCK:
        _check_definition(
            registry,
            definition,
        )

        if registry.contains(
            definition.source_id
        ):
            current = registry.get_snapshot(
                definition.source_id
            )

            if (
                current is not None
                and current.retrieved_at
                == result.snapshot.retrieved_at
                and current
                != result.snapshot
            ):
                raise WeatherIngestionError(
                    "The registry has a conflicting "
                    "weather snapshot at this "
                    "retrieval time."
                )

        # Durable persistence precedes publication.
        store.save(
            query,
            result,
        )

        latest = store.latest()

        if latest is None:
            raise WeatherIngestionError(
                "The saved weather snapshot "
                "could not be restored."
            )

        _publish(
            registry,
            latest,
            definition,
        )

    return result
