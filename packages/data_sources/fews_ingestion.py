"""Explicit FEWS refresh and local restore using the Phase 26A registry."""

from threading import RLock

from packages.data_sources.contracts import SourceDefinition, SourceType
from packages.data_sources.registry import SourceRegistry
from packages.data_sources.providers.fews_http_client import (
    FewsFetchResult, FewsMarketPriceClient, FewsMarketPriceQuery,
)
from packages.data_sources.providers.fews_market_prices import FEWS_MARKET_SOURCE_ID
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore, SnapshotScopeError, StoredFewsSnapshot, effective_fews_query,
)


_REGISTRY_LOCK = RLock()


class FewsIngestionError(RuntimeError):
    """The registry has a conflicting FEWS definition or snapshot."""


def build_fews_source_definition(stale_after_hours: int = 48) -> SourceDefinition:
    if type(stale_after_hours) is not int or stale_after_hours < 1:
        raise ValueError("stale_after_hours must be a positive integer.")
    return SourceDefinition(
        source_id=FEWS_MARKET_SOURCE_ID, display_name="FEWS NET Nigeria market prices",
        source_type=SourceType.MARKET_PRICE, provider="FEWS NET", geographic_scope="Nigeria",
        methodology_note=(
            "Monthly market observations for one explicitly selected commodity/date query. "
            "Coverage is limited to that query, not all Nigeria market prices. "
            "Freshness measures AgDA retrieval age, not the observation period or provider modification time."
        ),
        attribution="FEWS NET Data Warehouse", stale_after_hours=stale_after_hours,
        expected_refresh_hours=None, source_url="https://fdw.fews.net/api/marketpricefacts.json",
    )


def _check_definition(registry: SourceRegistry, definition: SourceDefinition) -> None:
    if registry.contains(definition.source_id) and registry.get_definition(definition.source_id) != definition:
        raise FewsIngestionError("The registry already has a different FEWS source definition.")


def _publish(registry: SourceRegistry, stored: StoredFewsSnapshot, definition: SourceDefinition) -> None:
    with _REGISTRY_LOCK:
        _check_definition(registry, definition)
        if not registry.contains(definition.source_id):
            registry.register(definition)
        current = registry.get_snapshot(definition.source_id)
        incoming = stored.result.snapshot
        if current is not None:
            if current.retrieved_at > incoming.retrieved_at:
                return
            if current.retrieved_at == incoming.retrieved_at and current != incoming:
                raise FewsIngestionError("The registry has a conflicting snapshot at this retrieval time.")
        registry.record_snapshot(incoming)


def restore_fews_market_prices(
    *, store: FewsSnapshotStore, registry: SourceRegistry, stale_after_hours: int = 48,
) -> StoredFewsSnapshot | None:
    definition = build_fews_source_definition(stale_after_hours)
    with _REGISTRY_LOCK:
        _check_definition(registry, definition)
        if not registry.contains(definition.source_id):
            registry.register(definition)
    stored = store.latest()
    if stored is not None:
        _publish(registry, stored, definition)
    return stored


def refresh_fews_market_prices(
    query: FewsMarketPriceQuery, *, store: FewsSnapshotStore,
    registry: SourceRegistry, client: FewsMarketPriceClient | None = None,
    stale_after_hours: int = 48,
) -> FewsFetchResult:
    definition = build_fews_source_definition(stale_after_hours)
    _check_definition(registry, definition)
    previous = store.latest()
    if previous is not None and effective_fews_query(previous.query) != effective_fews_query(query):
        raise SnapshotScopeError("This store belongs to another query; use a separate database.")
    result = (client if client is not None else FewsMarketPriceClient()).fetch(query)
    if result.snapshot is None:
        # Empty completion must not erase previous data or advance its freshness.
        return result
    with _REGISTRY_LOCK:
        _check_definition(registry, definition)
        if registry.contains(definition.source_id):
            current = registry.get_snapshot(definition.source_id)
            if (current is not None and current.retrieved_at == result.snapshot.retrieved_at
                    and current != result.snapshot):
                raise FewsIngestionError("The registry has a conflicting snapshot at this retrieval time.")
        # Keep registry conflict checks and publication serialized. HTTP happens
        # above this lock; the durable transaction still precedes publication.
        store.save(query, result)
        # Concurrent or out-of-order completions cannot publish an older stored run.
        latest = store.latest()
        if latest is None:
            raise FewsIngestionError("The saved FEWS snapshot could not be restored.")
        _publish(registry, latest, definition)
    return result
