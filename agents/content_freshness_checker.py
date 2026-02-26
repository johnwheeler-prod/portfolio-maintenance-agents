"""Content Freshness Checker — flags stale pages for content updates.

Takes a filtered list of pages from site_crawler (those not updated in 10+
months), fetches each page's content, and asks Claude to identify what's
outdated and what specific updates would improve it.

Runs as a sub-agent within the content pipeline alongside content_planner:
- content_planner answers "what new content should I create?"
- content_freshness_checker answers "what existing content needs refreshing?"

Usage:
    python agents/content_freshness_checker.py --pages stale_pages.json
    python agents/content_freshness_checker.py --dry-run
"""

import argparse
import json
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.claude_client import call_claude_json
from utils.prompt_loader import load_prompt

# Per-page content limit sent to Claude — keeps tokens manageable
MAX_CONTENT_CHARS = 8000
# Max pages per run to control API cost
MAX_PAGES = 10


class _TextExtractor(HTMLParser):
    """Minimal HTML parser that extracts visible text."""

    _SKIP = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._depth: int = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        """Return extracted text joined by spaces."""
        return " ".join(self._parts)


def _fetch_page_text(url: str) -> str:
    """Fetch a URL and return its visible text content, truncated to MAX_CONTENT_CHARS.

    Args:
        url: The page URL to fetch.

    Returns:
        Extracted text content.

    Raises:
        urllib.error.URLError: If the page cannot be fetched.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AgentOrchestrator-FreshnessCheck/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    extractor = _TextExtractor()
    extractor.feed(html)
    text = extractor.get_text()
    return text[:MAX_CONTENT_CHARS] if len(text) > MAX_CONTENT_CHARS else text


def _months_since(lastmod: str) -> int | None:
    """Return whole months since a lastmod date string.

    Args:
        lastmod: ISO date string (YYYY-MM-DD or YYYY-MM-DDThh:mm:ss).

    Returns:
        Integer months elapsed, or None if the date cannot be parsed.
    """
    if not lastmod:
        return None
    try:
        lastmod_date = date.fromisoformat(lastmod[:10])
        return int((date.today() - lastmod_date).days / 30)
    except ValueError:
        return None


def check_freshness(
    stale_pages: list[dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Identify outdated content on stale pages using Claude.

    Fetches each page's HTML content, then calls Claude with the
    content_freshness_template to get per-page findings and update suggestions.
    Caps at MAX_PAGES to keep API cost bounded.

    Args:
        stale_pages: Sitemap entry dicts (url, lastmod, priority, changefreq)
            already filtered to pages older than the staleness threshold.
        dry_run: If True, use stub page content instead of live fetches.

    Returns:
        Structured JSON report with per-page findings and an overall summary.
    """
    pages_to_check = stale_pages[:MAX_PAGES]
    if len(stale_pages) > MAX_PAGES:
        print(
            f"[freshness_checker] Capping at {MAX_PAGES} pages "
            f"({len(stale_pages)} stale found)"
        )

    pages_data: list[dict[str, Any]] = []
    for entry in pages_to_check:
        url = entry["url"]
        lastmod = entry.get("lastmod", "")
        months = _months_since(lastmod)

        if dry_run:
            content = f"[DRY RUN stub content for {url}]"
        else:
            try:
                print(f"[freshness_checker] Fetching {url}")
                content = _fetch_page_text(url)
            except Exception as exc:
                print(f"[freshness_checker] Skipping {url}: {exc}")
                continue

        pages_data.append({
            "url": url,
            "last_modified": lastmod or "unknown",
            "months_since_update": months,
            "content_excerpt": content,
        })

    if not pages_data:
        return {
            "audit_date": date.today().isoformat(),
            "pages_reviewed": 0,
            "summary": "No stale pages could be fetched for review.",
            "stale_pages": [],
        }

    print(f"[freshness_checker] Sending {len(pages_data)} page(s) to Claude")

    prompt = load_prompt(
        "content_freshness_template.md",
        current_date=date.today().isoformat(),
        stale_pages_json=json.dumps(pages_data, indent=2),
    )

    return call_claude_json(prompt, max_tokens=8192)


def check_freshness_dry_run() -> dict[str, Any]:
    """Return a sample freshness report without API calls.

    Returns:
        A dict matching the content freshness report schema.
    """
    print("[freshness_checker] DRY RUN — generating sample freshness report")
    return {
        "audit_date": date.today().isoformat(),
        "pages_reviewed": 2,
        "summary": (
            "[MOCK] 2 pages flagged for refresh. The Python async tutorial references "
            "deprecated syntax, and the about page has stale year references."
        ),
        "stale_pages": [
            {
                "url": "https://example.com/blog/python-async-tutorial",
                "last_modified": "2024-08-12",
                "months_since_update": 18,
                "update_priority": "high",
                "issues": [
                    {
                        "category": "deprecated_tech",
                        "description": (
                            "[MOCK] References @asyncio.coroutine, deprecated in "
                            "Python 3.10 and removed in 3.11."
                        ),
                        "suggested_update": (
                            "Replace @asyncio.coroutine with async def throughout all examples."
                        ),
                    }
                ],
            },
            {
                "url": "https://example.com/about",
                "last_modified": "2023-10-01",
                "months_since_update": 28,
                "update_priority": "medium",
                "issues": [
                    {
                        "category": "date_reference",
                        "description": "[MOCK] Bio mentions 2024 as the current year.",
                        "suggested_update": "Update year references and add 2025–2026 activity.",
                    }
                ],
            },
        ],
    }


def main() -> None:
    """CLI entry point for the content freshness checker."""
    parser = argparse.ArgumentParser(
        description="Check stale site pages for content that needs updating."
    )
    parser.add_argument(
        "--pages",
        type=str,
        help="Path to JSON file of stale pages (output of site_crawler --stale-months 10).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample data, skip live fetches and Claude API call.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. If not set, prints to stdout.",
    )
    args = parser.parse_args()

    if args.dry_run:
        result = check_freshness_dry_run()
    elif args.pages:
        pages = json.loads(Path(args.pages).read_text(encoding="utf-8"))
        result = check_freshness(pages)
    else:
        parser.error("--pages or --dry-run is required")

    output_json = json.dumps(result, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"[freshness_checker] Report written to {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
