"""Explicitly save a bounded FEWS retrieval, or inspect the last saved snapshot."""

import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path

from packages.data_sources.fews_ingestion import (
    FewsIngestionError, refresh_fews_market_prices, restore_fews_market_prices,
)
from packages.data_sources.providers.fews_http_client import (
    FewsClientError, FewsClientLimits, FewsMarketPriceClient, FewsMarketPriceQuery,
)
from packages.data_sources.registry import SourceRegistry
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore, SnapshotStoreError, effective_fews_query,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--live", action="store_true", help="Retrieve and persist a bounded live result.")
    action.add_argument("--inspect", action="store_true", help="Read the latest local snapshot without HTTP.")
    parser.add_argument("--database", type=Path, default=Path("data/external/fews_ng_white_maize_2025_01.sqlite3"))
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2025, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2025, 1, 31))
    parser.add_argument("--cpcv2", default="R01122AC")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-requests", type=int, default=3)
    parser.add_argument("--max-records", type=int, default=300)
    args = parser.parse_args(argv)
    if not (args.live or args.inspect):
        print("Choose --live to retrieve and save, or --inspect to read saved data.")
        return 0
    try:
        store = FewsSnapshotStore(args.database)
        registry = SourceRegistry()
        fetched = None
        if args.live:
            query = FewsMarketPriceQuery(
                start_date=args.start_date, end_date=args.end_date, cpcv2=args.cpcv2,
            )
            client = FewsMarketPriceClient(limits=FewsClientLimits(
                page_size=args.page_size, max_pages=args.max_pages,
                max_requests=args.max_requests, max_records=args.max_records,
            ))
            fetched = refresh_fews_market_prices(query, store=store, registry=registry, client=client)
        stored = restore_fews_market_prices(store=store, registry=registry)
        status = "stored" if args.live else "loaded"
        if args.live and fetched.snapshot is None:
            status = "no_data_previous_snapshot_retained" if stored else "no_data"
        elif stored is None:
            status = "missing"
        print(json.dumps({
            "status": status,
            "fetched_record_count": len(fetched.records) if fetched is not None else None,
            "snapshot_id": stored.snapshot_id if stored else None,
            "query": effective_fews_query(stored.query) if stored else None,
            "snapshot": asdict(stored.result.snapshot) if stored else None,
            "pages_fetched": fetched.pages_fetched if fetched else None,
            "requests_made": fetched.requests_made if fetched else None,
        }, default=lambda value: value.isoformat(), indent=2))
    except (FewsClientError, FewsIngestionError, SnapshotStoreError, ValueError, OSError) as error:
        print(f"FEWS ingestion failed: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
