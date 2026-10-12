"""Bind external answer provenance to the exact immutable snapshot executed."""

from packages.data_sources.catalog import source_state_manifest
from packages.data_sources.contracts import evaluate_freshness
from packages.data_sources.registry import SourceRegistry, SourceState
from packages.data_sources.snapshot_store import StoredFewsSnapshot, effective_fews_query
from packages.data_sources.weather_snapshot_store import StoredWeatherSnapshot, effective_open_meteo_query


def captured_source_manifest(
    registry: SourceRegistry,
    source_id: str,
    stored: StoredFewsSnapshot | StoredWeatherSnapshot,
) -> dict:
    definition = registry.get_definition(source_id)
    source = source_state_manifest(SourceState(
        definition=definition, snapshot=stored.result.snapshot,
        freshness=evaluate_freshness(definition, stored.result.snapshot),
    ))
    source["query"] = (
        effective_fews_query(stored.query) if isinstance(stored, StoredFewsSnapshot)
        else effective_open_meteo_query(stored.query)
    )
    return source
