"""PageSpeed Insights Fetcher — retrieves Lighthouse scores via the PSI API.

Calls the Google PageSpeed Insights API v5 to get performance, accessibility,
best practices, and SEO scores for a URL, plus the specific audits that are
failing or below target. Returns a condensed dict ready to feed into Claude.

Usage:
    python agents/pagespeed_fetcher.py --url https://yoursite.com --api-key KEY
    python agents/pagespeed_fetcher.py --dry-run
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]

# Audits with score below this are surfaced as failing
FAILING_THRESHOLD = 0.9


def fetch_pagespeed(url: str, api_key: str, strategy: str = "mobile") -> dict[str, Any]:
    """Fetch PageSpeed Insights data for a URL.

    Calls the PSI API and returns a condensed dict with category scores and
    the failing audits (score < FAILING_THRESHOLD), sorted worst-first.
    Informational audits (score=None) are excluded.

    Args:
        url: The page URL to analyze.
        api_key: Google API key with the PageSpeed Insights API enabled.
        strategy: "mobile" (default) or "desktop". Google ranks mobile-first.

    Returns:
        Dict with keys: url, strategy, scores {category: 0-100}, failing_audits.

    Raises:
        urllib.error.URLError: If the API call fails.
        ValueError: If the API returns an error response body.
    """
    print(f"[pagespeed_fetcher] Fetching PSI data: {url} ({strategy})")

    params = urllib.parse.urlencode(
        [("url", url), ("key", api_key), ("strategy", strategy)]
        + [("category", c) for c in CATEGORIES]
    )
    req = urllib.request.Request(
        f"{PSI_ENDPOINT}?{params}",
        headers={"User-Agent": "AgentOrchestrator-PSI/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    if "error" in data:
        raise ValueError(f"PSI API error: {data['error'].get('message', 'unknown')}")

    lhr = data.get("lighthouseResult", {})
    categories = lhr.get("categories", {})
    audits = lhr.get("audits", {})

    # Category scores: PSI returns 0.0–1.0, convert to 0–100 int
    scores: dict[str, int | None] = {}
    for cat_key, cat_data in categories.items():
        score = cat_data.get("score")
        scores[cat_key] = round(score * 100) if score is not None else None

    # Collect failing audits across all categories, deduplicated
    seen: set[str] = set()
    failing: list[dict[str, Any]] = []
    for cat_key, cat_data in categories.items():
        for ref in cat_data.get("auditRefs", []):
            audit_id = ref["id"]
            if audit_id in seen:
                continue
            seen.add(audit_id)
            audit = audits.get(audit_id, {})
            audit_score = audit.get("score")
            if audit_score is None or audit_score >= FAILING_THRESHOLD:
                continue  # informational or passing
            failing.append({
                "id": audit_id,
                "category": cat_key,
                "title": audit.get("title", audit_id),
                "description": audit.get("description", ""),
                "score": audit_score,
                "display_value": audit.get("displayValue", ""),
            })

    failing.sort(key=lambda a: a["score"])  # worst score first

    print(f"[pagespeed_fetcher] Scores: {scores}")
    print(f"[pagespeed_fetcher] {len(failing)} failing audit(s)")

    return {
        "url": url,
        "strategy": strategy,
        "scores": scores,
        "failing_audits": failing,
    }


def fetch_pagespeed_dry_run() -> dict[str, Any]:
    """Return sample PSI data for dry-run mode without an API call.

    Returns:
        A dict matching the pagespeed_fetcher output schema.
    """
    print("[pagespeed_fetcher] DRY RUN — using sample PSI data")
    return {
        "url": "https://example.com",
        "strategy": "mobile",
        "scores": {
            "performance": 72,
            "accessibility": 91,
            "best-practices": 100,
            "seo": 92,
        },
        "failing_audits": [
            {
                "id": "largest-contentful-paint",
                "category": "performance",
                "title": "Largest Contentful Paint",
                "description": "LCP marks when the main content has likely loaded.",
                "score": 0.56,
                "display_value": "3.2 s",
            },
            {
                "id": "total-blocking-time",
                "category": "performance",
                "title": "Total Blocking Time",
                "description": "TBT measures time the main thread was blocked from responding to input.",
                "score": 0.74,
                "display_value": "290 ms",
            },
            {
                "id": "color-contrast",
                "category": "accessibility",
                "title": "Background and foreground colors do not have sufficient contrast ratio",
                "description": "Low-contrast text is difficult or impossible to read for many users.",
                "score": 0.0,
                "display_value": "",
            },
            {
                "id": "meta-description",
                "category": "seo",
                "title": "Document does not have a meta description",
                "description": "Meta descriptions may appear in search results.",
                "score": 0.0,
                "display_value": "",
            },
        ],
    }


def main() -> None:
    """CLI entry point for the PageSpeed Insights fetcher."""
    parser = argparse.ArgumentParser(
        description="Fetch PageSpeed Insights scores and failing audits for a URL."
    )
    parser.add_argument("--url", type=str, help="URL to analyze.")
    parser.add_argument(
        "--api-key",
        type=str,
        help="Google API key (or set PAGESPEED_API_KEY env var).",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="mobile",
        choices=["mobile", "desktop"],
        help="Lighthouse strategy (default: mobile).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample data, skip API call.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. If not set, prints to stdout.",
    )
    args = parser.parse_args()

    if args.dry_run:
        result = fetch_pagespeed_dry_run()
    else:
        if not args.url:
            parser.error("--url is required unless --dry-run is set")
        api_key = args.api_key or os.environ.get("PAGESPEED_API_KEY", "")
        if not api_key:
            parser.error("Provide --api-key or set the PAGESPEED_API_KEY environment variable")
        result = fetch_pagespeed(args.url, api_key, strategy=args.strategy)

    output_json = json.dumps(result, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"[pagespeed_fetcher] Data written to {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
