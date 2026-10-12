"""Run one guarded external-data refresh for scheduling/operations."""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from packages.data_sources.external_refresh import (
    ExternalRefreshInvariantError,
    ExternalRefreshOutcome,
    ExternalRefreshStatus,
    refresh_fews_source,
    refresh_weather_source,
)
from packages.data_sources.providers.fews_http_client import (
    FewsClientLimits,
    FewsMarketPriceClient,
    FewsMarketPriceQuery,
)
from packages.data_sources.providers.open_meteo_forecast import (
    OpenMeteoForecastClient,
    OpenMeteoForecastQuery,
    WeatherClientLimits,
)
from packages.data_sources.registry import (
    SourceRegistry,
)
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore,
    SnapshotStoreError,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
    WeatherSnapshotStoreError,
)


def _coordinate(value: str) -> Decimal:
    try:
        return Decimal(value)

    except InvalidOperation as error:
        raise argparse.ArgumentTypeError(
            "coordinate must be a Decimal"
        ) from error


def _serialize(
    outcome: ExternalRefreshOutcome,
) -> dict[str, object | None]:
    return {
        "source_id":
            outcome.source_id,

        "status":
            outcome.status.value,

        "previous_snapshot_id":
            outcome.previous_snapshot_id,

        "active_snapshot_id":
            outcome.active_snapshot_id,

        "retrieved_at": (
            outcome.retrieved_at.isoformat()
            if outcome.retrieved_at is not None
            else None
        ),

        "record_count":
            outcome.record_count,

        "error_type":
            outcome.error_type,

        "error_message":
            outcome.error_message,
    }


def _emit(
    payload: dict[str, object | None],
) -> None:
    print(
        json.dumps(
            payload,
            sort_keys=True,
        )
    )


def _exit_code(
    status: ExternalRefreshStatus,
) -> int:
    if status in {
        ExternalRefreshStatus.UPDATED,
        ExternalRefreshStatus.UNCHANGED,
    }:
        return 0

    if status in {
        ExternalRefreshStatus.FAILED_RETAINED,
        ExternalRefreshStatus.FAILED_NO_SNAPSHOT,
    }:
        return 2

    if status in {
        ExternalRefreshStatus.NO_DATA,
        ExternalRefreshStatus.NO_DATA_RETAINED,
    }:
        return 3

    return 4


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "source",
        choices=(
            "fews",
            "weather",
        ),
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--stale-after-hours",
        type=int,
        default=None,
    )

    # FEWS pilot scope.
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        default=date(
            2025,
            1,
            1,
        ),
    )

    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=date(
            2025,
            1,
            31,
        ),
    )

    parser.add_argument(
        "--cpcv2",
        default="R01122AC",
    )

    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--max-requests",
        type=int,
        default=3,
    )

    # Source-specific default selected in main.
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
    )

    # Open-Meteo Aba pilot scope.
    parser.add_argument(
        "--latitude",
        type=_coordinate,
        default=Decimal(
            "5.10719"
        ),
    )

    parser.add_argument(
        "--longitude",
        type=_coordinate,
        default=Decimal(
            "7.37063"
        ),
    )

    parser.add_argument(
        "--days",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20,
    )

    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=1024 * 1024,
    )

    return parser


def _refresh_fews(
    args: argparse.Namespace,
) -> ExternalRefreshOutcome:
    database = (
        args.database
        if args.database is not None
        else Path(
            "data/external/"
            "fews_ng_white_maize_2025_01.sqlite3"
        )
    )

    stale_after_hours = (
        args.stale_after_hours
        if args.stale_after_hours is not None
        else 48
    )

    max_records = (
        args.max_records
        if args.max_records is not None
        else 300
    )

    query = FewsMarketPriceQuery(
        start_date=args.start_date,
        end_date=args.end_date,
        cpcv2=args.cpcv2,
    )

    client = FewsMarketPriceClient(
        limits=FewsClientLimits(
            page_size=args.page_size,
            max_pages=args.max_pages,
            max_requests=args.max_requests,
            max_records=max_records,
        )
    )

    return refresh_fews_source(
        query,
        store=FewsSnapshotStore(
            database
        ),
        registry=SourceRegistry(),
        client=client,
        stale_after_hours=
            stale_after_hours,
    )


def _refresh_weather(
    args: argparse.Namespace,
) -> ExternalRefreshOutcome:
    database = (
        args.database
        if args.database is not None
        else Path(
            "data/external/"
            "weather_aba_forecast.sqlite3"
        )
    )

    stale_after_hours = (
        args.stale_after_hours
        if args.stale_after_hours is not None
        else 6
    )

    max_records = (
        args.max_records
        if args.max_records is not None
        else 168
    )

    query = OpenMeteoForecastQuery(
        latitude=args.latitude,
        longitude=args.longitude,
        forecast_days=args.days,
    )

    client = OpenMeteoForecastClient(
        limits=WeatherClientLimits(
            max_records=max_records,
            timeout_seconds=
                args.timeout_seconds,
            max_response_bytes=
                args.max_response_bytes,
        )
    )

    return refresh_weather_source(
        query,
        store=WeatherSnapshotStore(
            database
        ),
        registry=SourceRegistry(),
        client=client,
        stale_after_hours=
            stale_after_hours,
    )


def main(
    argv=None,
) -> int:
    args = _parser().parse_args(
        argv
    )

    try:
        outcome = (
            _refresh_fews(args)
            if args.source == "fews"
            else _refresh_weather(args)
        )

    except ExternalRefreshInvariantError as error:
        _emit(
            {
                "source_id":
                    None,

                "status":
                    "invariant_violation",

                "previous_snapshot_id":
                    None,

                "active_snapshot_id":
                    None,

                "retrieved_at":
                    None,

                "record_count":
                    None,

                "error_type":
                    type(error).__name__,

                "error_message":
                    str(error),
            }
        )

        return 4

    except (
        SnapshotStoreError,
        WeatherSnapshotStoreError,
        ValueError,
        OSError,
    ) as error:
        _emit(
            {
                "source_id":
                    None,

                "status":
                    "command_error",

                "previous_snapshot_id":
                    None,

                "active_snapshot_id":
                    None,

                "retrieved_at":
                    None,

                "record_count":
                    None,

                "error_type":
                    type(error).__name__,

                "error_message":
                    str(error),
            }
        )

        return 2

    _emit(
        _serialize(
            outcome
        )
    )

    return _exit_code(
        outcome.status
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
