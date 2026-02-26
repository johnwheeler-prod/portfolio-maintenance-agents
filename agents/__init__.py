"""Agents package — specialized modules for data fetching and AI-powered analysis.

Each agent is a standalone module that either fetches data from an external source
(Google Search Console, sitemaps, web pages) or runs Claude-powered analysis against
a prompt template. Agents return structured JSON and are orchestrated by orchestrator.py.
"""

__all__ = [
    "analytics_fetcher",
    "content_planner",
    "fix_applier",
    "portfolio_auditor",
    "search_console_fetcher",
    "seo_auditor",
    "site_crawler",
]
