from contextlib import closing
from dataclasses import (
    asdict,
    dataclass,
    fields,
)
from datetime import (
    datetime,
    timedelta,
)
from decimal import (
    Decimal,
    DecimalException,
)
from hashlib import sha256
import json
import sqlite3
from pathlib import Path
from typing import Any

from packages.data_sources.contracts import (
    SourceSnapshot,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_FORECAST_SOURCE_ID,
    OPEN_METEO_MODEL,
    OpenMeteoFetchResult,
    OpenMeteoForecastQuery,
)
from packages.data_sources.weather_forecasts import (
    WeatherForecastRecord,
)


class WeatherSnapshotStoreError(RuntimeError):
    """Base error for local weather snapshot persistence."""


class WeatherSnapshotScopeError(
    WeatherSnapshotStoreError
):
    """Raised when a store is reused for a different weather query."""


class WeatherSnapshotConflictError(
    WeatherSnapshotStoreError
):
    """Raised when one retrieval instant maps to conflicting content."""


@dataclass(
    frozen=True,
    slots=True,
)
class StoredWeatherSnapshot:
    snapshot_id: str
    query: OpenMeteoForecastQuery
    result: OpenMeteoFetchResult


def effective_open_meteo_query(
    query: OpenMeteoForecastQuery,
) -> dict[str, str | int]:

    if not isinstance(
        query,
        OpenMeteoForecastQuery,
    ):
        raise WeatherSnapshotStoreError(
            "Expected an Open-Meteo forecast query."
        )

    return {
        "latitude": str(
            query.latitude
        ),
        "longitude": str(
            query.longitude
        ),
        "forecast_days":
            query.forecast_days,
        "model":
            OPEN_METEO_MODEL,
    }


def _json_default(
    value: Any,
) -> str:

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    if isinstance(
        value,
        Decimal,
    ):
        return str(
            value
        )

    raise TypeError(
        "Unsupported persisted value: "
        f"{type(value).__name__}"
    )


def _json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        default=_json_default,
        allow_nan=False,
    )


def _utc_datetime(
    value: Any,
) -> bool:

    return (
        isinstance(
            value,
            datetime,
        )
        and value.utcoffset()
        == timedelta(0)
    )


