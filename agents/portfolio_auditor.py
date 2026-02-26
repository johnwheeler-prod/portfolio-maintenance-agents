"""Portfolio Freshness Auditor — checks portfolio pages for staleness.

Reads portfolio content from local files or a live URL, compares against
a freshness rubric via Claude, and outputs a structured report with
prioritized findings and draft replacement copy.

Usage:
    python agents/portfolio_auditor.py --content-dir ./portfolio-pages/
    python agents/portfolio_auditor.py --url https://yoursite.com
    python agents/portfolio_auditor.py --dry-run
    python agents/portfolio_auditor.py --dry-run --print-prompt
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Add project root to path so utils are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.claude_client import call_claude_json
from utils.prompt_loader import load_prompt

MEMORY_PATH = Path(__file__).resolve().parent.parent / "memory" / "last_audit_state.json"

# Sample portfolio content for --dry-run mode
SAMPLE_PORTFOLIO_CONTENT = """
PAGE: Home (/)
---
<title>Developer Name — Web Developer & Solutions Architect</title>
<meta name="description" content="Full-stack web developer specializing in modern web applications.">
<h1>Developer Name</h1>
Web Developer & Solutions Architect

I build fast, accessible web applications using modern tools and frameworks.
Currently focused on React, Node.js, and cloud architecture on AWS.

<h2>What I Do</h2>
- Full-stack web development
- Cloud architecture and DevOps
- Performance optimization
- Technical consulting

© 2024 Developer Name. All rights reserved.

PAGE: Projects (/projects)
---
<title>Projects — Developer Name</title>

<h1>Selected Projects</h1>

<h2>E-Commerce Platform Redesign</h2>
Client: RetailCo | Completed: March 2024
Rebuilt their legacy jQuery storefront as a modern Next.js application.
Reduced page load times by 60% and increased mobile conversion by 25%.
Tech stack: Next.js 13, Tailwind CSS, Stripe API, PostgreSQL

<h2>Real-Time Dashboard</h2>
Client: DataMetrics Inc. | Completed: August 2023
Built an analytics dashboard processing 50k events/minute.
Tech stack: React, D3.js, Express, Redis, WebSocket

<h2>CMS Migration</h2>
Client: MediaGroup | Completed: January 2023
Migrated 10,000+ articles from WordPress to a headless CMS.
Tech stack: Contentful, Gatsby, GraphQL, AWS Lambda

<h2>Skills & Technologies</h2>
Languages: JavaScript, TypeScript, Python, SQL
Frontend: React, Next.js, Vue.js, Tailwind CSS
Backend: Node.js, Express, Django, Flask
Databases: PostgreSQL, MongoDB, Redis
Cloud: AWS (EC2, S3, Lambda, CloudFront), Docker
Tools: Git, GitHub Actions, Webpack, Jest

PAGE: About (/about)
---
<title>About — Developer Name</title>

<h1>About Me</h1>
I'm a solutions architect with 8+ years of experience building web applications
for startups and enterprise clients. I specialize in taking complex business
requirements and turning them into clean, maintainable code.

Previously, I worked at TechCorp (2019-2022) where I led the frontend team
and helped scale their SaaS platform from 10k to 100k users.

I hold an AWS Solutions Architect Associate certification (earned 2022).

