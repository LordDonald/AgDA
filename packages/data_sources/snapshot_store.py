"""Transactional local storage for one FEWS monthly query and its history."""

from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any

from packages.data_sources.contracts import SourceSnapshot
from packages.data_sources.market_prices import MarketPriceRecord
from packages.data_sources.providers.fews_http_client import (
    FewsFetchResult, FewsMarketPriceQuery, build_fews_snapshot,
)
from packages.data_sources.providers.fews_market_prices import FEWS_MARKET_SOURCE_ID


class SnapshotStoreError(RuntimeError):
    """A snapshot could not be validated, saved, or restored."""


class SnapshotScopeError(SnapshotStoreError):
    """A store already belongs to a different query."""


class SnapshotConflictError(SnapshotStoreError):
    """Different snapshots claim the same retrieval instant."""


@dataclass(frozen=True, slots=True)
class StoredFewsSnapshot:
    snapshot_id: str
    query: FewsMarketPriceQuery
    result: FewsFetchResult


def effective_fews_query(query: FewsMarketPriceQuery) -> dict[str, str]:
    scope = {
        "country_code": "NG", "schedule": "Monthly",
        "start_date": query.start_date.isoformat(), "price_type": query.price_type,
    }
    if query.end_date is not None:
        scope["end_date"] = query.end_date.isoformat()
    if query.cpcv2 is not None:
        scope["cpcv2"] = query.cpcv2
    else:
        scope["product"] = query.product
    return scope


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported persisted value: {type(value).__name__}")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      default=_json_default, allow_nan=False)


def _utc_datetime(value: Any) -> bool:
    return isinstance(value, datetime) and value.utcoffset() == timedelta(0)


def _validate_result(query: FewsMarketPriceQuery, result: FewsFetchResult) -> None:
    if not isinstance(query, FewsMarketPriceQuery) or not isinstance(result, FewsFetchResult):
        raise SnapshotStoreError("Expected a FEWS query and completed fetch result.")
    if not isinstance(result.snapshot, SourceSnapshot) or not result.records:
        raise SnapshotStoreError("Only a nonempty completed snapshot can be saved.")
    if not isinstance(result.records, tuple) or not _utc_datetime(result.retrieved_at):
        raise SnapshotStoreError("Records must be a tuple and retrieval time must be aware UTC.")
    if (type(result.pages_fetched) is not int or type(result.requests_made) is not int
            or result.pages_fetched < 1 or result.requests_made != result.pages_fetched):
        raise SnapshotStoreError("Invalid completed-fetch counters.")
    optional_text = {
        "admin_1", "admin_2", "fnid", "cpcv2_description", "product_source",
        "source_document", "collection_status",
    }
    special_fields = {
        "period_date", "source_modified_at", "market_id", "dataseries",
        "value", "longitude", "latitude",
    }
    for record in result.records:
        if not isinstance(record, MarketPriceRecord) or type(record.period_date) is not date:
            raise SnapshotStoreError("Invalid canonical market-price record.")
        for field in fields(record):
            value = getattr(record, field.name)
            if field.name not in special_fields:
                if value is None and field.name in optional_text:
                    continue
                if not isinstance(value, str) or not value.strip():
                    raise SnapshotStoreError("Invalid text field in canonical record.")
        for name in ("value", "longitude", "latitude"):
            value = getattr(record, name)
            if value is None and name != "value":
                continue
            if not isinstance(value, Decimal) or not value.is_finite():
                raise SnapshotStoreError("Canonical decimal fields must be finite Decimals.")
        if record.value < 0:
            raise SnapshotStoreError("Market prices must not be negative.")
        for name in ("market_id", "dataseries"):
            value = getattr(record, name)
            if value is not None and type(value) is not int:
                raise SnapshotStoreError("Canonical IDs must be integers or null.")
        if record.source_modified_at is not None and not isinstance(record.source_modified_at, datetime):
            raise SnapshotStoreError("Provider modification time must be a datetime or null.")
        if (record.source_id != FEWS_MARKET_SOURCE_ID or record.country_code != "NG"
                or record.price_type != query.price_type
                or record.period_date < query.start_date
                or (query.end_date is not None and record.period_date > query.end_date)
                or (query.cpcv2 is not None and not record.cpcv2.startswith(query.cpcv2))):
            raise SnapshotStoreError("Record is outside the persisted query scope.")
    snapshot = result.snapshot
    if (type(snapshot.record_count) is not int
            or any(not _utc_datetime(getattr(snapshot, name)) for name in (
                "observed_from", "observed_to", "refreshed_at", "retrieved_at"))
            or snapshot != build_fews_snapshot(query, result.records, result.retrieved_at)):
        raise SnapshotStoreError("Snapshot metadata or content version does not match its records.")


