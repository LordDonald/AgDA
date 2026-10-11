"""Explicitly save a bounded weather forecast, or inspect the last saved snapshot."""

import argparse
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from packages.data_sources.providers.open_meteo_forecast import (
    OpenMeteoForecastClient,
    OpenMeteoForecastQuery,
    WeatherClientError,
    WeatherClientLimits,
)
from packages.data_sources.registry import (
    SourceRegistry,
)
from packages.data_sources.weather_ingestion import (
    WeatherIngestionError,
    refresh_weather_forecast,
    restore_weather_forecast,
)
from packages.data_sources.weather_snapshot_store import (
    WeatherSnapshotStore,
    WeatherSnapshotStoreError,
    effective_open_meteo_query,
)


def _coordinate(
    value: str,
) -> Decimal:

    try:
        return Decimal(
            value
        )
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError(
            "Coordinate must be a decimal number."
        ) from error


def main(
    argv=None,
) -> int:

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    action = (
        parser.add_mutually_exclusive_group()
    )

    action.add_argument(
        "--live",
        action="store_true",
        help=(
            "Retrieve and persist one bounded "
            "Open-Meteo forecast."
        ),
    )

    action.add_argument(
        "--inspect",
        action="store_true",
        help=(
            "Read the latest local weather "
            "snapshot without HTTP."
        ),
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=Path(
            "data/external/"
            "weather_aba_forecast.sqlite3"
        ),
    )

    parser.add_argument(
        "--latitude",
        type=_coordinate,
        default=Decimal("5.10719"),
    )

    parser.add_argument(
        "--longitude",
        type=_coordinate,
        default=Decimal("7.37063"),
    )

    parser.add_argument(
        "--days",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--max-records",
        type=int,
        default=168,
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

    args = parser.parse_args(
        argv
    )

    if not (
        args.live
        or args.inspect
    ):
        print(
            "Choose --live to retrieve and save, "
            "or --inspect to read saved data."
        )
        return 0

    try:
        store = WeatherSnapshotStore(
            args.database
        )

        registry = SourceRegistry()

        fetched = None

        if args.live:
            query = OpenMeteoForecastQuery(
                latitude=
                    args.latitude,
                longitude=
                    args.longitude,
                forecast_days=
                    args.days,
            )

            client = OpenMeteoForecastClient(
                limits=WeatherClientLimits(
                    max_records=
                        args.max_records,
                    timeout_seconds=
                        args.timeout_seconds,
                    max_response_bytes=
                        args.max_response_bytes,
                )
            )

            fetched = refresh_weather_forecast(
                query,
                store=store,
                registry=registry,
                client=client,
            )

        stored = restore_weather_forecast(
            store=store,
            registry=registry,
        )

        status = (
            "stored"
            if args.live
            else "loaded"
        )

        if stored is None:
            status = "missing"

        print(
            json.dumps(
                {
                    "status":
                        status,
                    "fetched_record_count": (
                        len(
                            fetched.records
                        )
                        if fetched is not None
                        else None
                    ),
                    "snapshot_id": (
                        stored.snapshot_id
                        if stored
                        else None
                    ),
                    "query": (
                        effective_open_meteo_query(
                            stored.query
                        )
                        if stored
                        else None
                    ),
                    "snapshot": (
                        asdict(
                            stored.result.snapshot
                        )
                        if stored
                        else None
                    ),
                    "requests_made": (
                        fetched.requests_made
                        if fetched
                        else None
                    ),
                    "missing_value_count": (
                        fetched.missing_value_count
                        if fetched
                        else None
                    ),
                },
                default=lambda value:
                    value.isoformat(),
                indent=2,
            )
        )

    except (
        WeatherClientError,
        WeatherIngestionError,
        WeatherSnapshotStoreError,
        ValueError,
        OSError,
    ) as error:
        print(
            f"Weather ingestion failed: {error}"
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