When I'm not coding, I write about web development best practices on my blog
and contribute to open source projects.
"""


class HTMLTextExtractor(HTMLParser):
    """Simple HTML parser that extracts visible text and structural elements."""

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


def read_portfolio_from_dir(content_dir: str) -> str:
    """Read portfolio content from a directory of local files.

    Reads all .html, .md, and .txt files from the directory and
    concatenates them with page markers.

    Args:
        content_dir: Path to the directory containing portfolio files.

    Returns:
        Concatenated portfolio content as a single string.

    Raises:
        FileNotFoundError: If the directory does not exist.
    """
    dir_path = Path(content_dir)
    if not dir_path.exists():
        raise FileNotFoundError(f"Content directory not found: {dir_path}")

    extensions = {".html", ".htm", ".md", ".txt"}
    files = sorted(f for f in dir_path.iterdir() if f.suffix.lower() in extensions)

    if not files:
        raise ValueError(f"No portfolio files found in {dir_path} (looked for {extensions})")

    print(f"[portfolio_auditor] Reading {len(files)} files from {dir_path}")

    parts = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")

        # Extract text from HTML files
        if file_path.suffix.lower() in (".html", ".htm"):
            extractor = HTMLTextExtractor()
            extractor.feed(content)
            content = extractor.get_text()

        parts.append(f"PAGE: {file_path.name}\n---\n{content}")

    return "\n\n".join(parts)


def read_portfolio_from_url(url: str) -> str:
    """Fetch and extract portfolio content from a live URL.

    Fetches the page HTML and extracts visible text while preserving
    heading structure for analysis.

    Args:
        url: The URL to fetch.

    Returns:
        Extracted text content of the page.

    Raises:
        urllib.error.URLError: If the page cannot be fetched.
    """
    print(f"[portfolio_auditor] Fetching portfolio from: {url}")

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AgentOrchestrator-PortfolioAudit/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        html = response.read().decode("utf-8", errors="replace")

    extractor = HTMLTextExtractor()
    extractor.feed(html)
    content = extractor.get_text()

    max_chars = 20000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[Content truncated for analysis]"
        print(f"[portfolio_auditor] Content truncated to {max_chars} chars")

    print(f"[portfolio_auditor] Extracted {len(content)} chars")
    return f"PAGE: {url}\n---\n{content}"


def load_previous_audit_state() -> str:
    """Load the previous audit state from memory.

    Returns:
        JSON string of the previous state, or "No previous audit data." if none exists.
    """
    if not MEMORY_PATH.exists():
        return "No previous audit data."

    state = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    if not state:
        return "No previous audit data."

    return json.dumps(state, indent=2)


def save_audit_state(report: dict[str, Any]) -> None:
    """Save audit state to memory for trend detection in future runs.

    Stores the current scores so future runs can compute trends
    (improving / declining / stable) across performance, accessibility,
    best practices, and SEO.

    Args:
        report: The audit report dict (portfolio_audit_template schema).
    """
    state = {
        "last_audit_date": report.get("audit_date"),
        "scores": report.get("scores", {}),
        "finding_count": len(report.get("findings", [])),
        "quick_wins": report.get("quick_wins", []),
    }

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"[portfolio_auditor] Audit state saved to {MEMORY_PATH}")


def run_audit(portfolio_content: str) -> dict[str, Any]:
    """Run the legacy portfolio freshness audit via Claude (content-only, no PSI data).

    Kept for backward compatibility. New code should call run_audit_with_psi().

    Args:
        portfolio_content: The portfolio page content to audit.

    Returns:
        Parsed JSON dict of audit findings from Claude.
    """
    previous_state = load_previous_audit_state()
    print(f"[portfolio_auditor] Running freshness audit ({len(portfolio_content)} chars)")

    prompt = load_prompt(
        "portfolio_freshness_template.md",
        current_date=date.today().isoformat(),
        portfolio_content=portfolio_content,
        previous_audit_state=previous_state,
    )

    return call_claude_json(prompt)


def run_audit_with_psi(
    psi_data: dict[str, Any],
    page_content: str,
) -> dict[str, Any]:
    """Run the portfolio audit via Claude using PageSpeed Insights data and page content.

    Loads the previous audit state for score trend detection, then calls Claude
    with PSI scores, failing audits, and page content to produce a prioritized
    report covering performance, accessibility, best practices, and light content
    freshness review.

    Args:
        psi_data: Output dict from pagespeed_fetcher (scores + failing_audits).
        page_content: Extracted text content of the portfolio page.

    Returns:
        Parsed JSON dict of audit findings from Claude.

    Raises:
        json.JSONDecodeError: If Claude's response is not valid JSON.
    """
    previous_state = load_previous_audit_state()
    print(f"[portfolio_auditor] Running PSI-based portfolio audit")

    prompt = load_prompt(
        "portfolio_audit_template.md",
        current_date=date.today().isoformat(),
        pagespeed_data=json.dumps(psi_data, indent=2),
        page_content=page_content,
        previous_audit_state=previous_state,
    )

    return call_claude_json(prompt)


def run_audit_dry_run(portfolio_content: str = "") -> dict[str, Any]:
    """Return a mock PSI-based audit report for dry-run mode.

    Args:
        portfolio_content: Unused in dry-run; kept for signature compatibility.

    Returns:
        A dict matching the portfolio_audit_template JSON schema.
    """
    print("[portfolio_auditor] DRY RUN — generating mock portfolio audit report")

    return {
        "audit_date": date.today().isoformat(),
        "scores": {
            "performance": 72,
            "accessibility": 91,
            "best_practices": 100,
            "seo": 92,
        },
        "score_trends": {
            "performance": "first_run",
            "accessibility": "first_run",
            "best_practices": "first_run",
            "seo": "first_run",
        },
        "summary": (
            "[MOCK] Performance is the weakest category at 72/100, driven by a slow LCP of 3.2s on mobile. "
            "Accessibility is strong at 91 but a colour-contrast failure is holding it back. "
            "First run — no trend data yet."
        ),
        "findings": [
            {
                "category": "performance",
                "severity": "high",
                "title": "Largest Contentful Paint is slow (3.2 s)",
                "audit_id": "largest-contentful-paint",
                "detail": (
                    "[MOCK] LCP of 3.2s exceeds Google's 'needs improvement' threshold of 2.5s. "
                    "For a portfolio, a slow LCP creates a poor first impression and hurts SEO ranking."
                ),
                "current_value": "3.2 s",
                "recommendation": "Audit hero images for size and format. Consider lazy-loading below-fold assets and preloading the LCP element.",
            },
            {
                "category": "accessibility",
                "severity": "high",
                "title": "Insufficient colour contrast ratio",
                "audit_id": "color-contrast",
                "detail": (
                    "[MOCK] One or more text/background colour combinations fall below the WCAG AA "
                    "threshold of 4.5:1. This is a critical accessibility failure and a quick fix."
                ),
                "current_value": "Failing elements detected",
                "recommendation": "Use a contrast checker (e.g. WebAIM) to identify failing elements and darken text or lighten backgrounds to meet 4.5:1.",
            },
            {
                "category": "seo",
                "severity": "medium",
                "title": "Missing meta description on one or more pages",
                "audit_id": "meta-description",
                "detail": "[MOCK] Pages without meta descriptions rely on Google to auto-generate snippets, which is often suboptimal for a portfolio.",
                "current_value": "Meta description absent",
                "recommendation": "Add a unique, keyword-focused meta description (150-160 chars) to every page.",
            },
        ],
        "quick_wins": [
            "Fix colour-contrast failures — high accessibility impact, usually a one-line CSS change",
            "Add meta descriptions to pages missing them — direct SEO improvement",
            "Convert hero images to WebP and add explicit width/height — improves LCP and CLS",
        ],
    }


def main() -> None:
    """CLI entry point for the portfolio auditor."""
    parser = argparse.ArgumentParser(
        description="Audit portfolio pages for freshness and relevance."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--content-dir",
        type=str,
        help="Directory containing portfolio page files (.html, .md, .txt).",
    )
    source.add_argument(
        "--url",
        type=str,
        help="URL of the portfolio site to fetch and audit.",
    )
    source.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample portfolio data, skip live fetches.",
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

    # Load portfolio content
    if args.dry_run:
        portfolio_content = SAMPLE_PORTFOLIO_CONTENT
    elif args.content_dir:
        portfolio_content = read_portfolio_from_dir(args.content_dir)
    elif args.url:
        portfolio_content = read_portfolio_from_url(args.url)
    else:
        print("[portfolio_auditor] Error: provide --content-dir, --url, or --dry-run")
        sys.exit(1)

    # --print-prompt mode
    if args.print_prompt:
        previous_state = load_previous_audit_state()
        prompt = load_prompt(
            "portfolio_freshness_template.md",
            current_date=date.today().isoformat(),
            portfolio_content=portfolio_content,
            previous_audit_state=previous_state,
        )
        print(prompt)
        return

    # Run audit
    if args.dry_run:
        report = run_audit_dry_run(portfolio_content)
    else:
        report = run_audit(portfolio_content)

    # Save audit state for future comparisons
    save_audit_state(report)

    output_json = json.dumps(report, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"[portfolio_auditor] Report written to {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
