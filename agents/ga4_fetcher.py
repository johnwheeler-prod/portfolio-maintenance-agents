"""GA4 Fetcher — pulls pageview data from the Google Analytics Data API.

Fetches per-page view counts for blog posts over a rolling window.
Used by the content planner to understand which posts are popular vs.
underperforming, so briefs can be split between reinforcing popular
topics and shoring up weaker ones.

Usage:
    python agents/ga4_fetcher.py                    # Live API call
    python agents/ga4_fetcher.py --dry-run          # Sample data, no API call
    python agents/ga4_fetcher.py --days 90          # Custom date range (default: 90)
    python agents/ga4_fetcher.py --output out.json  # Write to file
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

# Blog path prefix — only pages under this path are included
BLOG_PATH_PREFIX = "/blog/"

# Sample data for --dry-run mode
SAMPLE_GA4_DATA: dict[str, Any] = {
    "date_range": {"start": "2025-01-01", "end": "2025-04-01"},
    "property_id": "000000000",
    "total_posts": 7,
    "posts": [
        {"slug": "most-popular-post",      "path": "/blog/most-popular-post",      "pageviews": 1842},
        {"slug": "second-popular-post",    "path": "/blog/second-popular-post",    "pageviews": 1204},
        {"slug": "third-popular-post",     "path": "/blog/third-popular-post",     "pageviews": 893},
        {"slug": "mid-traffic-post",       "path": "/blog/mid-traffic-post",       "pageviews": 541},
        {"slug": "lower-traffic-post",     "path": "/blog/lower-traffic-post",     "pageviews": 387},
        {"slug": "low-traffic-post",       "path": "/blog/low-traffic-post",       "pageviews": 214},
        {"slug": "least-popular-post",     "path": "/blog/least-popular-post",     "pageviews": 98},
    ],
}


def fetch_pageviews(
    days: int = 90,
    blog_prefix: str = BLOG_PATH_PREFIX,
) -> dict[str, Any]:
    """Fetch per-page pageview counts from the GA4 Data API.

    Queries the GA4 Data API for screenPageViews by pagePath over the
    given date range, filtered to paths under blog_prefix. Results are
    sorted by pageviews descending so the most-read posts appear first.

    Args:
        days: Number of days to look back from today (default: 90).
        blog_prefix: Only include pages whose path starts with this prefix.

    Returns:
        A dict with metadata and a list of post pageview records, e.g.:
        {
            "date_range": {"start": "2025-01-01", "end": "2025-04-01"},
            "property_id": "123456789",
            "total_posts": 7,
            "posts": [
                {"slug": "my-post", "path": "/blog/my-post", "pageviews": 1234},
                ...
            ]
        }

    Raises:
        ValueError: If GA4_PROPERTY_ID or GOOGLE_SERVICE_ACCOUNT_JSON are missing.
        ImportError: If google-analytics-data is not installed.
    """
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            FilterExpression,
            Filter,
            Metric,
            OrderBy,
            RunReportRequest,
        )
        from google.oauth2 import service_account
    except ImportError as exc:
        raise ImportError(
            "google-analytics-data is required for GA4 fetching. "
            "Run: pip install google-analytics-data"
        ) from exc

    property_id = os.getenv("GA4_PROPERTY_ID")
    if not property_id:
        raise ValueError(
            "GA4_PROPERTY_ID not found. Set it in your .env file "
            "(numeric property ID from Analytics Admin > Property details)."
        )

    sa_json_b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json_b64:
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON not found. "
            "Set it in your .env file (base64-encoded service account JSON)."
        )

    sa_info = json.loads(base64.b64decode(sa_json_b64))
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    client = BetaAnalyticsDataClient(credentials=credentials)

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    print(f"[ga4_fetcher] Fetching pageviews for property {property_id}")
    print(f"[ga4_fetcher] Date range: {start_date} to {end_date}")
    print(f"[ga4_fetcher] Filtering to paths starting with: {blog_prefix}")

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.BEGINS_WITH,
                    value=blog_prefix,
                ),
            )
        ),
        order_bys=[OrderBy(
            metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
            desc=True,
        )],
        limit=100,
    )

    response = client.run_report(request)
    print(f"[ga4_fetcher] Received {len(response.rows)} rows from API")

    posts = []
    for row in response.rows:
        path = row.dimension_values[0].value
        pageviews = int(row.metric_values[0].value)
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        posts.append({"slug": slug, "path": path, "pageviews": pageviews})

    return {
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "property_id": property_id,
        "total_posts": len(posts),
        "posts": posts,
    }


def fetch_pageviews_dry_run() -> dict[str, Any]:
    """Return sample GA4 pageview data without calling the API.

    Useful for testing the content pipeline end-to-end without credentials.

    Returns:
        A dict matching the same structure as fetch_pageviews().
    """
    print("[ga4_fetcher] DRY RUN — using sample data")
    return SAMPLE_GA4_DATA


def main() -> None:
    """CLI entry point for the GA4 fetcher."""
    parser = argparse.ArgumentParser(
        description="Fetch GA4 pageview data for content planning."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample data instead of calling the GA4 API.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days to look back (default: 90).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. If not set, prints to stdout.",
    )
    args = parser.parse_args()

    if args.dry_run:
        result = fetch_pageviews_dry_run()
    else:
        result = fetch_pageviews(days=args.days)

    output_json = json.dumps(result, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"[ga4_fetcher] Output written to {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
