"""SEO/AEO Auditor — audits a page for SEO and Answer Engine Optimization.

Takes a page URL, fetches its content and Search Console data, then
sends everything through Claude for a comprehensive audit. Outputs
a structured JSON report with prioritized findings and AEO recommendations.

Usage:
    python agents/seo_auditor.py --page-url https://yoursite.com/blog/post
    python agents/seo_auditor.py --dry-run --page-url https://example.com/blog/post
    python agents/seo_auditor.py --dry-run --page-url https://example.com/blog/post --print-prompt
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Add project root to path so utils are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.analytics_fetcher import fetch_page_queries, fetch_page_queries_dry_run
from utils.claude_client import call_claude_json
from utils.prompt_loader import load_prompt

# Sample page content for --dry-run mode
SAMPLE_PAGE_CONTENT = """
<html>
<head>
    <title>Python Async Await Tutorial - Learn Asynchronous Programming</title>
    <meta name="description" content="Learn Python async/await with practical examples.">
</head>
<body>
    <h1>Python Async Await Tutorial</h1>
    <p>Asynchronous programming in Python allows you to write concurrent code using the async/await syntax introduced in Python 3.5.</p>

    <h2>What is Async/Await?</h2>
    <p>The async and await keywords in Python provide a way to write asynchronous code that looks and behaves like synchronous code. This makes it easier to reason about concurrent operations.</p>

    <h2>Getting Started with asyncio</h2>
    <p>Python's asyncio module is the foundation for async/await. Here's a basic example:</p>
    <pre><code>
import asyncio

async def main():
    print("Hello")
    await asyncio.sleep(1)
    print("World")

asyncio.run(main())
    </code></pre>

    <h2>Common Patterns</h2>
    <p>There are several common patterns when working with async Python code, including gathering tasks and using async context managers.</p>

    <p>Last updated: January 2025</p>