def _encode(query: FewsMarketPriceQuery, result: FewsFetchResult) -> str:
    try:
        _validate_result(query, result)
        return _json({
            "schema_version": 1, "query": effective_fews_query(query),
            "snapshot": asdict(result.snapshot),
            "records": [asdict(record) for record in result.records],
            "retrieved_at": result.retrieved_at,
            "pages_fetched": result.pages_fetched, "requests_made": result.requests_made,
        })
    except (ValueError, TypeError, DecimalException, AttributeError, OverflowError) as error:
        raise SnapshotStoreError("Invalid snapshot data.") from error


def _decode(snapshot_id: str, payload: str) -> StoredFewsSnapshot:
    if sha256(payload.encode("utf-8")).hexdigest() != snapshot_id:
        raise SnapshotStoreError("Stored snapshot failed its integrity check.")
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or set(data) != {
            "schema_version", "query", "snapshot", "records", "retrieved_at",
            "pages_fetched", "requests_made",
        } or type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("Unsupported snapshot envelope")
        scope = data["query"]
        query = FewsMarketPriceQuery(
            start_date=date.fromisoformat(scope["start_date"]),
            end_date=date.fromisoformat(scope["end_date"]) if "end_date" in scope else None,
            cpcv2=scope.get("cpcv2"), product=scope.get("product"), price_type=scope["price_type"],
        )
        if scope != effective_fews_query(query):
            raise ValueError("Invalid query scope")
        snapshot_values = dict(data["snapshot"])
        for name in ("observed_from", "observed_to", "refreshed_at", "retrieved_at"):
            snapshot_values[name] = datetime.fromisoformat(snapshot_values[name])
        snapshot = SourceSnapshot(**snapshot_values)
        if not isinstance(data["records"], list):
            raise ValueError("Invalid record list")
        records = []
        for values in data["records"]:
            if not isinstance(values, dict) or set(values) != {field.name for field in fields(MarketPriceRecord)}:
                raise ValueError("Invalid record fields")
            values = dict(values)
            values["period_date"] = date.fromisoformat(values["period_date"])
            for name in ("value", "longitude", "latitude"):
                if values[name] is not None:
                    if not isinstance(values[name], str):
                        raise ValueError("Decimals must be stored as strings")
                    values[name] = Decimal(values[name])
            if values["source_modified_at"] is not None:
                values["source_modified_at"] = datetime.fromisoformat(values["source_modified_at"])
            records.append(MarketPriceRecord(**values))
        result = FewsFetchResult(
            records=tuple(records), snapshot=snapshot,
            retrieved_at=datetime.fromisoformat(data["retrieved_at"]),
            pages_fetched=data["pages_fetched"], requests_made=data["requests_made"],
        )
        _validate_result(query, result)
        return StoredFewsSnapshot(snapshot_id=snapshot_id, query=query, result=result)
    except (ValueError, TypeError, KeyError, AttributeError, DecimalException, OverflowError, RecursionError) as error:
        raise SnapshotStoreError("Stored snapshot is malformed or incompatible.") from error


