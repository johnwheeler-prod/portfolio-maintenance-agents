"""Site crawler — fetches and parses XML sitemaps, returns filtered URL lists.

Fetches XML sitemaps, handles both <urlset> and <sitemapindex> formats
(with recursive fetch capped at 2 levels), and filters URLs by freshness
and glob patterns.

Usage:
    python agents/site_crawler.py --dry-run
    python agents/site_crawler.py --dry-run --include "/blog/*"
    python agents/site_crawler.py --sitemap-url https://example.com/sitemap.xml
    python agents/site_crawler.py --sitemap-url https://example.com/sitemap.xml --stale-months 6
"""

import argparse
import gzip
import json
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from fnmatch import fnmatch
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def fetch_sitemap(sitemap_url: str, _depth: int = 0) -> list[dict]:
    """Download and parse an XML sitemap.

    Handles both <urlset> (leaf sitemaps) and <sitemapindex> (index sitemaps
    pointing to sub-sitemaps). Recursion is capped at 2 levels to avoid
    runaway crawling.

    Args:
        sitemap_url: The URL of the sitemap to fetch.
        _depth: Internal recursion depth counter.

    Returns:
        A list of dicts with keys: url, lastmod, priority, changefreq.
    """
    if _depth > 2:
        print(f"[site_crawler] Max depth reached, skipping {sitemap_url}")
        return []

    print(f"[site_crawler] Fetching {sitemap_url}")
    req = Request(
        sitemap_url,
        headers={
            "User-Agent": "AgentOrchestrator-SiteCrawler/1.0",
            "Accept-Encoding": "gzip",
        },
    )
    with urlopen(req, timeout=30) as response:
        raw_bytes = response.read()

    # Decompress if gzip-encoded
    if raw_bytes[:2] == b"\x1f\x8b":
        raw_bytes = gzip.decompress(raw_bytes)

    root = ET.fromstring(raw_bytes)

    # Strip namespace for easier tag matching
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    entries = []

    # Check if this is a sitemap index
    sitemap_tags = root.findall(f"{ns}sitemap")
    if sitemap_tags:
        for sitemap_tag in sitemap_tags:
            loc = sitemap_tag.findtext(f"{ns}loc", "")
            if loc:
                entries.extend(fetch_sitemap(loc.strip(), _depth=_depth + 1))
        return entries

    # Otherwise it's a urlset
    for url_tag in root.findall(f"{ns}url"):
        loc = url_tag.findtext(f"{ns}loc", "")
        if not loc:
            continue
        entries.append({
            "url": loc.strip(),
            "lastmod": url_tag.findtext(f"{ns}lastmod", ""),
            "priority": url_tag.findtext(f"{ns}priority", ""),
            "changefreq": url_tag.findtext(f"{ns}changefreq", ""),
        })

    print(f"[site_crawler] Found {len(entries)} URLs in {sitemap_url}")
    return entries


def fetch_sitemap_dry_run() -> list[dict]:
    """Return 6 sample sitemap entries with mixed freshness dates for testing.

    Returns:
        A list of 6 sample dicts matching the sitemap entry format.
    """
    today = date.today()
    return [
        {
            "url": "https://example.com/blog/python-async-tutorial",
            "lastmod": (today - timedelta(days=180)).isoformat(),
            "priority": "0.8",
            "changefreq": "monthly",
        },
        {
            "url": "https://example.com/blog/react-hooks-guide",
            "lastmod": (today - timedelta(days=10)).isoformat(),
            "priority": "0.8",
            "changefreq": "weekly",
        },
        {
            "url": "https://example.com/about",
            "lastmod": (today - timedelta(days=400)).isoformat(),
            "priority": "0.5",
            "changefreq": "yearly",
        },
        {
            "url": "https://example.com/projects/ml-dashboard",
            "lastmod": "",
            "priority": "0.6",
            "changefreq": "",
        },
        {
            "url": "https://example.com/blog/kubernetes-basics",
            "lastmod": (today - timedelta(days=120)).isoformat(),
            "priority": "0.7",
            "changefreq": "monthly",
        },
        {
            "url": "https://example.com/contact",
            "lastmod": (today - timedelta(days=30)).isoformat(),
            "priority": "0.3",
            "changefreq": "yearly",
        },
    ]


def filter_urls(
    entries: list[dict],
    stale_months: int = 3,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[dict]:
    """Filter sitemap entries by freshness and URL path patterns.

    Default behaviour: include pages whose lastmod is older than stale_months
    OR pages with no lastmod at all (unknown freshness = potentially stale).

    Glob patterns are matched against the URL path using fnmatch.
    Include patterns are applied first, then exclude patterns.

    Args:
        entries: List of sitemap entry dicts.
        stale_months: Pages older than this many months are considered stale.
        include_patterns: If provided, only URLs matching at least one pattern
            are kept. Glob patterns matched against URL path.
        exclude_patterns: URLs matching any of these patterns are removed.
            Glob patterns matched against URL path.

    Returns:
        Filtered list of sitemap entry dicts.
    """
    cutoff = date.today() - timedelta(days=stale_months * 30)
    filtered = []

    for entry in entries:
        path = urlparse(entry["url"]).path

        # Include filter: if patterns given, URL path must match at least one
        if include_patterns:
            if not any(fnmatch(path, pat) for pat in include_patterns):
                continue

        # Exclude filter: if URL path matches any pattern, skip it
        if exclude_patterns:
            if any(fnmatch(path, pat) for pat in exclude_patterns):
                continue

        # Freshness filter: keep stale or unknown-freshness pages
        lastmod = entry.get("lastmod", "")
        if lastmod:
            try:
                # Handle both YYYY-MM-DD and YYYY-MM-DDThh:mm:ss formats
                lastmod_date = date.fromisoformat(lastmod[:10])
                if lastmod_date > cutoff:
                    continue  # Fresh page, skip
            except ValueError:
                pass  # Can't parse date, treat as unknown freshness
        # No lastmod or stale lastmod — include
        filtered.append(entry)

    print(f"[site_crawler] Filtered {len(entries)} -> {len(filtered)} URLs "
          f"(stale_months={stale_months})")
    return filtered


def main() -> None:
    """CLI entry point for the site crawler."""
    parser = argparse.ArgumentParser(
        description="Fetch and filter XML sitemap URLs."
    )
    parser.add_argument(
        "--sitemap-url",
        type=str,
        help="URL of the XML sitemap to fetch.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample sitemap data instead of fetching live.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=None,
        help="Glob pattern to include (matched against URL path). Repeatable.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Glob pattern to exclude (matched against URL path). Repeatable.",
    )
    parser.add_argument(
        "--stale-months",
        type=int,
        default=3,
        help="Pages older than this are considered stale (default: 3).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save filtered URLs to this JSON file.",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.sitemap_url:
        parser.error("--sitemap-url is required unless --dry-run is set")

    # Fetch
    if args.dry_run:
        entries = fetch_sitemap_dry_run()
        print(f"[site_crawler] DRY RUN — {len(entries)} sample entries")
    else:
        entries = fetch_sitemap(args.sitemap_url)

    # Filter
    filtered = filter_urls(
        entries,
        stale_months=args.stale_months,
        include_patterns=args.include,
        exclude_patterns=args.exclude,
    )

    # Output
    print(json.dumps(filtered, indent=2))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2)
        print(f"[site_crawler] Saved to {args.output}")


if __name__ == "__main__":
    main()
