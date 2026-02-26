"""Analytics Fetcher — pulls page-level data from Google Search Console.

Unlike search_console_fetcher.py which fetches top queries site-wide,
this module fetches query data for a specific page URL. Used by the
SEO auditor to understand which queries drive traffic to a target page.

Usage:
    python agents/analytics_fetcher.py --page-url https://yoursite.com/page
    python agents/analytics_fetcher.py --dry-run --page-url https://example.com/blog/post
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
SAMPLE_PAGE_DATA: dict[str, Any] = {
    "queries": [
        {"query": "python async await tutorial", "clicks": 52, "impressions": 4800, "ctr": 0.0108, "position": 8.3},
        {"query": "async python example", "clicks": 23, "impressions": 2100, "ctr": 0.011, "position": 12.5},
        {"query": "python asyncio guide", "clicks": 18, "impressions": 1900, "ctr": 0.0095, "position": 15.2},
        {"query": "await keyword python", "clicks": 31, "impressions": 2800, "ctr": 0.0111, "position": 9.7},
        {"query": "python concurrent programming", "clicks": 12, "impressions": 1500, "ctr": 0.008, "position": 18.1},
    ],
    "page_metrics": {
        "total_clicks": 136,
        "total_impressions": 13100,
        "average_ctr": 0.0104,
        "average_position": 11.2,
    },
}


def build_gsc_service() -> Any:
    """Build an authenticated Google Search Console API service client.

    Returns:
        A Google API service resource for Search Console.

    Raises:
        ValueError: If GOOGLE_SERVICE_ACCOUNT_JSON is not set.
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


def fetch_page_queries(
    page_url: str,
    *,
    days: int = 28,
    top_n: int = 20,
) -> dict[str, Any]:
    """Fetch Search Console query data filtered to a specific page.

    Args:
        page_url: The exact URL of the page to fetch data for.
        days: Number of days to look back from today.
        top_n: Maximum number of queries to return.

    Returns:
        A dict with page-level metrics and query breakdown.

    Raises:
        ValueError: If GSC_PROPERTY_URL is not set.
    """
    site_url = os.getenv("GSC_PROPERTY_URL")
    if not site_url:
        raise ValueError("GSC_PROPERTY_URL not found. Set it in your .env file.")

    service = build_gsc_service()

    end_date = date.today() - timedelta(days=3)
    start_date = end_date - timedelta(days=days)

    print(f"[analytics_fetcher] Fetching data for: {page_url}")
    print(f"[analytics_fetcher] Date range: {start_date} to {end_date}")

    response = service.searchanalytics().query(
        siteUrl=site_url,
        body={
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query"],
            "dimensionFilterGroups": [
                {
                    "filters": [
                        {
                            "dimension": "page",
                            "operator": "equals",
                            "expression": page_url,
                        }
                    ]
                }
            ],
            "rowLimit": top_n,
            "type": "web",
        },
    ).execute()

    rows = response.get("rows", [])
    print(f"[analytics_fetcher] Received {len(rows)} query rows")

    queries = []
    total_clicks = 0
    total_impressions = 0

    for row in rows:
        q = {
            "query": row["keys"][0],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "ctr": round(row["ctr"], 4),
            "position": round(row["position"], 1),
        }
        queries.append(q)
        total_clicks += row["clicks"]
        total_impressions += row["impressions"]

    # Sort by impressions descending
    queries.sort(key=lambda q: q["impressions"], reverse=True)

    avg_ctr = round(total_clicks / total_impressions, 4) if total_impressions > 0 else 0.0
    avg_position = round(
        sum(q["position"] for q in queries) / len(queries), 1
    ) if queries else 0.0

    return {
        "page_url": page_url,
        "site_url": site_url,
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "queries": queries,
        "page_metrics": {
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "average_ctr": avg_ctr,
            "average_position": avg_position,
        },
    }


def fetch_page_queries_dry_run(page_url: str) -> dict[str, Any]:
    """Return sample page-level query data without calling the GSC API.

    Args:
        page_url: The page URL to include in the output metadata.

    Returns:
        A dict matching the same structure as fetch_page_queries().
    """
    today = date.today()
    print("[analytics_fetcher] DRY RUN — using sample data")

    return {
        "page_url": page_url,
        "site_url": os.getenv("GSC_PROPERTY_URL", "https://example.com"),
        "date_range": {
            "start": (today - timedelta(days=28)).isoformat(),
            "end": today.isoformat(),
        },
        "queries": SAMPLE_PAGE_DATA["queries"],
        "page_metrics": SAMPLE_PAGE_DATA["page_metrics"],
    }


def main() -> None:
    """CLI entry point for the analytics fetcher."""
    parser = argparse.ArgumentParser(
        description="Fetch Search Console data for a specific page URL."
    )
    parser.add_argument(
        "--page-url",
        type=str,
        required=True,
        help="The exact page URL to fetch data for.",
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
        "--output",
        type=str,
        default=None,
        help="Output file path. If not set, prints to stdout.",
    )
    args = parser.parse_args()

    if args.dry_run:
        result = fetch_page_queries_dry_run(args.page_url)
    else:
        result = fetch_page_queries(args.page_url, days=args.days)

    output_json = json.dumps(result, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"[analytics_fetcher] Output written to {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