</body>
</html>
"""


class HTMLTextExtractor(HTMLParser):
    """Simple HTML parser that extracts visible text and structural elements.

    Preserves heading tags and basic structure while stripping scripts,
    styles, and non-visible content. Produces a readable text representation
    that Claude can analyze for SEO purposes.
    """

    SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        # Preserve heading structure and meta tags for SEO analysis
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append(f"\n<{tag}>")
        elif tag == "title":
            self._parts.append("\n<title>")
        elif tag == "meta":
            attr_dict = dict(attrs)
            name = attr_dict.get("name", "")
            content = attr_dict.get("content", "")
            if name and content:
                self._parts.append(f'\n<meta name="{name}" content="{content}">')
        elif tag in ("p", "li", "div", "section", "article"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append(f"</{tag}>\n")
        elif tag == "title":
            self._parts.append("</title>\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        """Return the extracted text content."""
        return " ".join(self._parts).strip()


def fetch_page_content(page_url: str) -> str:
    """Fetch and extract readable content from a web page.

    Downloads the HTML of the page and extracts visible text content
    while preserving heading structure and meta tags for SEO analysis.

    Args:
        page_url: The URL of the page to fetch.

    Returns:
        Extracted text content with preserved structural elements.

    Raises:
        urllib.error.URLError: If the page cannot be fetched.
    """
    print(f"[seo_auditor] Fetching page content: {page_url}")

    req = urllib.request.Request(
        page_url,
        headers={"User-Agent": "AgentOrchestrator-SEOAudit/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        html = response.read().decode("utf-8", errors="replace")

    extractor = HTMLTextExtractor()
    extractor.feed(html)
    content = extractor.get_text()

    # Truncate very long pages to stay within token limits
    max_chars = 15000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[Content truncated for analysis]"
        print(f"[seo_auditor] Page content truncated to {max_chars} chars")

    print(f"[seo_auditor] Extracted {len(content)} chars of content")
    return content


def run_audit(
    page_url: str,
    page_content: str,
    search_console_data: dict[str, Any],
) -> dict[str, Any]:
    """Run the SEO/AEO audit by sending data through Claude.

    Loads the seo_audit_template.md prompt, populates it with the page
    content and search data, and calls Claude for analysis.

    Args:
        page_url: The URL of the page being audited.
        page_content: Extracted text content of the page.
        search_console_data: Page-level GSC data from analytics_fetcher.

    Returns:
        Parsed JSON dict of audit findings from Claude.

    Raises:
        json.JSONDecodeError: If Claude's response is not valid JSON.
    """
    print(f"[seo_auditor] Running audit for: {page_url}")

    prompt = load_prompt(
        "seo_audit_template.md",
        page_url=page_url,
        page_content=page_content,
        search_console_data=json.dumps(search_console_data, indent=2),
    )

    return call_claude_json(prompt)


def run_audit_dry_run(
    page_url: str,
    page_content: str,
    search_console_data: dict[str, Any],
) -> dict[str, Any]:
    """Return a mock audit report for dry-run mode.

    Produces a structurally valid response matching the prompt template
    schema so the pipeline can be tested end-to-end without Claude.

    Args:
        page_url: The URL of the page being audited.
        page_content: Extracted text content of the page.
        search_console_data: Page-level GSC data.

    Returns:
        A dict matching the SEO audit JSON schema.
    """
    from datetime import date

    print("[seo_auditor] DRY RUN — generating mock audit report")

    return {
        "audit_date": date.today().isoformat(),
        "page_url": page_url,
        "overall_score": 62,
        "summary": (
            "[MOCK] The page covers the topic adequately but lacks structured "
            "content for featured snippets and PAA. Meta description is too short "
            "and heading hierarchy could be improved for better crawlability."
        ),
        "findings": [
            {
                "id": 1,
                "category": "aeo_readiness",
                "severity": "high",
                "effort": "low",
                "title": "No FAQ or Q&A structure for featured snippets",
                "description": "[MOCK] The page lacks clear question-answer formatting that search engines extract for featured snippets and AI overviews.",
                "recommendation": "Add an FAQ section with concise answers to the top PAA questions.",
                "current_state": "Content is in paragraph form only.",
                "suggested_fix": "Add H2 'Frequently Asked Questions' with H3 questions and short paragraph answers.",
            },
            {
                "id": 2,
                "category": "on_page_seo",
                "severity": "medium",
                "effort": "low",
                "title": "Meta description too short",
                "description": "[MOCK] Current meta description is under 120 characters, missing opportunity to improve CTR.",
                "recommendation": "Expand to 140-155 characters with a clear value proposition and target keyword.",
                "current_state": "Learn Python async/await with practical examples.",
                "suggested_fix": "Master Python async/await with step-by-step examples, common patterns, and best practices for writing fast concurrent code in 2025.",
            },
            {
                "id": 3,
                "category": "schema_markup",
                "severity": "medium",
                "effort": "medium",
                "title": "Missing structured data",
                "description": "[MOCK] No schema markup detected on the page.",
                "recommendation": "Add Article and FAQPage schema markup.",
                "current_state": "No structured data.",
                "suggested_fix": "Add JSON-LD Article schema with dateModified and FAQPage schema for the FAQ section.",
            },
        ],
        "aeo_analysis": {
            "featured_snippet_ready": False,
            "featured_snippet_candidates": [
                {
                    "query": "python async await tutorial",
                    "current_format": "Long-form paragraph without clear definition",
                    "recommended_format": "paragraph",
                    "suggested_content": "[MOCK] Python async/await is a syntax for writing asynchronous code that lets you run multiple operations concurrently. Use 'async def' to define coroutines and 'await' to pause execution until a result is ready.",
                },
            ],
            "paa_targets": [
                {
                    "question": "What is async/await in Python?",
                    "currently_addressed": True,
                    "suggested_answer": "[MOCK] Async/await in Python is a syntax introduced in Python 3.5 for writing asynchronous code. The 'async' keyword defines a coroutine function, and 'await' pauses execution until an awaitable completes.",
                },
                {
                    "question": "Is Python async faster than threading?",
                    "currently_addressed": False,
                    "suggested_answer": "[MOCK] Python async is generally more efficient than threading for I/O-bound tasks because it uses a single thread with cooperative multitasking, avoiding the overhead of thread context switching.",
                },
            ],
            "schema_recommendations": [
                {"type": "Article", "rationale": "Tutorial content with clear authorship", "priority": "high"},
                {"type": "FAQPage", "rationale": "FAQ section with Q&A pairs", "priority": "high"},
            ],
        },
        "quick_wins": [
            "Add FAQ section with top 3 PAA questions and concise answers",
            "Expand meta description to 140-155 characters",
            "Add Article + FAQPage JSON-LD schema markup",
        ],
    }


def main() -> None:
    """CLI entry point for the SEO auditor."""
    parser = argparse.ArgumentParser(
        description="Audit a page for SEO and AEO optimization opportunities."
    )
    parser.add_argument(
        "--page-url",
        type=str,
        required=True,
        help="The URL of the page to audit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample data, skip live API and web fetches.",
    )
    parser.add_argument(
        "--page-content-file",
        type=str,
        default=None,
        help="Read page content from a local file instead of fetching the URL.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. If not set, prints to stdout.",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Print the populated prompt and exit without calling Claude.",
    )
    args = parser.parse_args()

    # Get page content
    if args.dry_run:
        page_content = SAMPLE_PAGE_CONTENT
    elif args.page_content_file:
        page_content = Path(args.page_content_file).read_text(encoding="utf-8")
    else:
        page_content = fetch_page_content(args.page_url)

    # Get search console data
    if args.dry_run:
        gsc_data = fetch_page_queries_dry_run(args.page_url)
    else:
        gsc_data = fetch_page_queries(args.page_url)

    # --print-prompt mode
    if args.print_prompt:
        prompt = load_prompt(
            "seo_audit_template.md",
            page_url=args.page_url,
            page_content=page_content,
            search_console_data=json.dumps(gsc_data, indent=2),
        )
        print(prompt)
        return

    # Run audit
    if args.dry_run:
        report = run_audit_dry_run(args.page_url, page_content, gsc_data)
    else:
        report = run_audit(args.page_url, page_content, gsc_data)

    output_json = json.dumps(report, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"[seo_auditor] Report written to {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
