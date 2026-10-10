"""Explicit local weather evaluation; no persistence, scheduling, or API changes."""

import argparse
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json

from packages.data_sources.providers.open_meteo_forecast import (
    OPEN_METEO_MODEL,
    OpenMeteoForecastClient,
    OpenMeteoForecastQuery,
    WeatherClientError,
    WeatherClientLimits,
    build_open_meteo_source_definition,
)


def _json_scalar(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError("Unsupported probe value.")


def _coordinate(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("Coordinate must be a decimal number.") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make one bounded Open-Meteo request.")
    # Public Aba market coordinates from the existing FEWS pilot.
    parser.add_argument("--latitude", type=_coordinate, default=Decimal("5.10719"))
    parser.add_argument("--longitude", type=_coordinate, default=Decimal("7.37063"))
    parser.add_argument("--days", type=int, default=3, help="UTC days including today, from 1 to 7.")
    parser.add_argument("--max-records", type=int, default=168)
    parser.add_argument("--timeout-seconds", type=float, default=20)
    parser.add_argument("--max-response-bytes", type=int, default=1024 * 1024)
    args = parser.parse_args()
    if not args.live:
        print("Live weather probe disabled. Pass --live for local evaluation; no files will be written.")
        return 0
    try:
        query = OpenMeteoForecastQuery(args.latitude, args.longitude, args.days)
        result = OpenMeteoForecastClient(limits=WeatherClientLimits(
            max_records=args.max_records, timeout_seconds=args.timeout_seconds,
            max_response_bytes=args.max_response_bytes,
        )).fetch(query)
    except (ValueError, WeatherClientError) as error:
        print(f"Weather probe failed: {error}")
        return 2
    print(json.dumps({
        "status": "complete",
        "data_quality": "partial" if result.missing_value_count else "complete",
        "source_type": "weather_forecast",
        "model": OPEN_METEO_MODEL,
        "query_url": query.url(result.requested_from.date()),
        "attribution": build_open_meteo_source_definition().attribution,
        "requests_made": result.requests_made,
        "record_count": len(result.records),
        "missing_value_count": result.missing_value_count,
        "forecast_valid_from": result.requested_from,
        "forecast_valid_to": result.requested_to,
        "retrieved_at": result.retrieved_at,
        "snapshot": asdict(result.snapshot),
        "first_record": asdict(result.records[0]),
    }, default=_json_scalar, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