def build_open_meteo_snapshot(
    query: OpenMeteoForecastQuery,
    records: tuple[
        WeatherForecastRecord,
        ...
    ],
    retrieved_at: datetime,
) -> SourceSnapshot:

    if not records:
        raise WeatherSnapshotStoreError(
            "Weather snapshot requires records."
        )

    query_url = query.url(
        records[0]
        .valid_at
        .date()
    )

    digest = sha256(
        _json(
            {
                "query_url":
                    query_url,
                "records": [
                    asdict(
                        record
                    )
                    for record
                    in records
                ],
            }
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    return SourceSnapshot(
        source_id=
            OPEN_METEO_FORECAST_SOURCE_ID,
        dataset_version=
            "open-meteo-hourly-v1:"
            + digest,
        observed_from=
            records[0].valid_at,
        observed_to=
            records[-1].valid_at,
        refreshed_at=
            retrieved_at,
        retrieved_at=
            retrieved_at,
        record_count=
            len(
                records
            ),
    )


def _validate_result(
    query: OpenMeteoForecastQuery,
    result: OpenMeteoFetchResult,
) -> None:

    if (
        not isinstance(
            query,
            OpenMeteoForecastQuery,
        )
        or not isinstance(
            result,
            OpenMeteoFetchResult,
        )
    ):
        raise WeatherSnapshotStoreError(
            "Expected an Open-Meteo query "
            "and completed fetch result."
        )

    if (
        not isinstance(
            result.records,
            tuple,
        )
        or not result.records
    ):
        raise WeatherSnapshotStoreError(
            "Only a nonempty completed "
            "weather snapshot can be saved."
        )

    if not isinstance(
        result.snapshot,
        SourceSnapshot,
    ):
        raise WeatherSnapshotStoreError(
            "Weather result requires "
            "SourceSnapshot metadata."
        )

    for name in (
        "requested_from",
        "requested_to",
        "retrieved_at",
    ):
        if not _utc_datetime(
            getattr(
                result,
                name,
            )
        ):
            raise WeatherSnapshotStoreError(
                "Weather result timestamps "
                "must be aware UTC."
            )

    if (
        result.requested_from
        > result.requested_to
    ):
        raise WeatherSnapshotStoreError(
            "Weather forecast bounds "
            "are invalid."
        )

    if (
        type(
            result.requests_made
        ) is not int
        or result.requests_made
        != 1
    ):
        raise WeatherSnapshotStoreError(
            "Completed weather fetch "
            "must contain exactly one request."
        )

    if (
        type(
            result.missing_value_count
        ) is not int
        or result.missing_value_count
        < 0
    ):
        raise WeatherSnapshotStoreError(
            "Invalid weather missing-value count."
        )

    expected_count = (
        query.forecast_days
        * 24
    )

    if (
        len(
            result.records
        )
        != expected_count
    ):
        raise WeatherSnapshotStoreError(
            "Weather record count does not "
            "match the requested horizon."
        )

    if (
        result.requested_from
        != result.records[0].valid_at
        or result.requested_to
        != result.records[-1].valid_at
    ):
        raise WeatherSnapshotStoreError(
            "Weather requested bounds do not "
            "match canonical records."
        )

    expected_time = (
        result.requested_from
    )

    missing_count = 0

    for record in result.records:

        if not isinstance(
            record,
            WeatherForecastRecord,
        ):
            raise WeatherSnapshotStoreError(
                "Invalid canonical weather record."
            )

        if (
            record.source_id
            != OPEN_METEO_FORECAST_SOURCE_ID
            or record.model
            != OPEN_METEO_MODEL
            or record.requested_latitude
            != query.latitude
            or record.requested_longitude
            != query.longitude
        ):
            raise WeatherSnapshotStoreError(
                "Weather record is outside "
                "the persisted query scope."
            )

        if (
            not _utc_datetime(
                record.valid_at
            )
            or record.valid_at
            != expected_time
        ):
            raise WeatherSnapshotStoreError(
                "Weather records must form "
                "a complete hourly UTC sequence."
            )

        expected_time += (
            timedelta(
                hours=1
            )
        )

        if (
            record.source_issued_at
            is not None
            and not _utc_datetime(
                record.source_issued_at
            )
        ):
            raise WeatherSnapshotStoreError(
                "Weather source issue time "
                "must be UTC or null."
            )

        for name in (
            "requested_latitude",
            "requested_longitude",
            "grid_latitude",
            "grid_longitude",
        ):
            value = getattr(
                record,
                name,
            )

            if (
                not isinstance(
                    value,
                    Decimal,
                )
                or not value.is_finite()
            ):
                raise WeatherSnapshotStoreError(
                    "Weather coordinates must "
                    "be finite Decimals."
                )

        for name in (
            "temperature_2m_c",
            "relative_humidity_2m_pct",
            "precipitation_mm",
        ):
            value = getattr(
                record,
                name,
            )

            if value is None:
                missing_count += 1
                continue

            if (
                not isinstance(
                    value,
                    Decimal,
                )
                or not value.is_finite()
            ):
                raise WeatherSnapshotStoreError(
                    "Weather measurements must "
                    "be finite Decimals or null."
                )

    if (
        missing_count
        != result.missing_value_count
    ):
        raise WeatherSnapshotStoreError(
            "Weather missing-value count "
            "does not match canonical records."
        )

    expected_snapshot = (
        build_open_meteo_snapshot(
            query,
            result.records,
            result.retrieved_at,
        )
    )

    if (
        result.snapshot
        != expected_snapshot
    ):
        raise WeatherSnapshotStoreError(
            "Weather snapshot metadata or "
            "content version does not match "
            "its canonical records."
        )


def _encode(
    query: OpenMeteoForecastQuery,
    result: OpenMeteoFetchResult,
) -> str:

    try:
        _validate_result(
            query,
            result,
        )

        return _json(
            {
                "schema_version":
                    1,
                "query":
                    effective_open_meteo_query(
                        query
                    ),
                "snapshot":
                    asdict(
                        result.snapshot
                    ),
                "records": [
                    asdict(
                        record
                    )
                    for record
                    in result.records
                ],
                "requested_from":
                    result.requested_from,
                "requested_to":
                    result.requested_to,
                "retrieved_at":
                    result.retrieved_at,
                "requests_made":
                    result.requests_made,
                "missing_value_count":
                    result.missing_value_count,
            }
        )

    except (
        ValueError,
        TypeError,
        DecimalException,
        AttributeError,
        OverflowError,
    ) as error:

        raise WeatherSnapshotStoreError(
            "Invalid weather snapshot data."
        ) from error


def _decode(
    snapshot_id: str,
    payload: str,
) -> StoredWeatherSnapshot:

    if (
        not isinstance(
            snapshot_id,
            str,
        )
        or len(
            snapshot_id
        )
        != 64
        or any(
            character
            not in "0123456789abcdef"
            for character
            in snapshot_id
        )
    ):
        raise WeatherSnapshotStoreError(
            "Invalid weather snapshot ID."
        )

    if (
        sha256(
            payload.encode(
                "utf-8"
            )
        ).hexdigest()
        != snapshot_id
    ):
        raise WeatherSnapshotStoreError(
            "Stored weather snapshot failed "
            "its integrity check."
        )

    try:
        data = json.loads(
            payload
        )

        expected_envelope = {
            "schema_version",
            "query",
            "snapshot",
            "records",
            "requested_from",
            "requested_to",
            "retrieved_at",
            "requests_made",
            "missing_value_count",
        }

        if (
            not isinstance(
                data,
                dict,
            )
            or set(
                data
            )
            != expected_envelope
            or type(
                data["schema_version"]
            ) is not int
            or data["schema_version"]
            != 1
        ):
            raise ValueError(
                "Unsupported weather snapshot envelope."
            )

        scope = data[
            "query"
        ]

        if (
            not isinstance(
                scope,
                dict,
            )
            or set(
                scope
            )
            != {
                "latitude",
                "longitude",
                "forecast_days",
                "model",
            }
            or scope[
                "model"
            ]
            != OPEN_METEO_MODEL
            or type(
                scope["forecast_days"]
            ) is not int
        ):
            raise ValueError(
                "Invalid weather query scope."
            )

        if (
            not isinstance(
                scope["latitude"],
                str,
            )
            or not isinstance(
                scope["longitude"],
                str,
            )
        ):
            raise ValueError(
                "Weather coordinates must "
                "be stored as strings."
            )

        query = OpenMeteoForecastQuery(
            latitude=Decimal(
                scope["latitude"]
            ),
            longitude=Decimal(
                scope["longitude"]
            ),
            forecast_days=
                scope["forecast_days"],
        )

        if (
            scope
            != effective_open_meteo_query(
                query
            )
        ):
            raise ValueError(
                "Invalid weather query scope."
            )

        snapshot_values = dict(
            data["snapshot"]
        )

        for name in (
            "observed_from",
            "observed_to",
            "refreshed_at",
            "retrieved_at",
        ):
            if not isinstance(
                snapshot_values[
                    name
                ],
                str,
            ):
                raise ValueError(
                    "Snapshot timestamps must "
                    "be stored as strings."
                )

            snapshot_values[
                name
            ] = datetime.fromisoformat(
                snapshot_values[
                    name
                ]
            )

        snapshot = SourceSnapshot(
            **snapshot_values
        )

        if not isinstance(
            data["records"],
            list,
        ):
            raise ValueError(
                "Invalid weather record list."
            )

        expected_record_fields = {
            field.name
            for field
            in fields(
                WeatherForecastRecord
            )
        }

        records = []

        decimal_fields = {
            "requested_latitude",
            "requested_longitude",
            "grid_latitude",
            "grid_longitude",
            "temperature_2m_c",
            "relative_humidity_2m_pct",
            "precipitation_mm",
        }

        for values in data[
            "records"
        ]:
            if (
                not isinstance(
                    values,
                    dict,
                )
                or set(
                    values
                )
                != expected_record_fields
            ):
                raise ValueError(
                    "Invalid weather record fields."
                )

            values = dict(
                values
            )

            if not isinstance(
                values["valid_at"],
                str,
            ):
                raise ValueError(
                    "Weather validity time must "
                    "be stored as text."
                )

            values["valid_at"] = (
                datetime.fromisoformat(
                    values["valid_at"]
                )
            )

            if (
                values[
                    "source_issued_at"
                ]
                is not None
            ):
                if not isinstance(
                    values[
                        "source_issued_at"
                    ],
                    str,
                ):
                    raise ValueError(
                        "Weather source issue time "
                        "must be text or null."
                    )

                values[
                    "source_issued_at"
                ] = datetime.fromisoformat(
                    values[
                        "source_issued_at"
                    ]
                )

            for name in decimal_fields:
                value = values[
                    name
                ]

                if value is None:
                    if name in {
                        "requested_latitude",
                        "requested_longitude",
                        "grid_latitude",
                        "grid_longitude",
                    }:
                        raise ValueError(
                            "Weather coordinates "
                            "cannot be null."
                        )

                    continue

                if not isinstance(
                    value,
                    str,
                ):
                    raise ValueError(
                        "Weather decimals must "
                        "be stored as strings."
                    )

                values[
                    name
                ] = Decimal(
                    value
                )

            records.append(
                WeatherForecastRecord(
                    **values
                )
            )

        for name in (
            "requested_from",
            "requested_to",
            "retrieved_at",
        ):
            if not isinstance(
                data[
                    name
                ],
                str,
            ):
                raise ValueError(
                    "Weather result timestamps must "
                    "be stored as strings."
                )

        result = OpenMeteoFetchResult(
            records=tuple(
                records
            ),
            snapshot=snapshot,
            requested_from=
                datetime.fromisoformat(
                    data[
                        "requested_from"
                    ]
                ),
            requested_to=
                datetime.fromisoformat(
                    data[
                        "requested_to"
                    ]
                ),
            retrieved_at=
                datetime.fromisoformat(
                    data[
                        "retrieved_at"
                    ]
                ),
            requests_made=
                data[
                    "requests_made"
                ],
            missing_value_count=
                data[
                    "missing_value_count"
                ],
        )

        _validate_result(
            query,
            result,
        )

        return StoredWeatherSnapshot(
            snapshot_id=
                snapshot_id,
            query=
                query,
            result=
                result,
        )

    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        DecimalException,
        OverflowError,
        RecursionError,
    ) as error:
        raise WeatherSnapshotStoreError(
            "Stored weather snapshot is "
            "malformed or incompatible."
        ) from error


class WeatherSnapshotStore:
    """Persistent store for complete validated weather forecast snapshots."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_snapshot_bytes:
            int = 16 * 1024 * 1024,
    ) -> None:

        if (
            type(
                max_snapshot_bytes
            ) is not int
            or max_snapshot_bytes
            < 1
        ):
            raise ValueError(
                "max_snapshot_bytes must "
                "be a positive integer."
            )

        if (
            not str(
                path
            ).strip()
            or str(
                path
            )
            == ":memory:"
        ):
            raise WeatherSnapshotStoreError(
                "A persistent weather snapshot "
                "database path is required."
            )

        self.path = (
            Path(
                path
            )
            .expanduser()
            .resolve()
        )

        release_root = (
            Path(
                __file__
            )
            .resolve()
            .parents[2]
            / "data"
            / "releases"
        ).resolve()

        if (
            self.path
            == release_root
            or self.path.is_relative_to(
                release_root
            )
        ):
            raise WeatherSnapshotStoreError(
                "External weather snapshots "
                "cannot be stored in data/releases."
            )

        self.max_snapshot_bytes = (
            max_snapshot_bytes
        )


    def _read_row(
        self,
        connection: sqlite3.Connection,
        snapshot_id: str | None,
    ) -> StoredWeatherSnapshot | None:

        if snapshot_id is None:
            row = connection.execute(
                "SELECT snapshot_id, retrieved_at, "
                "scope_json, "
                "length(CAST(payload AS BLOB)) "
                "FROM weather_forecast_snapshots "
                "ORDER BY retrieved_at DESC LIMIT 1"
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT snapshot_id, retrieved_at, "
                "scope_json, "
                "length(CAST(payload AS BLOB)) "
                "FROM weather_forecast_snapshots "
                "WHERE snapshot_id = ?",
                (
                    snapshot_id,
                ),
            ).fetchone()

        if row is None:
            return None

        if (
            type(row[3]) is not int
            or row[3] > self.max_snapshot_bytes
        ):
            raise WeatherSnapshotStoreError(
                "Stored weather snapshot exceeds "
                "max_snapshot_bytes."
            )

        payload_row = connection.execute(
            "SELECT payload "
            "FROM weather_forecast_snapshots "
            "WHERE snapshot_id = ?",
            (
                row[0],
            ),
        ).fetchone()

        if (
            payload_row is None
            or not isinstance(
                payload_row[0],
                str,
            )
        ):
            raise WeatherSnapshotStoreError(
                "Stored weather payload must "
                "be JSON text."
            )

        stored = _decode(
            row[0],
            payload_row[0],
        )

        if (
            row[1]
            != stored.result.retrieved_at.isoformat(
                timespec="microseconds"
            )
            or row[2]
            != _json(
                effective_open_meteo_query(
                    stored.query
                )
            )
        ):
            raise WeatherSnapshotStoreError(
                "Stored weather snapshot index "
                "does not match its payload."
            )

        return stored

    def _load(
        self,
        snapshot_id: str | None,
    ) -> StoredWeatherSnapshot | None:

        try:
            if not self.path.exists():
                return None

            with closing(
                sqlite3.connect(
                    self.path.as_uri()
                    + "?mode=ro",
                    uri=True,
                    timeout=5,
                )
            ) as connection:

                connection.execute(
                    "BEGIN"
                )

                if (
                    connection.execute(
                        "SELECT 1 FROM sqlite_master "
                        "WHERE name NOT LIKE 'sqlite_%' "
                        "LIMIT 1"
                    ).fetchone()
                    is None
                ):
                    return None

                return self._read_row(
                    connection,
                    snapshot_id,
                )

        except (
            OSError,
            sqlite3.Error,
        ) as error:
            raise WeatherSnapshotStoreError(
                "Could not read the local weather "
                "snapshot store."
            ) from error

    def latest(
        self,
    ) -> StoredWeatherSnapshot | None:

        return self._load(
            None
        )

    def get(
        self,
        snapshot_id: str,
    ) -> StoredWeatherSnapshot | None:

        if (
            not isinstance(
                snapshot_id,
                str,
            )
            or len(
                snapshot_id
            )
            != 64
            or any(
                character
                not in "0123456789abcdef"
                for character
                in snapshot_id
            )
        ):
            raise WeatherSnapshotStoreError(
                "Invalid weather snapshot ID."
            )

        return self._load(
            snapshot_id
        )


    def save(
        self,
        query: OpenMeteoForecastQuery,
        result: OpenMeteoFetchResult,
    ) -> StoredWeatherSnapshot:

        payload = _encode(
            query,
            result,
        )

        encoded = payload.encode(
            "utf-8"
        )

        if (
            len(encoded)
            > self.max_snapshot_bytes
        ):
            raise WeatherSnapshotStoreError(
                "Weather snapshot exceeds "
                "max_snapshot_bytes."
            )

        snapshot_id = sha256(
            encoded
        ).hexdigest()

        candidate = _decode(
            snapshot_id,
            payload,
        )

        scope_json = _json(
            effective_open_meteo_query(
                query
            )
        )

        retrieved_at = (
            result.retrieved_at
            .isoformat(
                timespec="microseconds"
            )
        )

        try:
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with closing(
                sqlite3.connect(
                    self.path,
                    timeout=5,
                )
            ) as connection:

                connection.execute(
                    "PRAGMA synchronous = FULL"
                )

                with connection:
                    connection.execute(
                        "BEGIN IMMEDIATE"
                    )

                    existing_schema = (
                        connection.execute(
                            "SELECT name "
                            "FROM sqlite_master "
                            "WHERE name NOT LIKE "
                            "'sqlite_%'"
                        )
                        .fetchall()
                    )

                    if (
                        existing_schema
                        and (
                            "weather_forecast_snapshots",
                        )
                        not in existing_schema
                    ):
                        raise WeatherSnapshotStoreError(
                            "The database contains "
                            "an unrelated schema."
                        )

                    connection.execute(
                        "CREATE TABLE IF NOT EXISTS "
                        "weather_forecast_snapshots ("
                        "snapshot_id TEXT PRIMARY KEY, "
                        "retrieved_at TEXT NOT NULL UNIQUE, "
                        "scope_json TEXT NOT NULL, "
                        "payload TEXT NOT NULL)"
                    )

                    latest = self._read_row(
                        connection,
                        None,
                    )

                    if (
                        latest is not None
                        and effective_open_meteo_query(
                            latest.query
                        )
                        != effective_open_meteo_query(
                            query
                        )
                    ):
                        raise WeatherSnapshotScopeError(
                            "This weather store belongs "
                            "to another query; use a "
                            "separate database."
                        )

                    same_time = (
                        connection.execute(
                            "SELECT snapshot_id "
                            "FROM "
                            "weather_forecast_snapshots "
                            "WHERE retrieved_at = ?",
                            (
                                retrieved_at,
                            ),
                        )
                        .fetchone()
                    )

                    if (
                        same_time is not None
                        and same_time[0]
                        != snapshot_id
                    ):
                        raise WeatherSnapshotConflictError(
                            "Conflicting weather snapshot "
                            "at the same retrieval time."
                        )

                    connection.execute(
                        "INSERT INTO "
                        "weather_forecast_snapshots "
                        "(snapshot_id, retrieved_at, "
                        "scope_json, payload) "
                        "VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(snapshot_id) "
                        "DO NOTHING",
                        (
                            snapshot_id,
                            retrieved_at,
                            scope_json,
                            payload,
                        ),
                    )

            return candidate

        except (
            OSError,
            sqlite3.Error,
        ) as error:
            raise WeatherSnapshotStoreError(
                "Could not save the local weather "
                "snapshot."
            ) from error
