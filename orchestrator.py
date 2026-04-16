"""Orchestrator — chains agents together into pipelines.

The orchestrator is the main entry point for running agent pipelines.
It coordinates data flow between agents: each agent's JSON output becomes
the next agent's input. No agent calls another agent directly.

Usage:
    python orchestrator.py content-pipeline                # Run live
    python orchestrator.py content-pipeline --dry-run      # Sample data, no API calls
    python orchestrator.py content-pipeline --dry-run --create-issue  # Also open GitHub issue
    python orchestrator.py seo-audit --page-url https://yoursite.com/page
    python orchestrator.py seo-audit --dry-run --page-url https://example.com/blog/post
    python orchestrator.py portfolio-audit --dry-run
    python orchestrator.py portfolio-audit --url https://yoursite.com
    python orchestrator.py site-audit --sitemap-url https://example.com/sitemap.xml
    python orchestrator.py site-audit --dry-run
    python orchestrator.py apply-fixes --dry-run
    python orchestrator.py apply-fixes --categories robots_txt --portfolio-dir ../your-portfolio-repo
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agents.analytics_fetcher import fetch_page_queries, fetch_page_queries_dry_run
from agents.ga4_fetcher import fetch_pageviews, fetch_pageviews_dry_run
from agents.content_freshness_checker import check_freshness, check_freshness_dry_run
from agents.content_planner import generate_briefs, save_briefs
from agents.pagespeed_fetcher import fetch_pagespeed, fetch_pagespeed_dry_run
from agents.search_console_fetcher import fetch_queries, fetch_queries_dry_run
from agents.portfolio_auditor import (
    read_portfolio_from_url,
    run_audit_with_psi,
    run_audit_dry_run as run_portfolio_audit_dry_run,
    save_audit_state,
    SAMPLE_PORTFOLIO_CONTENT,
)
from agents.fix_applier import (
    fix_build_errors,
    generate_fixes,
    generate_fixes_dry_run,
    generate_portfolio_fixes,
    generate_portfolio_fixes_dry_run,
    PORTFOLIO_CATEGORY_LABELS,
)
from agents.seo_auditor import (
    fetch_page_content,
    run_audit,
    run_audit_dry_run,
    SAMPLE_PAGE_CONTENT,
)
from agents.site_crawler import (
    fetch_sitemap,
    fetch_sitemap_dry_run,
    filter_urls,
)


def run_content_pipeline(
    *,
    dry_run: bool = False,
    days: int = 28,
    top_n: int = 30,
    sitemap_url: str | None = None,
    output_dir: str | None = None,
    create_issue: bool = False,
    portfolio_dir: str | None = None,
) -> dict[str, Any]:
    """Run the full content planning pipeline with two parallel sub-agents.

    Steps:
        1. Fetch query data from Google Search Console (or sample data)
        1b. Fetch GA4 pageview data (optional, skipped if GA4_PROPERTY_ID unset)
        2a. content_planner — generate up to 4 new content briefs with internal
            linking (capped so total drafts in portfolio never exceeds 4)
        2b. content_freshness_checker — flag pages ≥ 10 months old for refresh
        3. Save both outputs
        4. Optionally create GitHub issues for both sub-agent outputs

    Draft cap: when portfolio_dir is provided, the pipeline counts existing
    draft .md files in src/content/blog/drafts/ and only generates enough new
    briefs to bring the total to 4. If 4 drafts already exist, the content
    planner step is skipped entirely.

    The two sub-agents are independent: content_planner uses GSC query data to
    identify new content opportunities; content_freshness_checker uses the
    sitemap to find stale existing pages that need updating.

    Args:
        dry_run: Use sample data and skip live API calls.
        days: Lookback window for GSC data in days.
        top_n: Max queries to fetch from GSC.
        sitemap_url: Sitemap URL for the freshness check. If omitted, the
            freshness step runs in dry-run mode with sample data.
        output_dir: Custom output directory path.
        create_issue: Whether to create GitHub issues with findings.

    Returns:
        A dict with pipeline results including file paths and both sub-agent outputs.
    """
    print("=" * 60)
    print("PIPELINE: Content Planning")
    print("=" * 60)

    # --- Step 1: Fetch Search Console data ---
    print("\n--- Step 1: Fetch Search Console Data ---")
    if dry_run:
        gsc_data = fetch_queries_dry_run()
    else:
        gsc_data = fetch_queries(days=days, top_n=top_n)

    query_count = len(gsc_data.get("queries", []))
    if query_count == 0 and not dry_run:
        print("[orchestrator] No GSC queries found — loading seed queries")
        gsc_data = _load_seed_queries()
        query_count = len(gsc_data.get("queries", []))
    print(f"[orchestrator] {query_count} queries ready for analysis")

    today = date.today().isoformat()
    intermediate_dir = Path(output_dir) if output_dir else Path("outputs") / "content_briefs" / today
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    gsc_path = intermediate_dir / "gsc_data.json"
    gsc_path.write_text(json.dumps(gsc_data, indent=2), encoding="utf-8")
    print(f"[orchestrator] GSC data saved to {gsc_path}")

    # --- Step 1b: Fetch GA4 pageview data ---
    # Used to split briefs between reinforcing popular topics and shoring up weak ones.
    # Gracefully skipped if GA4_PROPERTY_ID is not configured.
    print("\n--- Step 1b: Fetch GA4 Pageview Data ---")
    ga4_data: dict[str, Any] | None = None
    if dry_run:
        ga4_data = fetch_pageviews_dry_run()
    elif os.getenv("GA4_PROPERTY_ID"):
        try:
            ga4_data = fetch_pageviews()
            ga4_path = intermediate_dir / "ga4_data.json"
            ga4_path.write_text(json.dumps(ga4_data, indent=2), encoding="utf-8")
            print(f"[orchestrator] {len(ga4_data.get('posts', []))} post(s) → {ga4_path}")
        except Exception as exc:
            print(f"[orchestrator] GA4 fetch failed ({exc}) — continuing without pageview data")
            ga4_data = None
    else:
        print("[orchestrator] GA4_PROPERTY_ID not set — skipping pageview fetch")

    # Fetch sitemap once — used by both sub-agents below
    sitemap_entries: list[dict[str, Any]] = []
    if sitemap_url and not dry_run:
        print(f"[orchestrator] Fetching sitemap: {sitemap_url}")
        sitemap_entries = fetch_sitemap(sitemap_url)
        print(f"[orchestrator] {len(sitemap_entries)} sitemap entries loaded")

    # --- Draft cap check (before Step 2a) ---
    # Never exceed 4 drafts in the portfolio at once. Count what's already there
    # and only generate enough new briefs to fill the remaining slots.
    DRAFT_CAP = 4
    STALE_DAYS = 60
    brief_slots = DRAFT_CAP  # default: generate a full set
    if portfolio_dir and not dry_run:
        existing_draft_count = _count_existing_drafts(portfolio_dir)
        brief_slots = max(0, DRAFT_CAP - existing_draft_count)
        print(
            f"[orchestrator] Draft cap check: {existing_draft_count} existing draft(s), "
            f"{brief_slots} slot(s) available (cap={DRAFT_CAP})"
        )
        _warn_stale_drafts(portfolio_dir, stale_days=STALE_DAYS)
        if brief_slots == 0:
            print(
                "[orchestrator] Draft cap reached — skipping content brief generation. "
                "Publish or delete existing drafts before the next run."
            )

    # --- Step 2a: Generate content briefs (content_planner sub-agent) ---
    print("\n--- Step 2a: Generate Content Briefs (content_planner) ---")
    if brief_slots == 0 and not dry_run:
        print("[orchestrator] Skipping — no draft slots available")
        briefs: dict[str, Any] = {"opportunities": [], "internal_linking_opportunities": []}
    elif dry_run:
        print("[orchestrator] DRY RUN — skipping Claude API call")
        briefs = _mock_briefs(gsc_data)
    else:
        existing_posts = _extract_blog_posts(sitemap_entries)
        briefs = generate_briefs(gsc_data, existing_posts=existing_posts, count=brief_slots, ga4_data=ga4_data)

    briefs_path = save_briefs(briefs, output_dir=str(intermediate_dir))
    print(f"[orchestrator] {len(briefs.get('opportunities', []))} briefs → {briefs_path}")

    # --- Step 2b: Check stale pages (content_freshness_checker sub-agent) ---
    print("\n--- Step 2b: Check Stale Content (content_freshness_checker) ---")
    freshness_report: dict[str, Any] | None = None
    freshness_path: Path | None = None

    if dry_run:
        print("[orchestrator] DRY RUN — using sample freshness data")
        freshness_report = check_freshness_dry_run()
    elif sitemap_entries:
        stale_pages = filter_urls(sitemap_entries, stale_months=10)
        if stale_pages:
            freshness_report = check_freshness(stale_pages)
        else:
            print("[orchestrator] No pages ≥ 10 months old — freshness check skipped")
    else:
        print("[orchestrator] No --sitemap-url provided — freshness check skipped")

    if freshness_report is not None:
        freshness_path = intermediate_dir / "freshness_report.json"
        freshness_path.write_text(json.dumps(freshness_report, indent=2), encoding="utf-8")
        stale_count = len(freshness_report.get("stale_pages", []))
        print(f"[orchestrator] {stale_count} stale page(s) flagged → {freshness_path}")

    # --- Step 3: Create GitHub issues (optional) ---
    briefs_issue_url = None
    freshness_issue_url = None
    if create_issue:
        print("\n--- Step 3: Create GitHub Issues ---")
        briefs_issue_url = create_github_issue(briefs)
        if freshness_report is not None:
            freshness_issue_url = create_freshness_github_issue(freshness_report)

    # --- Step 4: Write draft files to portfolio (optional) ---
    draft_paths: list[str] = []
    if portfolio_dir and not dry_run:
        print("\n--- Step 4: Write Portfolio Drafts ---")
        draft_paths = create_portfolio_drafts(briefs, portfolio_dir)
        print(f"[orchestrator] {len(draft_paths)} draft(s) written to {portfolio_dir}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Queries analyzed: {query_count}")
    print(f"  New content briefs: {len(briefs.get('opportunities', []))}")
    stale = len(freshness_report.get("stale_pages", [])) if freshness_report else "skipped"
    print(f"  Stale pages flagged: {stale}")
    print(f"  Drafts written: {len(draft_paths) if draft_paths else 'skipped'}")
    if briefs_issue_url:
        print(f"  Briefs issue: {briefs_issue_url}")
    if freshness_issue_url:
        print(f"  Freshness issue: {freshness_issue_url}")
    print("=" * 60)

    return {
        "pipeline": "content-pipeline",
        "gsc_data_path": str(gsc_path),
        "briefs_path": str(briefs_path),
        "briefs": briefs,
        "freshness_report_path": str(freshness_path) if freshness_path else None,
        "freshness_report": freshness_report,
        "briefs_issue_url": briefs_issue_url,
        "freshness_issue_url": freshness_issue_url,
    }


def create_github_issue(briefs: dict[str, Any]) -> str | None:
    """Create a GitHub issue summarizing the content opportunities.

    Uses the `gh` CLI tool which must be installed and authenticated.
    Falls back gracefully if `gh` is not available.

    Args:
        briefs: The content briefs dict from generate_briefs().

    Returns:
        The URL of the created issue, or None if creation failed.
    """
    opportunities = briefs.get("opportunities", [])
    if not opportunities:
        print("[orchestrator] No opportunities to report — skipping issue creation")
        return None

    today = date.today().isoformat()
    title = f"Content Opportunities — {today}"

    # Build issue body as markdown
    lines = [
        f"## Weekly Content Opportunities — {today}",
        "",
        f"**{len(opportunities)} opportunities** identified from Search Console data.",
        "",
    ]

    for opp in opportunities:
        lines.extend([
            f"### #{opp.get('rank', '?')}: {opp.get('target_query', 'Unknown')}",
            "",
            f"- **Position:** {opp.get('current_position', 'N/A')} | "
            f"**Impressions:** {opp.get('impressions', 'N/A')} | "
            f"**CTR:** {opp.get('ctr', 'N/A')}",
            f"- **Intent:** {opp.get('search_intent', 'N/A')}",
            f"- **Action:** {opp.get('content_action', 'N/A')}",
            f"- **Suggested title:** {opp.get('suggested_title', 'N/A')}",
            "",
            opp.get("priority_rationale", ""),
            "",
        ])

    lines.append("---")
    lines.append("*Generated by the content planning pipeline.*")
    body = "\n".join(lines)

    try:
        result = subprocess.run(
            [
                "gh", "issue", "create",
                "--title", title,
                "--body", body,
                "--label", "content-opportunity",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            issue_url = result.stdout.strip()
            print(f"[orchestrator] GitHub issue created: {issue_url}")
            return issue_url
        else:
            print(f"[orchestrator] GitHub issue creation failed: {result.stderr.strip()}")
            return None

    except FileNotFoundError:
        print("[orchestrator] `gh` CLI not found — skipping issue creation")
        print("[orchestrator] Install with: brew install gh")
        return None
    except subprocess.TimeoutExpired:
        print("[orchestrator] GitHub issue creation timed out")
        return None


def create_freshness_github_issue(report: dict[str, Any]) -> str | None:
    """Create a GitHub issue summarizing stale-content findings.

    Args:
        report: The freshness report dict from content_freshness_checker.

    Returns:
        The URL of the created issue, or None if creation failed.
    """
    stale_pages = report.get("stale_pages", [])
    if not stale_pages:
        print("[orchestrator] No stale pages to report — skipping freshness issue")
        return None

    today = date.today().isoformat()
    title = f"Stale Content Refresh — {today}"

    lines = [
        f"## Stale Content Audit — {today}",
        "",
        f"**Pages reviewed:** {report.get('pages_reviewed', 0)} | "
        f"**Pages flagged:** {len(stale_pages)}",
        "",
        f"> {report.get('summary', '')}",
        "",
    ]

    for page in stale_pages:
        priority = page.get("update_priority", "?")
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        months = page.get("months_since_update", "?")
        lines.extend([
            f"### {emoji} {page.get('url', 'Unknown URL')}",
            f"Last modified: {page.get('last_modified', 'unknown')} ({months} months ago)",
            "",
        ])
        for issue in page.get("issues", []):
            lines.extend([
                f"- **{issue.get('category', '?')}:** {issue.get('description', '')}",
                f"  → {issue.get('suggested_update', '')}",
                "",
            ])

    lines.append("---")
    lines.append("*Generated by the content freshness checker (content pipeline).*")
    body = "\n".join(lines)

    try:
        result = subprocess.run(
            [
                "gh", "issue", "create",
                "--title", title,
                "--body", body,
                "--label", "content-opportunity",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            issue_url = result.stdout.strip()
            print(f"[orchestrator] Freshness issue created: {issue_url}")
            return issue_url
        else:
            print(f"[orchestrator] Freshness issue creation failed: {result.stderr.strip()}")
            return None
    except FileNotFoundError:
        print("[orchestrator] `gh` CLI not found — skipping issue creation")
        return None
    except subprocess.TimeoutExpired:
        print("[orchestrator] Freshness issue creation timed out")
        return None


def run_seo_audit(
    *,
    page_url: str,
    dry_run: bool = False,
    days: int = 28,
    output_dir: str | None = None,
    create_issue: bool = False,
) -> dict[str, Any]:
    """Run the SEO/AEO audit pipeline for a single page.

    Steps:
        1. Fetch the page content (or use sample content)
        2. Fetch Search Console data for the page
        3. Run Claude audit against SEO/AEO rubric
        4. Save the report
        5. Optionally create a GitHub issue with findings

    Args:
        page_url: The URL of the page to audit.
        dry_run: Use sample data and skip live API calls.
        days: Lookback window for GSC data in days.
        output_dir: Custom output directory path.
        create_issue: Whether to create a GitHub issue with findings.

    Returns:
        A dict with pipeline results including file paths and report data.
    """
    print("=" * 60)
    print("PIPELINE: SEO/AEO Audit")
    print(f"TARGET:   {page_url}")
    print("=" * 60)

    # --- Step 1: Fetch page content ---
    print("\n--- Step 1: Fetch Page Content ---")
    if dry_run:
        print("[orchestrator] DRY RUN — using sample page content")
        page_content = SAMPLE_PAGE_CONTENT
    else:
        page_content = fetch_page_content(page_url)

    # --- Step 2: Fetch Search Console data for this page ---
    print("\n--- Step 2: Fetch Search Console Data ---")
    if dry_run:
        gsc_data = fetch_page_queries_dry_run(page_url)
    else:
        gsc_data = fetch_page_queries(page_url, days=days)

    query_count = len(gsc_data.get("queries", []))
    print(f"[orchestrator] {query_count} queries found for this page")

    # Save intermediate data
    today = date.today().isoformat()
    intermediate_dir = Path(output_dir) if output_dir else Path("outputs") / "seo_audits" / today
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    gsc_path = intermediate_dir / "gsc_data.json"
    gsc_path.write_text(json.dumps(gsc_data, indent=2), encoding="utf-8")

    content_path = intermediate_dir / "page_content.txt"
    content_path.write_text(page_content, encoding="utf-8")
    print(f"[orchestrator] Intermediate data saved to {intermediate_dir}")

    # --- Step 3: Run audit ---
    print("\n--- Step 3: Run SEO/AEO Audit ---")
    if dry_run:
        report = run_audit_dry_run(page_url, page_content, gsc_data)
    else:
        report = run_audit(page_url, page_content, gsc_data)

    # --- Step 4: Save report ---
    print("\n--- Step 4: Save Report ---")
    report_path = intermediate_dir / "seo_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[orchestrator] Report saved to {report_path}")

    # --- Step 5: Create GitHub issue (optional) ---
    issue_url = None
    if create_issue:
        print("\n--- Step 5: Create GitHub Issue ---")
        issue_url = create_seo_github_issue(report)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Page: {page_url}")
    print(f"  Overall score: {report.get('overall_score', 'N/A')}/100")
    print(f"  Findings: {len(report.get('findings', []))}")
    print(f"  Quick wins: {len(report.get('quick_wins', []))}")
    print(f"  Output: {report_path}")
    if issue_url:
        print(f"  GitHub Issue: {issue_url}")
    print("=" * 60)

    return {
        "pipeline": "seo-audit",
        "page_url": page_url,
        "report_path": str(report_path),
        "report": report,
        "issue_url": issue_url,
    }


def create_seo_github_issue(report: dict[str, Any]) -> str | None:
    """Create a GitHub issue summarizing the SEO audit findings.

    Args:
        report: The SEO audit report dict.

    Returns:
        The URL of the created issue, or None if creation failed.
    """
    findings = report.get("findings", [])
    if not findings:
        print("[orchestrator] No findings to report — skipping issue creation")
        return None

    today = date.today().isoformat()
    page_url = report.get("page_url", "Unknown page")
    score = report.get("overall_score", "N/A")
    title = f"SEO Audit: {page_url} ({score}/100) — {today}"

    lines = [
        f"## SEO/AEO Audit Report — {today}",
        "",
        f"**Page:** {page_url}",
        f"**Overall Score:** {score}/100",
        "",
        f"> {report.get('summary', '')}",
        "",
        "### Quick Wins",
        "",
    ]
    for win in report.get("quick_wins", []):
        lines.append(f"- [ ] {win}")

    lines.extend(["", "### Detailed Findings", ""])

    for finding in findings:
        severity = finding.get("severity", "?")
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
        lines.extend([
            f"#### {emoji} {finding.get('title', 'Untitled')}",
            "",
            f"**Category:** {finding.get('category', 'N/A')} | "
            f"**Severity:** {severity} | "
            f"**Effort:** {finding.get('effort', 'N/A')}",
            "",
            finding.get("description", ""),
            "",
            f"**Recommendation:** {finding.get('recommendation', '')}",
            "",
        ])

    lines.append("---")
    lines.append("*Generated by the SEO/AEO audit pipeline.*")
    body = "\n".join(lines)

    try:
        result = subprocess.run(
            [
                "gh", "issue", "create",
                "--title", title,
                "--body", body,
                "--label", "seo-audit",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            issue_url = result.stdout.strip()
            print(f"[orchestrator] GitHub issue created: {issue_url}")
            return issue_url
        else:
            print(f"[orchestrator] GitHub issue creation failed: {result.stderr.strip()}")
            return None

    except FileNotFoundError:
        print("[orchestrator] `gh` CLI not found — skipping issue creation")
        return None
    except subprocess.TimeoutExpired:
        print("[orchestrator] GitHub issue creation timed out")
        return None


def run_portfolio_audit(
    *,
    dry_run: bool = False,
    url: str | None = None,
    api_key: str | None = None,
    output_dir: str | None = None,
    create_issue: bool = False,
) -> dict[str, Any]:
    """Run the portfolio audit pipeline using PageSpeed Insights + Claude.

    Steps:
        1. Fetch PageSpeed Insights data (performance, accessibility, best practices, SEO)
        2. Fetch the portfolio page content for Claude context
        3. Run Claude analysis — prioritizes PSI findings, adds light content freshness notes
        4. Save the report and update memory state (scores persist for trend detection)
        5. Optionally create a GitHub issue with findings

    Args:
        dry_run: Use sample data and skip live API calls.
        url: URL of the portfolio site to audit.
        api_key: Google API key for PSI. Falls back to PAGESPEED_API_KEY env var.
        output_dir: Custom output directory path.
        create_issue: Whether to create a GitHub issue with findings.

    Returns:
        A dict with pipeline results including file paths and report data.
    """
    import os

    print("=" * 60)
    print("PIPELINE: Portfolio Audit")
    print("=" * 60)

    today = date.today().isoformat()
    intermediate_dir = (
        Path(output_dir) if output_dir else Path("outputs") / "portfolio_audits" / today
    )
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Fetch PageSpeed Insights data ---
    print("\n--- Step 1: Fetch PageSpeed Insights Data ---")
    if dry_run:
        psi_data = fetch_pagespeed_dry_run()
    else:
        if not url:
            raise ValueError("Provide --url or --dry-run")
        key = api_key or os.environ.get("PAGESPEED_API_KEY", "")
        if not key:
            raise ValueError("PAGESPEED_API_KEY environment variable is required")
        psi_data = fetch_pagespeed(url, key)

    psi_path = intermediate_dir / "psi_data.json"
    psi_path.write_text(json.dumps(psi_data, indent=2), encoding="utf-8")
    print(f"[orchestrator] PSI data saved to {psi_path}")

    # --- Step 2: Fetch page content for Claude context ---
    print("\n--- Step 2: Fetch Page Content ---")
    if dry_run:
        page_content = SAMPLE_PORTFOLIO_CONTENT
        print("[orchestrator] DRY RUN — using sample page content")
    else:
        page_content = read_portfolio_from_url(url)

    content_path = intermediate_dir / "page_content.txt"
    content_path.write_text(page_content, encoding="utf-8")

    # --- Step 3: Run Claude analysis ---
    print("\n--- Step 3: Run Claude Analysis ---")
    if dry_run:
        report = run_portfolio_audit_dry_run()
    else:
        report = run_audit_with_psi(psi_data, page_content)

    # --- Step 4: Save report and update memory ---
    print("\n--- Step 4: Save Report ---")
    report_path = intermediate_dir / "portfolio_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[orchestrator] Report saved to {report_path}")
    save_audit_state(report)

    # --- Step 5: Create GitHub issue (optional) ---
    issue_url = None
    if create_issue:
        print("\n--- Step 5: Create GitHub Issue ---")
        issue_url = create_portfolio_github_issue(report)

    # --- Summary ---
    scores = report.get("scores", {})
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Performance: {scores.get('performance', 'N/A')}/100")
    print(f"  Accessibility: {scores.get('accessibility', 'N/A')}/100")
    print(f"  Best Practices: {scores.get('best_practices', 'N/A')}/100")
    print(f"  SEO: {scores.get('seo', 'N/A')}/100")
    print(f"  Findings: {len(report.get('findings', []))}")
    print(f"  Output: {report_path}")
    if issue_url:
        print(f"  GitHub Issue: {issue_url}")
    print("=" * 60)

    return {
        "pipeline": "portfolio-audit",
        "psi_data_path": str(psi_path),
        "report_path": str(report_path),
        "report": report,
        "issue_url": issue_url,
    }


def create_portfolio_github_issue(report: dict[str, Any]) -> str | None:
    """Create a GitHub issue summarizing the portfolio audit findings.

    Args:
        report: The portfolio audit report dict (portfolio_audit_template schema).

    Returns:
        The URL of the created issue, or None if creation failed.
    """
    findings = report.get("findings", [])
    if not findings:
        print("[orchestrator] No findings to report — skipping issue creation")
        return None

    today = date.today().isoformat()
    scores = report.get("scores", {})
    trends = report.get("score_trends", {})
    title = f"Portfolio Audit — {today}"

    trend_arrow = {"improving": "↑", "declining": "↓", "stable": "→", "first_run": "●"}

    lines = [
        f"## Portfolio Audit — {today}",
        "",
        "| Category | Score | Trend |",
        "|---|---|---|",
        f"| Performance | {scores.get('performance', 'N/A')}/100 | {trend_arrow.get(trends.get('performance', ''), '')} |",
        f"| Accessibility | {scores.get('accessibility', 'N/A')}/100 | {trend_arrow.get(trends.get('accessibility', ''), '')} |",
        f"| Best Practices | {scores.get('best_practices', 'N/A')}/100 | {trend_arrow.get(trends.get('best_practices', ''), '')} |",
        f"| SEO | {scores.get('seo', 'N/A')}/100 | {trend_arrow.get(trends.get('seo', ''), '')} |",
        "",
        f"> {report.get('summary', '')}",
        "",
        "### Quick Wins",
        "",
    ]
    for win in report.get("quick_wins", []):
        lines.append(f"- [ ] {win}")

    if findings:
        lines.extend(["", "### Findings", ""])
        for finding in findings:
            severity = finding.get("severity", "?")
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
            lines.extend([
                f"#### {emoji} {finding.get('title', 'Untitled')}",
                "",
                f"**Category:** {finding.get('category', 'N/A')} | "
                f"**Severity:** {severity}",
                "",
                finding.get("detail", ""),
                f"**Current:** {finding.get('current_value', 'N/A')}",
                f"**Fix:** {finding.get('recommendation', 'N/A')}",
                "",
            ])

    lines.append("---")
    lines.append("*Generated by the portfolio audit pipeline.*")
    body = "\n".join(lines)

    try:
        result = subprocess.run(
            [
                "gh", "issue", "create",
                "--title", title,
                "--body", body,
                "--label", "portfolio-audit",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            issue_url = result.stdout.strip()
            print(f"[orchestrator] GitHub issue created: {issue_url}")
            return issue_url
        else:
            print(f"[orchestrator] GitHub issue creation failed: {result.stderr.strip()}")
            return None

    except FileNotFoundError:
        print("[orchestrator] `gh` CLI not found — skipping issue creation")
        return None
    except subprocess.TimeoutExpired:
        print("[orchestrator] GitHub issue creation timed out")
        return None


def url_to_slug(url: str) -> str:
    """Convert a URL path to a filesystem-safe directory name.

    Examples:
        https://example.com/blog/python-async  -> blog_python-async
        https://example.com/about              -> about
        https://example.com/                   -> index

    Args:
        url: The full URL to convert.

    Returns:
        A filesystem-safe slug string.
    """
    path = urlparse(url).path.strip("/")
    if not path:
        return "index"
    # Replace slashes with underscores, strip unsafe chars
    slug = re.sub(r"[^\w\-]", "_", path)
    # Collapse multiple underscores
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug


def build_site_summary(
    page_reports: list[dict[str, Any]],
    all_entries: list[dict],
    filtered_entries: list[dict],
) -> dict[str, Any]:
    """Aggregate per-page SEO reports into a site-level summary.

    Args:
        page_reports: List of dicts with 'url', 'report', 'error' keys.
        all_entries: All sitemap entries before filtering.
        filtered_entries: Sitemap entries after freshness/pattern filtering.

    Returns:
        A site summary dict with aggregated stats.
    """
    successful = [p for p in page_reports if p.get("report")]
    scores = [p["report"]["overall_score"] for p in successful
              if "overall_score" in p["report"]]

    mean_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Score distribution
    distribution = {"excellent": 0, "good": 0, "needs_work": 0, "poor": 0}
    for s in scores:
        if s >= 80:
            distribution["excellent"] += 1
        elif s >= 60:
            distribution["good"] += 1
        elif s >= 40:
            distribution["needs_work"] += 1
        else:
            distribution["poor"] += 1

    # Cross-site findings grouped by title
    finding_groups: dict[str, list[dict]] = {}
    for p in successful:
        for finding in p["report"].get("findings", []):
            title = finding.get("title", "Untitled")
            finding_groups.setdefault(title, []).append({
                "url": p["url"],
                "severity": finding.get("severity", "unknown"),
            })

    top_findings = sorted(
        finding_groups.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )[:10]

    # 5 lowest-scoring priority pages
    priority_pages = sorted(successful, key=lambda p: p["report"].get("overall_score", 100))[:5]

    return {
        "generated_date": date.today().isoformat(),
        "total_sitemap_urls": len(all_entries),
        "filtered_urls": len(filtered_entries),
        "audited_pages": len(successful),
        "failed_pages": len(page_reports) - len(successful),
        "mean_score": mean_score,
        "score_distribution": distribution,
        "top_cross_site_findings": [
            {"title": title, "count": len(pages), "pages": pages}
            for title, pages in top_findings
        ],
        "priority_pages": [
            {"url": p["url"], "score": p["report"].get("overall_score", "N/A")}
            for p in priority_pages
        ],
    }


def create_site_audit_github_issues(
    summary: dict[str, Any],
    page_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create GitHub issues for site audit — per-page issues + one summary.

    Creates individual issues for each audited page (reusing
    create_seo_github_issue), then creates one summary issue linking
    to all per-page issues.

    Args:
        summary: The site summary dict from build_site_summary().
        page_reports: List of per-page report dicts.

    Returns:
        A dict with 'page_issues' (list of URLs) and 'summary_issue' URL.
    """
    page_issue_urls = []

    # Create per-page issues
    for p in page_reports:
        report = p.get("report")
        if not report:
            continue
        issue_url = create_seo_github_issue(report)
        if issue_url:
            page_issue_urls.append({"url": p["url"], "issue_url": issue_url})

    # Create summary issue
    today = date.today().isoformat()
    title = f"Site SEO Audit Summary ({summary['mean_score']}/100 avg) — {today}"

    lines = [
        f"## Site-Wide SEO Audit — {today}",
        "",
        f"**Pages in sitemap:** {summary['total_sitemap_urls']}",
        f"**Pages audited:** {summary['audited_pages']}",
        f"**Mean score:** {summary['mean_score']}/100",
        "",
        "### Score Distribution",
        "",
        f"- Excellent (80+): {summary['score_distribution']['excellent']}",
        f"- Good (60-79): {summary['score_distribution']['good']}",
        f"- Needs Work (40-59): {summary['score_distribution']['needs_work']}",
        f"- Poor (<40): {summary['score_distribution']['poor']}",
        "",
        "### Priority Pages (Lowest Scores)",
        "",
    ]
    for p in summary.get("priority_pages", []):
        lines.append(f"- **{p['score']}/100** — {p['url']}")

    lines.extend(["", "### Top Cross-Site Findings", ""])
    for finding in summary.get("top_cross_site_findings", [])[:5]:
        lines.append(f"- **{finding['title']}** — found on {finding['count']} pages")

    if page_issue_urls:
        lines.extend(["", "### Per-Page Issues", ""])
        for entry in page_issue_urls:
            lines.append(f"- {entry['url']}: {entry['issue_url']}")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by the site-audit pipeline.*")
    body = "\n".join(lines)

    summary_issue_url = None
    try:
        result = subprocess.run(
            [
                "gh", "issue", "create",
                "--title", title,
                "--body", body,
                "--label", "seo-audit",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            summary_issue_url = result.stdout.strip()
            print(f"[orchestrator] Summary issue created: {summary_issue_url}")
        else:
            print(f"[orchestrator] Summary issue creation failed: {result.stderr.strip()}")
    except FileNotFoundError:
        print("[orchestrator] `gh` CLI not found — skipping summary issue")
    except subprocess.TimeoutExpired:
        print("[orchestrator] Summary issue creation timed out")

    return {
        "page_issues": page_issue_urls,
        "summary_issue": summary_issue_url,
    }


def run_site_audit(
    *,
    sitemap_url: str | None = None,
    dry_run: bool = False,
    days: int = 28,
    stale_months: int = 3,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    output_dir: str | None = None,
    create_issue: bool = False,
) -> dict[str, Any]:
    """Run the sitemap-based multi-page SEO audit pipeline.

    Steps:
        1. Fetch sitemap (or dry-run sample)
        2. Filter URLs by freshness + patterns
        3. Loop through filtered URLs, running SEO audit per page
        4. Build site-level summary
        5. Save consolidated report
        6. Optionally create GitHub issues

    Args:
        sitemap_url: The URL of the XML sitemap.
        dry_run: Use sample data and skip live API calls.
        days: GSC lookback window in days.
        stale_months: Pages older than this are considered stale.
        include_patterns: Glob patterns to include (matched against URL path).
        exclude_patterns: Glob patterns to exclude (matched against URL path).
        output_dir: Custom output directory path.
        create_issue: Whether to create GitHub issues with findings.

    Returns:
        A dict with pipeline results including file paths and summary data.
    """
    print("=" * 60)
    print("PIPELINE: Site-Wide SEO Audit")
    print("=" * 60)

    # --- Step 1: Fetch sitemap ---
    print("\n--- Step 1: Fetch Sitemap ---")
    if dry_run:
        all_entries = fetch_sitemap_dry_run()
        print(f"[orchestrator] DRY RUN — {len(all_entries)} sample entries")
    else:
        all_entries = fetch_sitemap(sitemap_url)

    today = date.today().isoformat()
    base_dir = Path(output_dir) if output_dir else Path("outputs") / "site_audits" / today
    base_dir.mkdir(parents=True, exist_ok=True)

    sitemap_path = base_dir / "sitemap_data.json"
    sitemap_path.write_text(json.dumps(all_entries, indent=2), encoding="utf-8")
    print(f"[orchestrator] Sitemap data saved to {sitemap_path}")

    # --- Step 2: Filter URLs ---
    print("\n--- Step 2: Filter URLs ---")
    filtered_entries = filter_urls(
        all_entries,
        stale_months=stale_months,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )

    filtered_path = base_dir / "filtered_urls.json"
    filtered_path.write_text(json.dumps(filtered_entries, indent=2), encoding="utf-8")
    print(f"[orchestrator] {len(filtered_entries)} URLs to audit")

    # --- Step 3: Audit each page ---
    print("\n--- Step 3: Audit Pages ---")
    pages_dir = base_dir / "pages"
    pages_dir.mkdir(exist_ok=True)

    page_reports: list[dict[str, Any]] = []
    for i, entry in enumerate(filtered_entries, start=1):
        page_url = entry["url"]
        slug = url_to_slug(page_url)
        page_dir = pages_dir / slug

        print(f"\n  [{i}/{len(filtered_entries)}] {page_url}")

        try:
            result = run_seo_audit(
                page_url=page_url,
                dry_run=dry_run,
                days=days,
                output_dir=str(page_dir),
                create_issue=False,  # Issues created in bulk later
            )
            page_reports.append({
                "url": page_url,
                "slug": slug,
                "report": result.get("report", {}),
                "report_path": result.get("report_path"),
                "error": None,
            })
        except Exception as exc:
            print(f"  [ERROR] {page_url}: {exc}")
            page_reports.append({
                "url": page_url,
                "slug": slug,
                "report": None,
                "report_path": None,
                "error": str(exc),
            })

        # Rate limit between pages
        if i < len(filtered_entries):
            time.sleep(1)

    # --- Step 4: Build summary ---
    print("\n--- Step 4: Build Site Summary ---")
    summary = build_site_summary(page_reports, all_entries, filtered_entries)

    summary_path = base_dir / "site_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[orchestrator] Site summary saved to {summary_path}")

    # --- Step 5: Create GitHub issues (optional) ---
    issues_result = None
    if create_issue:
        print("\n--- Step 5: Create GitHub Issues ---")
        issues_result = create_site_audit_github_issues(summary, page_reports)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Sitemap URLs: {len(all_entries)}")
    print(f"  Filtered (stale): {len(filtered_entries)}")
    successful = [p for p in page_reports if p.get("report")]
    print(f"  Audited: {len(successful)}, Failed: {len(page_reports) - len(successful)}")
    print(f"  Mean score: {summary['mean_score']}/100")
    print(f"  Output: {base_dir}")
    if issues_result and issues_result.get("summary_issue"):
        print(f"  Summary Issue: {issues_result['summary_issue']}")
    print("=" * 60)

    return {
        "pipeline": "site-audit",
        "summary_path": str(summary_path),
        "summary": summary,
        "page_reports": page_reports,
        "issues": issues_result,
    }


# ---------------------------------------------------------------------------
# apply-fixes: category → source file mapping
# ---------------------------------------------------------------------------

CATEGORY_SOURCE_FILES: dict[str, list[str]] = {
    "robots_txt": [
        "public/robots.txt",
    ],
    "title_meta": [
        "src/components/layout/BaseHead.astro",
        "src/pages/index.astro",
        "src/pages/blog/index.astro",
        "src/pages/blog/[slug].astro",
        "src/pages/blog/tags/[tag].astro",
        "src/layouts/BlogPost.astro",
        "src/layouts/Default.astro",
    ],
    "schema": [
        "src/components/layout/BaseHead.astro",
        "src/layouts/BlogPost.astro",
        "src/layouts/Default.astro",
    ],
}

ALL_CATEGORIES = list(CATEGORY_SOURCE_FILES.keys())

CATEGORY_LABELS: dict[str, str] = {
    "robots_txt": "robots.txt",
    "title_meta": "title tags and meta descriptions",
    "schema": "structured data / JSON-LD schema",
}


def _find_latest_audit_date() -> str | None:
    """Find the most recent audit date directory in outputs/site_audits/.

    Returns:
        The date string (YYYY-MM-DD) or None if no audits exist.
    """
    audits_dir = Path("outputs") / "site_audits"
    if not audits_dir.exists():
        return None
    dates = sorted(
        (d.name for d in audits_dir.iterdir() if d.is_dir()),
        reverse=True,
    )
    return dates[0] if dates else None


def _load_audit_findings(audit_date: str) -> list[dict[str, Any]]:
    """Load all findings from per-page seo_report.json files for an audit date.

    Args:
        audit_date: The YYYY-MM-DD date string for the audit.

    Returns:
        Flat list of all finding dicts, each augmented with 'page_url'.
    """
    pages_dir = Path("outputs") / "site_audits" / audit_date / "pages"
    if not pages_dir.exists():
        print(f"[orchestrator] No pages directory found at {pages_dir}")
        return []

    all_findings: list[dict[str, Any]] = []
    for report_path in sorted(pages_dir.rglob("seo_report.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        page_url = report.get("page_url", "unknown")
        for finding in report.get("findings", []):
            finding["page_url"] = page_url
            all_findings.append(finding)

    return all_findings


AUTO_PATCH_SEVERITIES = {"high", "medium"}


def _filter_findings_for_category(
    category: str, findings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Filter findings relevant to a specific fix category.

    Args:
        category: One of robots_txt, title_meta, schema.
        findings: Full list of findings from all pages.

    Returns:
        Filtered list of findings relevant to the category (high/medium severity only).
    """
    if category == "robots_txt":
        matched = [
            f for f in findings
            if "robots" in f.get("title", "").lower()
            or "robots" in f.get("description", "").lower()
        ]
        matched = [f for f in matched if f.get("severity", "low") in AUTO_PATCH_SEVERITIES]
        return matched

    if category == "title_meta":
        keywords = ("title", "meta description", "h1")
        return [
            f for f in findings
            if f.get("category") == "on_page_seo"
            and any(kw in f.get("title", "").lower() for kw in keywords)
            and f.get("severity", "low") in AUTO_PATCH_SEVERITIES
        ]

    if category == "schema":
        return [
            f for f in findings
            if (
                "schema" in f.get("title", "").lower()
                or "schema" in f.get("description", "").lower()
                or "structured data" in f.get("title", "").lower()
                or "breadcrumb" in f.get("title", "").lower()
                or f.get("category") == "schema_markup"
            )
            and f.get("severity", "low") in AUTO_PATCH_SEVERITIES
        ]

    return []


def _count_existing_drafts(portfolio_dir: str) -> int:
    """Count .md files currently sitting in the portfolio drafts folder.

    Excludes files whose names start with '_' (e.g. _README.md) so
    permanent fixtures never count against the draft cap.

    Args:
        portfolio_dir: Path to the portfolio repo root.

    Returns:
        Number of .md files in src/content/blog/drafts/, or 0 if the
        directory doesn't exist yet.
    """
    drafts_dir = Path(portfolio_dir) / "src" / "content" / "blog" / "drafts"
    if not drafts_dir.exists():
        return 0
    return sum(
        1 for f in drafts_dir.iterdir()
        if f.suffix == ".md" and not f.name.startswith("_")
    )


def _warn_stale_drafts(portfolio_dir: str, stale_days: int = 60) -> None:
    """Print a warning listing any draft files older than stale_days.

    Helps surface forgotten drafts without blocking the pipeline. Files
    starting with '_' (e.g. _README.md) are excluded from the check.

    Args:
        portfolio_dir: Path to the portfolio repo root.
        stale_days: Age threshold in days; drafts older than this are flagged.
    """
    drafts_dir = Path(portfolio_dir) / "src" / "content" / "blog" / "drafts"
    if not drafts_dir.exists():
        return
    cutoff = datetime.now().timestamp() - stale_days * 86400
    stale = [
        f for f in drafts_dir.iterdir()
        if f.suffix == ".md"
        and not f.name.startswith("_")
        and f.stat().st_mtime < cutoff
    ]
    if stale:
        print(
            f"[orchestrator] WARNING: {len(stale)} draft(s) are older than "
            f"{stale_days} days — consider publishing or deleting them:"
        )
        for f in sorted(stale):
            age_days = int((datetime.now().timestamp() - f.stat().st_mtime) / 86400)
            print(f"  - {f.name} ({age_days}d old)")


def _read_source_files(portfolio_dir: str, category: str, source_files_map: dict[str, list[str]] | None = None) -> dict[str, str]:
    """Read the source files relevant to a category from the portfolio repo.

    Args:
        portfolio_dir: Path to the portfolio repository root.
        category: The fix category determining which files to read.
        source_files_map: Optional mapping of category → file paths. Defaults
            to CATEGORY_SOURCE_FILES if not provided.

    Returns:
        Dict of {relative_path: file_content} for existing files.
    """
    source_files: dict[str, str] = {}
    base = Path(portfolio_dir)
    mapping = source_files_map if source_files_map is not None else CATEGORY_SOURCE_FILES

    for rel_path in mapping.get(category, []):
        full_path = base / rel_path
        if full_path.exists():
            source_files[rel_path] = full_path.read_text(encoding="utf-8")
            print(f"[orchestrator]   Read {rel_path} ({len(source_files[rel_path])} chars)")
        else:
            print(f"[orchestrator]   Skipped {rel_path} (not found)")

    return source_files


MAX_BUILD_RETRIES = 2


def _run_build_check(portfolio_dir: str) -> tuple[bool, str]:
    """Run pnpm build in the portfolio directory and return the result.

    Args:
        portfolio_dir: Path to the portfolio repository root.

    Returns:
        Tuple of (success, output). On failure, output contains combined
        stdout+stderr for diagnosing the build error.
    """
    print("[orchestrator] Running build check (pnpm build)...")
    try:
        result = subprocess.run(
            ["pnpm", "build"],
            cwd=portfolio_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("[orchestrator] Build check passed")
            return True, ""
        else:
            output = (result.stdout + "\n" + result.stderr).strip()
            print(f"[orchestrator] Build check failed (exit {result.returncode})")
            return False, output
    except subprocess.TimeoutExpired:
        print("[orchestrator] Build check timed out after 120s")
        return False, "Build timed out after 120 seconds"


def _apply_patches(portfolio_dir: str, patches: list[dict[str, Any]]) -> None:
    """Write patch files to disk in the portfolio repo.

    Args:
        portfolio_dir: Path to the portfolio repository root.
        patches: List of patch dicts with file, action, content keys.
    """
    base = Path(portfolio_dir)
    for patch in patches:
        file_path = base / patch["file"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(patch["content"], encoding="utf-8")


def _save_originals(
    portfolio_dir: str, patches: list[dict[str, Any]]
) -> dict[str, str | None]:
    """Save the original contents of files that will be patched.

    Args:
        portfolio_dir: Path to the portfolio repository root.
        patches: List of patch dicts with file keys.

    Returns:
        Dict of {relative_path: original_content_or_None}. None means the file
        did not exist (i.e. it would be created by the patch).
    """
    base = Path(portfolio_dir)
    originals: dict[str, str | None] = {}
    for patch in patches:
        file_path = base / patch["file"]
        if file_path.exists():
            originals[patch["file"]] = file_path.read_text(encoding="utf-8")
        else:
            originals[patch["file"]] = None
    return originals


def _restore_files(
    portfolio_dir: str, original_contents: dict[str, str | None]
) -> None:
    """Restore files to their original contents after a failed build.

    Args:
        portfolio_dir: Path to the portfolio repository root.
        original_contents: Dict from _save_originals(). None values mean the
            file should be deleted (it was created by a patch).
    """
    base = Path(portfolio_dir)
    for rel_path, content in original_contents.items():
        file_path = base / rel_path
        if content is None:
            if file_path.exists():
                file_path.unlink()
        else:
            file_path.write_text(content, encoding="utf-8")


def _create_combined_fix_pr(
    portfolio_dir: str,
    patches_by_category: dict[str, list[dict[str, Any]]],
    category_pr_info: dict[str, tuple[str, str]],
    *,
    branch_prefix: str = "fix/seo",
    pr_title_prefix: str = "Monthly SEO fixes",
    category_labels: dict[str, str] | None = None,
) -> str | None:
    """Apply all category patches to one branch and open a single combined PR.

    All categories are committed together, eliminating merge conflicts that arise
    when multiple per-category PRs are open against the same base branch.

    Args:
        portfolio_dir: Path to the portfolio repository root.
        patches_by_category: Dict of {category: patches} for categories that
            passed build validation.
        category_pr_info: Dict of {category: (pr_title, pr_description)} for
            each category's suggested PR copy.
        branch_prefix: Git branch name prefix (e.g. "fix/seo" or "fix/portfolio").
        pr_title_prefix: PR title prefix used when multiple categories are combined.
        category_labels: Optional label map for human-readable category names in
            the multi-category PR description. Defaults to CATEGORY_LABELS.

    Returns:
        The URL of the created PR, or None if creation failed or no changes exist.
    """
    today = date.today().isoformat()
    branch = f"{branch_prefix}-{today}"
    repo = os.environ.get("PORTFOLIO_REPO", "")
    if not repo:
        print("[orchestrator] ERROR: PORTFOLIO_REPO environment variable is not set. Cannot create PR.")
        return None

    labels = category_labels if category_labels is not None else CATEGORY_LABELS

    # Build combined PR title and description
    categories = list(patches_by_category.keys())
    if len(categories) == 1:
        cat = categories[0]
        pr_title, pr_description = category_pr_info[cat]
    else:
        cat_label_str = ", ".join(labels.get(c, c) for c in categories)
        pr_title = f"{pr_title_prefix}: {cat_label_str}"
        pr_description = "\n\n---\n\n".join(
            f"## {labels.get(cat, cat)}\n\n{desc}"
            for cat, (_, desc) in category_pr_info.items()
        )

    # Flatten patches from all categories into one list
    all_patches = [p for patches in patches_by_category.values() for p in patches]

    try:
        # Ensure we're on main and up to date
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )

        # Delete stale local/remote branch from previous runs
        subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )
        subprocess.run(
            ["git", "push", "origin", "--delete", branch],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )

        # Create and switch to new branch
        result = subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"[orchestrator] Failed to create branch {branch}: {result.stderr.strip()}")
            return None
        print(f"[orchestrator] Created branch: {branch}")

        # Apply all patches
        base = Path(portfolio_dir)
        for patch in all_patches:
            file_path = base / patch["file"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(patch["content"], encoding="utf-8")
            print(f"[orchestrator] Wrote {patch['file']} ({patch['action']})")

        # Final combined build check — catches cross-category conflicts where
        # two categories both patch the same file in incompatible ways.
        # Each category was validated in isolation, but the merged result may differ.
        ok, build_output = _run_build_check(portfolio_dir)
        if not ok:
            print("[orchestrator] Combined build check failed — cross-category patch conflict")
            print(f"[orchestrator] Build output:\n{build_output[:3000]}")
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
            )
            return None

        # Stage and commit
        files_to_add = [p["file"] for p in all_patches]
        subprocess.run(
            ["git", "add"] + files_to_add,
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )

        # Check if there are actual changes to commit
        diff_check = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )
        if diff_check.returncode == 0:
            print("[orchestrator] No changes to commit — patches match existing files")
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
            )
            return None

        commit_msg = f"{pr_title}\n\nGenerated by the apply-fixes pipeline."
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"[orchestrator] Commit failed: {result.stderr.strip()}")
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
            )
            return None
        print("[orchestrator] Committed changes")

        # Push
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"[orchestrator] Push failed: {result.stderr.strip()}")
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
            )
            return None
        print("[orchestrator] Pushed branch to origin")

        # Open PR
        result = subprocess.run(
            [
                "gh", "pr", "create",
                "--repo", repo,
                "--title", pr_title,
                "--body", pr_description,
                "--head", branch,
            ],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            pr_url = result.stdout.strip()
            print(f"[orchestrator] PR created: {pr_url}")
        else:
            print(f"[orchestrator] PR creation failed: {result.stderr.strip()}")
            pr_url = None

        # Return to main
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=portfolio_dir, capture_output=True, text=True, timeout=30,
        )

        return pr_url

    except FileNotFoundError:
        print("[orchestrator] `git` or `gh` CLI not found — skipping PR creation")
        return None
    except subprocess.TimeoutExpired:
        print("[orchestrator] Git/PR operation timed out")
        # Try to get back to main
        try:
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=portfolio_dir, capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass
        return None


def run_apply_fixes(
    *,
    dry_run: bool = False,
    audit_date: str | None = None,
    portfolio_dir: str | None = None,
    categories: list[str] | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Run the apply-fixes pipeline: read audit findings, generate patches, open PRs.

    Steps:
        1. Resolve audit date (default: latest)
        2. Load all findings from site audit reports
        3. For each requested category, filter findings + generate patches
        4. Save patches to outputs/fix_patches/YYYY-MM-DD/
        5. If not dry-run, apply patches and open PRs on the portfolio repo

    Args:
        dry_run: Use sample patches, skip git/PR operations.
        audit_date: Which audit date to read findings from (default: latest).
        portfolio_dir: Path to the portfolio repository.
        categories: List of categories to process (default: all).
        output_dir: Custom output directory path.

    Returns:
        A dict with pipeline results including patches and PR URLs.
    """
    print("=" * 60)
    print("PIPELINE: Apply Fixes")
    print("=" * 60)

    requested_categories = categories or ALL_CATEGORIES

    # --- Step 1: Resolve audit date ---
    print("\n--- Step 1: Resolve Audit Date ---")
    if audit_date is None:
        audit_date = _find_latest_audit_date()
        if audit_date is None:
            print("[orchestrator] No site audits found in outputs/site_audits/")
            print("[orchestrator] Run 'python orchestrator.py site-audit' first.")
            return {"pipeline": "apply-fixes", "error": "no_audits_found"}
    print(f"[orchestrator] Using audit date: {audit_date}")

    # --- Step 2: Load findings ---
    print("\n--- Step 2: Load Audit Findings ---")
    all_findings = _load_audit_findings(audit_date)
    print(f"[orchestrator] Loaded {len(all_findings)} total findings")

    # --- Step 3: Process each category ---
    today = date.today().isoformat()
    base_dir = Path(output_dir) if output_dir else Path("outputs") / "fix_patches" / today
    base_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict[str, Any]] = {}
    # Collect patches from categories that pass build validation, then open one PR.
    validated_patches: dict[str, list[dict[str, Any]]] = {}
    category_pr_info: dict[str, tuple[str, str]] = {}

    for cat in requested_categories:
        print(f"\n--- Category: {cat} ---")

        cat_dir = base_dir / cat
        cat_dir.mkdir(parents=True, exist_ok=True)

        # Filter findings for this category
        cat_findings = _filter_findings_for_category(cat, all_findings)
        print(f"[orchestrator] {len(cat_findings)} findings for {cat}")

        if not cat_findings and not dry_run:
            print(f"[orchestrator] No findings for {cat} — skipping")
            results[cat] = {"skipped": True, "reason": "no_findings"}
            continue

        # Generate patches
        if dry_run:
            print("[orchestrator] DRY RUN — using sample patches")
            fix_result = generate_fixes_dry_run(cat)
        else:
            # Read source files from portfolio
            print(f"[orchestrator] Reading source files from {portfolio_dir}")
            source_files = _read_source_files(portfolio_dir, cat)
            if not source_files:
                print(f"[orchestrator] No source files found for {cat} — skipping")
                results[cat] = {"skipped": True, "reason": "no_source_files"}
                continue

            fix_result = generate_fixes(cat, cat_findings, source_files)

        # Save patches
        patches_path = cat_dir / "patches.json"
        patches_path.write_text(json.dumps(fix_result, indent=2), encoding="utf-8")
        print(f"[orchestrator] Patches saved to {patches_path}")

        # Validate build per category (if not dry-run), collect for combined PR
        if not dry_run:
            patches = fix_result.get("patches", [])
            if patches:
                # Save original file contents for restoration between attempts
                original_contents = _save_originals(portfolio_dir, patches)
                build_ok = False

                for attempt in range(1 + MAX_BUILD_RETRIES):
                    _apply_patches(portfolio_dir, patches)
                    passed, build_output = _run_build_check(portfolio_dir)

                    if passed:
                        build_ok = True
                        _restore_files(portfolio_dir, original_contents)
                        break

                    if attempt < MAX_BUILD_RETRIES:
                        print(
                            f"[orchestrator] Build failed (attempt {attempt + 1})"
                            " — asking Claude to fix"
                        )
                        _restore_files(portfolio_dir, original_contents)
                        fix_result = fix_build_errors(
                            cat, patches, build_output, source_files
                        )
                        patches = fix_result.get("patches", [])
                        # Save updated patches
                        patches_path.write_text(
                            json.dumps(fix_result, indent=2), encoding="utf-8"
                        )
                    else:
                        print(
                            f"[orchestrator] Build still failing after"
                            f" {MAX_BUILD_RETRIES} retries — skipping category"
                        )
                        _restore_files(portfolio_dir, original_contents)

                if not build_ok:
                    results[cat] = {"skipped": True, "reason": "build_failed"}
                    continue

                # Queue validated patches for the combined PR
                validated_patches[cat] = patches
                category_pr_info[cat] = (
                    fix_result.get("pr_title", f"Fix {cat} issues"),
                    fix_result.get("pr_description", f"Automated fixes for {cat}."),
                )
            else:
                print(f"[orchestrator] No patches generated for {cat}")

        results[cat] = {
            "findings_count": len(cat_findings),
            "patches_path": str(patches_path),
            "patches_count": len(fix_result.get("patches", [])),
            "pr_title": fix_result.get("pr_title"),
        }

    # --- Create single combined PR for all validated categories ---
    combined_pr_url = None
    if not dry_run and validated_patches:
        print(f"\n--- Creating combined PR for: {', '.join(validated_patches)} ---")
        combined_pr_url = _create_combined_fix_pr(
            portfolio_dir, validated_patches, category_pr_info
        )
        if combined_pr_url:
            (base_dir / "pr_url.txt").write_text(combined_pr_url, encoding="utf-8")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Audit date: {audit_date}")
    print(f"  Categories processed: {len(results)}")
    for cat, info in results.items():
        if info.get("skipped"):
            print(f"  {cat}: skipped ({info.get('reason')})")
        else:
            print(f"  {cat}: {info.get('patches_count', 0)} patches")
    print(f"  Combined PR: {combined_pr_url or 'none'}")
    print(f"  Output: {base_dir}")
    print("=" * 60)

    return {
        "pipeline": "apply-fixes",
        "audit_date": audit_date,
        "output_dir": str(base_dir),
        "categories": results,
        "pr_url": combined_pr_url,
    }


# ---------------------------------------------------------------------------
# apply-portfolio-fixes: category → source file mapping (config-driven)
# ---------------------------------------------------------------------------

def _load_portfolio_source_files_config() -> dict[str, list[str]]:
    """Load the portfolio source file mapping from config/portfolio_source_files.json.

    Returns:
        Dict mapping category name to list of relative file paths. Returns an empty
        dict if the config file is not found, so the pipeline degrades gracefully.
    """
    config_path = Path("config") / "portfolio_source_files.json"
    if not config_path.exists():
        print(
            "[orchestrator] config/portfolio_source_files.json not found — "
            "no source files will be read. Create this file to enable patching."
        )
        return {}
    data = json.loads(config_path.read_text(encoding="utf-8"))
    # Strip the _comment key if present
    return {k: v for k, v in data.items() if not k.startswith("_")}


PORTFOLIO_CATEGORY_SOURCE_FILES: dict[str, list[str]] = _load_portfolio_source_files_config()
PORTFOLIO_ALL_CATEGORIES = list(PORTFOLIO_CATEGORY_LABELS.keys())


def _find_latest_portfolio_audit_date() -> str | None:
    """Find the most recent audit date directory in outputs/portfolio_audits/.

    Returns:
        The date string (YYYY-MM-DD) or None if no audits exist.
    """
    audits_dir = Path("outputs") / "portfolio_audits"
    if not audits_dir.exists():
        return None
    dates = sorted(
        (d.name for d in audits_dir.iterdir() if d.is_dir()),
        reverse=True,
    )
    return dates[0] if dates else None


def _load_portfolio_findings(audit_date: str) -> list[dict[str, Any]]:
    """Load findings from outputs/portfolio_audits/<date>/portfolio_report.json.

    Args:
        audit_date: The YYYY-MM-DD date string for the audit.

    Returns:
        Flat list of finding dicts from the portfolio report.
    """
    report_path = Path("outputs") / "portfolio_audits" / audit_date / "portfolio_report.json"
    if not report_path.exists():
        print(f"[orchestrator] No portfolio report found at {report_path}")
        return []

    report = json.loads(report_path.read_text(encoding="utf-8"))
    return report.get("findings", [])


def _filter_portfolio_findings_for_category(
    category: str, findings: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Filter portfolio findings by category and severity.

    Args:
        category: One of accessibility, performance, seo, best_practices.
        findings: Full list of findings from the portfolio report.

    Returns:
        Filtered list of high/medium severity findings for the category.
    """
    return [
        f for f in findings
        if f.get("category") == category
        and f.get("severity", "low") in AUTO_PATCH_SEVERITIES
    ]


def run_apply_portfolio_fixes(
    *,
    dry_run: bool = False,
    audit_date: str | None = None,
    portfolio_dir: str = "../your-portfolio-repo",
    categories: list[str] | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Run the apply-portfolio-fixes pipeline: read PSI findings, generate patches, open PR.

    Steps:
        1. Resolve audit date (outputs/portfolio_audits/)
        2. Load findings from portfolio_report.json
        3. For each category, filter findings + generate patches via generate_portfolio_fixes()
        4. Validate build per category (same retry logic as run_apply_fixes)
        5. Open single combined PR via _create_combined_fix_pr()

    Args:
        dry_run: Use sample patches, skip git/PR operations.
        audit_date: Which audit date to read findings from (default: latest).
        portfolio_dir: Path to the portfolio repository.
        categories: List of categories to process (default: all).
        output_dir: Custom output directory path.

    Returns:
        A dict with pipeline results including patches and PR URL.
    """
    print("=" * 60)
    print("PIPELINE: Apply Portfolio Fixes")
    print("=" * 60)

    requested_categories = categories or PORTFOLIO_ALL_CATEGORIES

    # --- Step 1: Resolve audit date ---
    print("\n--- Step 1: Resolve Audit Date ---")
    if audit_date is None:
        audit_date = _find_latest_portfolio_audit_date()
        if audit_date is None:
            print("[orchestrator] No portfolio audits found in outputs/portfolio_audits/")
            print("[orchestrator] Run 'python orchestrator.py portfolio-audit' first.")
            return {"pipeline": "apply-portfolio-fixes", "error": "no_audits_found"}
    print(f"[orchestrator] Using audit date: {audit_date}")

    # --- Step 2: Load findings ---
    print("\n--- Step 2: Load Portfolio Findings ---")
    all_findings = _load_portfolio_findings(audit_date)
    print(f"[orchestrator] Loaded {len(all_findings)} total findings")

    # --- Step 3: Process each category ---
    today = date.today().isoformat()
    base_dir = (
        Path(output_dir) if output_dir
        else Path("outputs") / "fix_patches" / today / "portfolio"
    )
    base_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict[str, Any]] = {}
    validated_patches: dict[str, list[dict[str, Any]]] = {}
    category_pr_info: dict[str, tuple[str, str]] = {}

    for cat in requested_categories:
        print(f"\n--- Category: {cat} ---")

        cat_dir = base_dir / cat
        cat_dir.mkdir(parents=True, exist_ok=True)

        # Filter findings for this category
        cat_findings = _filter_portfolio_findings_for_category(cat, all_findings)
        print(f"[orchestrator] {len(cat_findings)} findings for {cat}")

        if not cat_findings and not dry_run:
            print(f"[orchestrator] No findings for {cat} — skipping")
            results[cat] = {"skipped": True, "reason": "no_findings"}
            continue

        # Generate patches
        if dry_run:
            print("[orchestrator] DRY RUN — using sample patches")
            fix_result = generate_portfolio_fixes_dry_run(cat)
        else:
            print(f"[orchestrator] Reading source files from {portfolio_dir}")
            source_files = _read_source_files(
                portfolio_dir, cat, source_files_map=PORTFOLIO_CATEGORY_SOURCE_FILES
            )
            if not source_files:
                print(f"[orchestrator] No source files found for {cat} — skipping")
                results[cat] = {"skipped": True, "reason": "no_source_files"}
                continue

            site_url = os.environ.get("PORTFOLIO_URL", "https://yoursite.com")
            fix_result = generate_portfolio_fixes(cat, cat_findings, source_files, site_url)

        # Save patches
        patches_path = cat_dir / "patches.json"
        patches_path.write_text(json.dumps(fix_result, indent=2), encoding="utf-8")
        print(f"[orchestrator] Patches saved to {patches_path}")

        # Validate build per category (if not dry-run), collect for combined PR
        if not dry_run:
            patches = fix_result.get("patches", [])
            if patches:
                original_contents = _save_originals(portfolio_dir, patches)
                build_ok = False

                for attempt in range(1 + MAX_BUILD_RETRIES):
                    _apply_patches(portfolio_dir, patches)
                    passed, build_output = _run_build_check(portfolio_dir)

                    if passed:
                        build_ok = True
                        _restore_files(portfolio_dir, original_contents)
                        break

                    if attempt < MAX_BUILD_RETRIES:
                        print(
                            f"[orchestrator] Build failed (attempt {attempt + 1})"
                            " — asking Claude to fix"
                        )
                        _restore_files(portfolio_dir, original_contents)
                        fix_result = fix_build_errors(
                            cat, patches, build_output, source_files
                        )
                        patches = fix_result.get("patches", [])
                        patches_path.write_text(
                            json.dumps(fix_result, indent=2), encoding="utf-8"
                        )
                    else:
                        print(
                            f"[orchestrator] Build still failing after"
                            f" {MAX_BUILD_RETRIES} retries — skipping category"
                        )
                        _restore_files(portfolio_dir, original_contents)

                if not build_ok:
                    results[cat] = {"skipped": True, "reason": "build_failed"}
                    continue

                validated_patches[cat] = patches
                category_pr_info[cat] = (
                    fix_result.get("pr_title", f"Fix portfolio {cat} issues"),
                    fix_result.get("pr_description", f"Automated fixes for {cat}."),
                )
            else:
                print(f"[orchestrator] No patches generated for {cat} (not source-addressable)")

        results[cat] = {
            "findings_count": len(cat_findings),
            "patches_path": str(patches_path),
            "patches_count": len(fix_result.get("patches", [])),
            "pr_title": fix_result.get("pr_title"),
        }

    # --- Create single combined PR for all validated categories ---
    combined_pr_url = None
    if not dry_run and validated_patches:
        print(f"\n--- Creating combined PR for: {', '.join(validated_patches)} ---")
        combined_pr_url = _create_combined_fix_pr(
            portfolio_dir,
            validated_patches,
            category_pr_info,
            branch_prefix="fix/portfolio",
            pr_title_prefix="Monthly portfolio fixes",
            category_labels=PORTFOLIO_CATEGORY_LABELS,
        )
        if combined_pr_url:
            (base_dir / "pr_url.txt").write_text(combined_pr_url, encoding="utf-8")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Audit date: {audit_date}")
    print(f"  Categories processed: {len(results)}")
    for cat, info in results.items():
        if info.get("skipped"):
            print(f"  {cat}: skipped ({info.get('reason')})")
        else:
            print(f"  {cat}: {info.get('patches_count', 0)} patches")
    print(f"  Combined PR: {combined_pr_url or 'none'}")
    print(f"  Output: {base_dir}")
    print("=" * 60)

    return {
        "pipeline": "apply-portfolio-fixes",
        "audit_date": audit_date,
        "output_dir": str(base_dir),
        "categories": results,
        "pr_url": combined_pr_url,
    }


def _extract_blog_posts(sitemap_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract blog post entries from sitemap for internal linking context.

    Filters sitemap URLs that look like /blog/<slug>/ (excludes the blog
    index and tag pages) and derives a human-readable title from each slug.

    Args:
        sitemap_entries: List of sitemap entry dicts with at least a 'url' key.

    Returns:
        List of dicts with 'url', 'slug', and 'title' keys.
    """
    import re
    posts = []
    for entry in sitemap_entries:
        url = entry.get("url", "").rstrip("/")
        parts = url.split("/")
        # Expect .../blog/<slug> — skip the /blog/ index and /blog/tags/...
        if len(parts) >= 2 and parts[-2] == "blog" and parts[-1] and not parts[-1].startswith("tag"):
            slug = parts[-1]
            title = re.sub(r"^\d+-", "", slug).replace("-", " ").title()
            posts.append({"url": entry.get("url", ""), "slug": slug, "title": title})
    return posts


def create_portfolio_drafts(
    briefs: dict[str, Any],
    portfolio_dir: str,
) -> list[str]:
    """Write content brief skeletons as draft .md files in the portfolio repo.

    Creates one file per brief opportunity in src/content/blog/drafts/. Skips
    files that already exist so manual edits are never overwritten.

    Args:
        briefs: Content briefs dict from generate_briefs().
        portfolio_dir: Path to the portfolio repository root.

    Returns:
        List of absolute file paths that were created (skipped files excluded).
    """
    import re

    drafts_dir = Path(portfolio_dir) / "src" / "content" / "blog" / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    today_str = date.today().strftime("%B %d, %Y")
    created: list[str] = []

    linking_by_rank: dict[int, list[dict[str, Any]]] = {}
    for link in briefs.get("internal_linking_opportunities", []):
        r = link.get("from_brief_rank")
        if r is not None:
            linking_by_rank.setdefault(r, []).append(link)

    for opp in briefs.get("opportunities", []):
        query = opp.get("target_query", f"draft-{opp.get('rank', 0)}")
        slug = re.sub(r"[^a-z0-9\s-]", "", query.lower())
        slug = re.sub(r"\s+", "-", slug.strip())
        filename = f"{slug}.md"
        filepath = drafts_dir / filename

        if filepath.exists():
            print(f"[orchestrator] Draft exists, skipping: {filename}")
            continue

        rank = opp.get("rank")
        aeo = opp.get("aeo_recommendations", {})

        # Build internal linking notes for the brief comment block
        link_lines: list[str] = []
        for link in linking_by_rank.get(rank, []):
            anchor = link.get("suggested_anchor_text", "")
            context = link.get("linking_context", "")
            to_slug = link.get("to_existing_slug")
            to_title = link.get("to_existing_title")
            to_rank = link.get("to_brief_rank")
            if to_slug:
                link_lines.append(f'- "{anchor}" → /blog/{to_slug}/ ({to_title})\n  {context}')
            elif to_rank:
                link_lines.append(f'- "{anchor}" → brief #{to_rank} ({query})\n  {context}')
        links_block = "\n".join(link_lines) if link_lines else "(none identified)"

        # H2 sections from key subtopics
        subtopic_sections = "\n\n".join(
            f"## {sub.title()}\n\n<!-- TODO -->"
            for sub in opp.get("key_subtopics", [])
        )

        # FAQ section from PAA targets
        paa = aeo.get("people_also_ask_targets", [])
        faq_section = (
            "\n\n## Frequently Asked Questions\n\n"
            + "\n\n".join(
                f"**{q}**\n\n<!-- 2-3 sentence direct answer -->"
                for q in paa
            )
        ) if paa else ""

        content = f"""---
title: "{opp.get('suggested_title', '')}"
pubDate: "{today_str}"
author: ""
tags:
  - AEO
  - SEO
imgUrl: '../../../assets/astro.jpeg'
description: "{opp.get('suggested_meta_description', '')}"
draft: true
---

<!-- BRIEF
Target query: {query}
Target word count: ~{opp.get('target_word_count', 0)}
Featured snippet format: {aeo.get('featured_snippet_format', 'paragraph')}

Quick answer:
{aeo.get('quick_answer_summary', '')}

Internal links:
{links_block}
-->

# {opp.get('suggested_title', '')}

<!-- {opp.get('content_brief', '')} -->

{subtopic_sections}{faq_section}
"""
        filepath.write_text(content, encoding="utf-8")
        print(f"[orchestrator] Created draft: {filename}")
        created.append(str(filepath))

    return created


def _load_seed_queries() -> dict[str, Any]:
    """Load fallback seed queries from config/seed_queries.json.

    Returns:
        A dict matching the fetch_queries() output structure, with
        'site_url', 'date_range', and 'queries' fields.

    Raises:
        FileNotFoundError: If config/seed_queries.json does not exist.
    """
    seed_path = Path(__file__).resolve().parent / "config" / "seed_queries.json"
    seed_data = json.loads(seed_path.read_text(encoding="utf-8"))
    return {
        "site_url": "seed-queries",
        "date_range": {"start": date.today().isoformat(), "end": date.today().isoformat()},
        "queries": seed_data["queries"],
    }


def _mock_briefs(gsc_data: dict[str, Any]) -> dict[str, Any]:
    """Generate mock briefs for dry-run mode without calling Claude.

    Produces a structurally valid response matching the prompt template
    schema so the rest of the pipeline can be tested end-to-end.

    Args:
        gsc_data: The GSC data dict to base mock briefs on.

    Returns:
        A dict matching the content brief JSON schema.
    """
    queries = gsc_data.get("queries", [])[:5]
    opportunities = []

    for i, q in enumerate(queries, start=1):
        opportunities.append({
            "rank": i,
            "target_query": q["query"],
            "current_position": q["position"],
            "impressions": q["impressions"],
            "clicks": q["clicks"],
            "ctr": q["ctr"],
            "search_intent": "informational",
            "content_action": "update_existing" if q["position"] < 10 else "create_new",
            "suggested_title": f"Guide: {q['query'].title()}",
            "suggested_meta_description": f"Learn everything about {q['query']} with practical examples and best practices.",
            "content_brief": f"[MOCK] This is a placeholder brief for '{q['query']}'. In a live run, Claude would provide a detailed 2-3 paragraph actionable content plan here.",
            "target_word_count": 1500,
            "key_subtopics": ["subtopic-1", "subtopic-2", "subtopic-3"],
            "aeo_recommendations": {
                "featured_snippet_opportunity": True,
                "featured_snippet_format": "paragraph",
                "people_also_ask_targets": [
                    f"What is {q['query']}?",
                    f"How to use {q['query']}?",
                ],
                "schema_markup": ["Article", "FAQPage"],
                "quick_answer_summary": f"[MOCK] A concise answer about {q['query']}.",
            },
            "priority_rationale": f"[MOCK] Ranked #{i} based on impressions and position.",
        })

    return {
        "generated_date": date.today().isoformat(),
        "site_url": gsc_data.get("site_url", ""),
        "opportunities": opportunities,
    }


def main() -> None:
    """CLI entry point for the orchestrator."""
    parser = argparse.ArgumentParser(
        description="Run agent pipelines for website maintenance and SEO."
    )
    subparsers = parser.add_subparsers(dest="pipeline", help="Pipeline to run")

    # --- content-pipeline subcommand ---
    content = subparsers.add_parser(
        "content-pipeline",
        help="Fetch GSC data and generate content briefs.",
    )
    content.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample data, skip live API calls.",
    )
    content.add_argument(
        "--days",
        type=int,
        default=28,
        help="GSC lookback window in days (default: 28).",
    )
    content.add_argument(
        "--top",
        type=int,
        default=30,
        help="Max queries to fetch from GSC (default: 30).",
    )
    content.add_argument(
        "--sitemap-url",
        type=str,
        default=None,
        help="Sitemap URL for the freshness check sub-agent. If omitted, freshness check is skipped.",
    )
    content.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output directory.",
    )
    content.add_argument(
        "--create-issue",
        action="store_true",
        help="Create GitHub issues for both content briefs and freshness findings.",
    )
    content.add_argument(
        "--portfolio-dir",
        type=str,
        default=None,
        help="Path to the portfolio repo. If set, writes draft .md files to src/content/blog/drafts/.",
    )

    # --- seo-audit subcommand ---
    seo = subparsers.add_parser(
        "seo-audit",
        help="Audit a page for SEO and AEO optimization.",
    )
    seo.add_argument(
        "--page-url",
        type=str,
        required=True,
        help="The URL of the page to audit.",
    )
    seo.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample data, skip live API calls.",
    )
    seo.add_argument(
        "--days",
        type=int,
        default=28,
        help="GSC lookback window in days (default: 28).",
    )
    seo.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output directory.",
    )
    seo.add_argument(
        "--create-issue",
        action="store_true",
        help="Create a GitHub issue with audit findings.",
    )

    # --- portfolio-audit subcommand ---
    portfolio = subparsers.add_parser(
        "portfolio-audit",
        help="Audit portfolio site using PageSpeed Insights + Claude analysis.",
    )
    portfolio.add_argument(
        "--url",
        type=str,
        help="URL of the portfolio site to audit.",
    )
    portfolio.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample PSI data and page content, skip live API calls.",
    )
    portfolio.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output directory.",
    )
    portfolio.add_argument(
        "--create-issue",
        action="store_true",
        help="Create a GitHub issue with audit findings.",
    )

    # --- site-audit subcommand ---
    site = subparsers.add_parser(
        "site-audit",
        help="Audit all stale pages from a sitemap for SEO.",
    )
    site.add_argument(
        "--sitemap-url",
        type=str,
        help="URL of the XML sitemap to fetch.",
    )
    site.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample sitemap and audit data.",
    )
    site.add_argument(
        "--days",
        type=int,
        default=28,
        help="GSC lookback window in days (default: 28).",
    )
    site.add_argument(
        "--stale-months",
        type=int,
        default=3,
        help="Pages older than this are considered stale (default: 3).",
    )
    site.add_argument(
        "--include",
        action="append",
        default=None,
        help="Glob pattern to include (matched against URL path). Repeatable.",
    )
    site.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Glob pattern to exclude (matched against URL path). Repeatable.",
    )
    site.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output directory.",
    )
    site.add_argument(
        "--create-issue",
        action="store_true",
        help="Create GitHub issues with audit findings.",
    )

    # --- apply-portfolio-fixes subcommand ---
    portfolio_fixes = subparsers.add_parser(
        "apply-portfolio-fixes",
        help="Generate code patches from PSI/Lighthouse portfolio audit findings and open a PR.",
    )
    portfolio_fixes.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample patches, skip git/PR operations.",
    )
    portfolio_fixes.add_argument(
        "--audit-date",
        type=str,
        default=None,
        help="Portfolio audit date to read findings from (default: latest).",
    )
    portfolio_fixes.add_argument(
        "--portfolio-dir",
        type=str,
        default=None,
        help="Path to the local checkout of your portfolio repository.",
    )
    portfolio_fixes.add_argument(
        "--categories",
        type=str,
        default=None,
        help="Comma-separated categories: accessibility,performance,seo,best_practices (default: all).",
    )
    portfolio_fixes.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output directory.",
    )

    # --- apply-fixes subcommand ---
    fixes = subparsers.add_parser(
        "apply-fixes",
        help="Generate code patches from audit findings and open PRs.",
    )
    fixes.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample patches, skip git/PR operations.",
    )
    fixes.add_argument(
        "--audit-date",
        type=str,
        default=None,
        help="Audit date to read findings from (default: latest).",
    )
    fixes.add_argument(
        "--portfolio-dir",
        type=str,
        default=None,
        help="Path to the local checkout of your portfolio repository.",
    )
    fixes.add_argument(
        "--categories",
        type=str,
        default=None,
        help="Comma-separated categories: robots_txt,title_meta,schema (default: all).",
    )
    fixes.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output directory.",
    )

    args = parser.parse_args()

    if not args.pipeline:
        parser.print_help()
        sys.exit(1)

    if args.pipeline == "content-pipeline":
        run_content_pipeline(
            dry_run=args.dry_run,
            days=args.days,
            top_n=args.top,
            sitemap_url=getattr(args, "sitemap_url", None),
            output_dir=args.output,
            create_issue=args.create_issue,
            portfolio_dir=getattr(args, "portfolio_dir", None),
        )
    elif args.pipeline == "seo-audit":
        run_seo_audit(
            page_url=args.page_url,
            dry_run=args.dry_run,
            days=args.days,
            output_dir=args.output,
            create_issue=args.create_issue,
        )
    elif args.pipeline == "portfolio-audit":
        if not args.dry_run and not getattr(args, "url", None):
            parser.error("--url is required unless --dry-run is set")
        run_portfolio_audit(
            dry_run=args.dry_run,
            url=getattr(args, "url", None),
            output_dir=args.output,
            create_issue=args.create_issue,
        )
    elif args.pipeline == "site-audit":
        if not args.dry_run and not args.sitemap_url:
            parser.error("--sitemap-url is required unless --dry-run is set")
        run_site_audit(
            sitemap_url=args.sitemap_url,
            dry_run=args.dry_run,
            days=args.days,
            stale_months=args.stale_months,
            include_patterns=args.include,
            exclude_patterns=args.exclude,
            output_dir=args.output,
            create_issue=args.create_issue,
        )
    elif args.pipeline == "apply-fixes":
        cats = args.categories.split(",") if args.categories else None
        run_apply_fixes(
            dry_run=args.dry_run,
            audit_date=args.audit_date,
            portfolio_dir=args.portfolio_dir,
            categories=cats,
            output_dir=args.output,
        )
    elif args.pipeline == "apply-portfolio-fixes":
        cats = args.categories.split(",") if args.categories else None
        run_apply_portfolio_fixes(
            dry_run=args.dry_run,
            audit_date=args.audit_date,
            portfolio_dir=args.portfolio_dir or "../your-portfolio-repo",
            categories=cats,
            output_dir=args.output,
        )


if __name__ == "__main__":
    main()
