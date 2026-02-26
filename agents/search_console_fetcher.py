"""Search Console Fetcher — pulls query data from the Google Search Console API.

Fetches the top queries for a site property, filtered to positions 5–20
(ranking but not dominating). Outputs structured JSON that feeds into
the content planner agent.

Usage:
    python agents/search_console_fetcher.py                # Live API call
    python agents/search_console_fetcher.py --dry-run      # Sample data, no API call
    python agents/search_console_fetcher.py --days 28      # Custom date range (default: 28)
    python agents/search_console_fetcher.py --top 30       # Max queries to fetch (default: 30)
"""

import argparse
import base64
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Sample data for --dry-run mode
SAMPLE_QUERIES: list[dict[str, Any]] = [
    {"query": "python async await tutorial", "clicks": 52, "impressions": 4800, "ctr": 0.0108, "position": 8.3},
    {"query": "fastapi authentication guide", "clicks": 34, "impressions": 3200, "ctr": 0.0106, "position": 11.7},
    {"query": "docker compose best practices", "clicks": 28, "impressions": 5100, "ctr": 0.0055, "position": 14.2},
    {"query": "react server components explained", "clicks": 41, "impressions": 3900, "ctr": 0.0105, "position": 9.1},
    {"query": "github actions ci cd pipeline", "clicks": 19, "impressions": 2700, "ctr": 0.0070, "position": 16.5},
    {"query": "typescript generics examples", "clicks": 63, "impressions": 5500, "ctr": 0.0115, "position": 6.8},
    {"query": "web accessibility checklist 2025", "clicks": 22, "impressions": 3100, "ctr": 0.0071, "position": 12.4},
    {"query": "nextjs vs remix comparison", "clicks": 15, "impressions": 2200, "ctr": 0.0068, "position": 18.1},
    {"query": "python dataclasses tutorial", "clicks": 47, "impressions": 4100, "ctr": 0.0115, "position": 7.5},
    {"query": "tailwind css component patterns", "clicks": 31, "impressions": 3600, "ctr": 0.0086, "position": 10.9},
]


def build_gsc_service() -> Any:
    """Build an authenticated Google Search Console API service client.

    Reads the base64-encoded service account JSON from the
    GOOGLE_SERVICE_ACCOUNT_JSON environment variable.

    Returns:
        A Google API service resource for Search Console.

    Raises:
        ValueError: If required environment variables are missing.
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_json_b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json_b64:
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON not found. "
            "Set it in your .env file (base64-encoded service account JSON)."
        )

    sa_info = json.loads(base64.b64decode(sa_json_b64))
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    )

    return build("searchconsole", "v1", credentials=credentials)


def fetch_queries(
    days: int = 28,
    top_n: int = 30,
    min_position: float = 5.0,
    max_position: float = 20.0,
) -> dict[str, Any]:
    """Fetch top queries from Google Search Console, filtered by position.

    Queries the GSC API for the top queries over the given date range,
    then filters to only those with an average position between
    min_position and max_position (the "striking distance" range).

    Args:
        days: Number of days to look back from today.
        top_n: Maximum number of queries to request from the API.
        min_position: Minimum average position to include (inclusive).
        max_position: Maximum average position to include (inclusive).

    Returns:
        A dict with metadata and a list of filtered query rows, e.g.:
        {
            "site_url": "https://example.com",
            "date_range": {"start": "2025-01-01", "end": "2025-01-28"},
            "total_fetched": 30,
            "total_filtered": 12,
            "position_filter": {"min": 5.0, "max": 20.0},
            "queries": [{"query": "...", "clicks": 0, ...}, ...]
        }

    Raises:
        ValueError: If GSC_PROPERTY_URL is not set.
    """
    site_url = os.getenv("GSC_PROPERTY_URL")
    if not site_url:
        raise ValueError(
            "GSC_PROPERTY_URL not found. Set it in your .env file "
            "(e.g. https://yoursite.com)."
        )

    service = build_gsc_service()

    end_date = date.today() - timedelta(days=3)  # GSC data lags ~3 days
    start_date = end_date - timedelta(days=days)

    print(f"[search_console_fetcher] Fetching top {top_n} queries for {site_url}")
    print(f"[search_console_fetcher] Date range: {start_date} to {end_date}")

    response = service.searchanalytics().query(
        siteUrl=site_url,
        body={
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query"],
            "rowLimit": top_n,
            "type": "web",
        },
    ).execute()

    rows = response.get("rows", [])
    print(f"[search_console_fetcher] Received {len(rows)} rows from API")

    # Parse and filter to striking-distance positions
    queries = []
    for row in rows:
        query_data = {
            "query": row["keys"][0],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": round(row["ctr"], 4),
            "position": round(row["position"], 1),
        }
        if min_position <= query_data["position"] <= max_position:
            queries.append(query_data)

    # Sort by impressions descending (highest visibility potential first)
    queries.sort(key=lambda q: q["impressions"], reverse=True)

    print(f"[search_console_fetcher] {len(queries)} queries in position {min_position}–{max_position}")

    return {
        "site_url": site_url,
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "total_fetched": len(rows),
        "total_filtered": len(queries),
        "position_filter": {"min": min_position, "max": max_position},
        "queries": queries,
    }


def fetch_queries_dry_run() -> dict[str, Any]:
    """Return sample query data without calling the GSC API.

    Useful for testing the pipeline end-to-end without credentials.

    Returns:
        A dict matching the same structure as fetch_queries().
    """
    site_url = os.getenv("GSC_PROPERTY_URL", "https://example.com")
    today = date.today()

    print("[search_console_fetcher] DRY RUN — using sample data")

    return {
        "site_url": site_url,
        "date_range": {
            "start": (today - timedelta(days=28)).isoformat(),
            "end": today.isoformat(),
        },
        "total_fetched": len(SAMPLE_QUERIES),
        "total_filtered": len(SAMPLE_QUERIES),
        "position_filter": {"min": 5.0, "max": 20.0},
        "queries": SAMPLE_QUERIES,
    }


def main() -> None:
    """CLI entry point for the search console fetcher."""
    parser = argparse.ArgumentParser(
        description="Fetch Search Console query data for content planning."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample data instead of calling the GSC API.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=28,
        help="Number of days to look back (default: 28).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Max number of queries to fetch (default: 30).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. If not set, prints to stdout.",
    )
    args = parser.parse_args()

    if args.dry_run:
        result = fetch_queries_dry_run()
    else:
        result = fetch_queries(days=args.days, top_n=args.top)

    output_json = json.dumps(result, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"[search_console_fetcher] Output written to {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
