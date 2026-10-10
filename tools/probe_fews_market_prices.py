"""Optional, explicitly enabled live probe; never part of the regression suite."""

import argparse
from dataclasses import asdict
from datetime import date
import json

from packages.data_sources.providers.fews_http_client import (
    FewsClientError,
    FewsClientLimits,
    FewsMarketPriceClient,
    FewsMarketPriceQuery,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Enable bounded live HTTP requests.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2025, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2025, 1, 31))
    parser.add_argument("--cpcv2", default="R01122AC", help="Single CPCv2 code or prefix.")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-requests", type=int, default=3)
    parser.add_argument("--max-records", type=int, default=300)
    args = parser.parse_args()
    if not args.live:
        print("Live probe disabled. Pass --live to query FEWS; no files will be written.")
        return 0
    try:
        query = FewsMarketPriceQuery(
            start_date=args.start_date, end_date=args.end_date, cpcv2=args.cpcv2,
        )
        limits = FewsClientLimits(
            page_size=args.page_size, max_pages=args.max_pages,
            max_requests=args.max_requests, max_records=args.max_records,
        )
        result = FewsMarketPriceClient(limits=limits).fetch(query)
    except (ValueError, FewsClientError) as error:
        print(f"FEWS probe failed: {error}")
        return 2
    print(json.dumps({
        "status": "complete" if result.records else "no_data",
        "schedule": "Monthly",
        "pages_fetched": result.pages_fetched,
        "requests_made": result.requests_made,
        "record_count": len(result.records),
        "retrieved_at": result.retrieved_at,
        "snapshot": asdict(result.snapshot) if result.snapshot else None,
        "first_record": asdict(result.records[0]) if result.records else None,
    }, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