class FewsSnapshotStore:
    """Append-only complete snapshots; latest is determined by retrieval time.

    A store is pinned to its first effective query. Use another store to ingest
    another scope. Construction and reads never create a database or directories.
    """

    def __init__(self, path: str | Path, *, max_snapshot_bytes: int = 64 * 1024 * 1024):
        if type(max_snapshot_bytes) is not int or max_snapshot_bytes < 1:
            raise ValueError("max_snapshot_bytes must be a positive integer.")
        if not str(path).strip() or str(path) == ":memory:":
            raise SnapshotStoreError("A persistent snapshot database path is required.")
        self.path = Path(path).expanduser().resolve()
        release_root = (Path(__file__).resolve().parents[2] / "data" / "releases").resolve()
        if self.path == release_root or self.path.is_relative_to(release_root):
            raise SnapshotStoreError("External snapshots cannot be stored in data/releases.")
        self.max_snapshot_bytes = max_snapshot_bytes

    def _read_row(self, connection: sqlite3.Connection, snapshot_id: str | None) -> StoredFewsSnapshot | None:
        if snapshot_id is None:
            row = connection.execute(
                "SELECT snapshot_id, retrieved_at, scope_json, length(CAST(payload AS BLOB)) "
                "FROM fews_market_price_snapshots ORDER BY retrieved_at DESC LIMIT 1"
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT snapshot_id, retrieved_at, scope_json, length(CAST(payload AS BLOB)) "
                "FROM fews_market_price_snapshots WHERE snapshot_id = ?", (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        if type(row[3]) is not int or row[3] > self.max_snapshot_bytes:
            raise SnapshotStoreError("Stored snapshot exceeds max_snapshot_bytes.")
        payload = connection.execute(
            "SELECT payload FROM fews_market_price_snapshots WHERE snapshot_id = ?", (row[0],),
        ).fetchone()[0]
        if not isinstance(payload, str):
            raise SnapshotStoreError("Stored payload must be JSON text.")
        stored = _decode(row[0], payload)
        if (row[1] != stored.result.retrieved_at.isoformat(timespec="microseconds")
                or row[2] != _json(effective_fews_query(stored.query))):
            raise SnapshotStoreError("Stored snapshot index does not match its payload.")
        return stored

    def _load(self, snapshot_id: str | None) -> StoredFewsSnapshot | None:
        try:
            if not self.path.exists():
                return None
            with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)) as connection:
                # Keep metadata and payload reads in one consistent SQLite view.
                connection.execute("BEGIN")
                if connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
                ).fetchone() is None:
                    # A failed first transaction can leave an empty SQLite file.
                    # It has no saved state; later explicit ingestion may retry.
                    return None
                return self._read_row(connection, snapshot_id)
        except (OSError, sqlite3.Error) as error:
            raise SnapshotStoreError("Could not read the local FEWS snapshot store.") from error

    def latest(self) -> StoredFewsSnapshot | None:
        return self._load(None)

    def get(self, snapshot_id: str) -> StoredFewsSnapshot | None:
        if not isinstance(snapshot_id, str) or len(snapshot_id) != 64 or any(c not in "0123456789abcdef" for c in snapshot_id):
            raise SnapshotStoreError("Invalid snapshot ID.")
        return self._load(snapshot_id)

    def save(self, query: FewsMarketPriceQuery, result: FewsFetchResult) -> StoredFewsSnapshot:
        payload = _encode(query, result)
        encoded = payload.encode("utf-8")
        if len(encoded) > self.max_snapshot_bytes:
            raise SnapshotStoreError("Snapshot exceeds max_snapshot_bytes.")
        snapshot_id = sha256(encoded).hexdigest()
        candidate = _decode(snapshot_id, payload)
        scope_json = _json(effective_fews_query(query))
        retrieved_at = result.retrieved_at.isoformat(timespec="microseconds")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=5)) as connection:
                connection.execute("PRAGMA synchronous = FULL")
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    existing_schema = connection.execute(
                        "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                    if existing_schema and ("fews_market_price_snapshots",) not in existing_schema:
                        raise SnapshotStoreError("The database contains an unrelated schema.")
                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS fews_market_price_snapshots ("
                        "snapshot_id TEXT PRIMARY KEY, retrieved_at TEXT NOT NULL UNIQUE, "
                        "scope_json TEXT NOT NULL, payload TEXT NOT NULL)"
                    )
                    latest = self._read_row(connection, None)
                    if latest is not None and effective_fews_query(latest.query) != effective_fews_query(query):
                        raise SnapshotScopeError("This store belongs to another query; use a separate database.")
                    same_time = connection.execute(
                        "SELECT snapshot_id FROM fews_market_price_snapshots WHERE retrieved_at = ?", (retrieved_at,),
                    ).fetchone()
                    if same_time is not None and same_time[0] != snapshot_id:
                        raise SnapshotConflictError("Conflicting snapshot at the same retrieval time.")
                    connection.execute(
                        "INSERT INTO fews_market_price_snapshots (snapshot_id, retrieved_at, scope_json, payload) "
                        "VALUES (?, ?, ?, ?) ON CONFLICT(snapshot_id) DO NOTHING",
                        (snapshot_id, retrieved_at, scope_json, payload),
                    )
            return candidate
        except (OSError, sqlite3.Error) as error:
            raise SnapshotStoreError("Could not save the local FEWS snapshot; registry was not updated.") from error
