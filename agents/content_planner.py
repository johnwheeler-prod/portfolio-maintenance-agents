"""Content Planner — generates content briefs from Search Console query data.

Takes the JSON output of search_console_fetcher.py, loads the content brief
prompt template, calls Claude to analyze the queries, and outputs structured
content briefs as JSON.

Usage:
    python agents/content_planner.py --input outputs/gsc_data.json
    python agents/content_planner.py --dry-run                        # Uses sample data
    python agents/content_planner.py --dry-run --output outputs/briefs/
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Add project root to path so utils are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.search_console_fetcher import fetch_queries_dry_run
from utils.claude_client import call_claude_json
from utils.prompt_loader import load_prompt


def generate_briefs(
    gsc_data: dict[str, Any],
    existing_posts: list[dict[str, Any]] | None = None,
    count: int = 4,
    ga4_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate content briefs by sending GSC data through Claude.

    Loads the content_brief_template.md prompt, populates it with the
    query data, site URL, existing blog posts for internal linking, and
    optional GA4 pageview data for popularity-informed brief allocation.

    Args:
        gsc_data: The output dict from search_console_fetcher, containing
            'site_url' and 'queries' fields.
        existing_posts: List of dicts with 'url', 'slug', and 'title' keys
            for existing blog posts. Used for internal linking suggestions.
        count: Number of briefs to generate (default 4). Pass a lower value
            when existing drafts are already taking up some of the 4-draft cap.
        ga4_data: Optional output dict from ga4_fetcher, containing a 'posts'
            list ranked by pageviews. When provided, Claude splits briefs
            between reinforcing popular topics and shoring up weaker ones.

    Returns:
        Parsed JSON dict of content briefs from Claude, matching the
        schema defined in the prompt template.

    Raises:
        json.JSONDecodeError: If Claude's response is not valid JSON.
        ValueError: If gsc_data is missing required fields.
    """
    site_url = gsc_data.get("site_url")
    queries = gsc_data.get("queries")

    if not site_url:
        raise ValueError("gsc_data missing 'site_url' field.")
    if not queries:
        raise ValueError("gsc_data missing 'queries' field or queries list is empty.")

    print(f"[content_planner] Generating {count} brief(s) for {len(queries)} queries")
    print(f"[content_planner] Site: {site_url}")
    if existing_posts:
        print(f"[content_planner] {len(existing_posts)} existing posts available for linking")
    if ga4_data:
        post_count = len(ga4_data.get("posts", []))
        print(f"[content_planner] GA4 pageview data: {post_count} post(s)")

    # Format query data as readable JSON for the prompt
    query_data_str = json.dumps(queries, indent=2)
    existing_posts_str = json.dumps(existing_posts or [], indent=2)

    # Format GA4 data — fall back to a note if not provided
    if ga4_data and ga4_data.get("posts"):
        post_performance_str = json.dumps(ga4_data["posts"], indent=2)
    else:
        post_performance_str = (
            "Not available — prioritize entirely by GSC impressions and position."
        )

    prompt = load_prompt(
        "content_brief_template.md",
        query_data=query_data_str,
        site_url=site_url,
        existing_posts_json=existing_posts_str,
        brief_count=str(count),
        post_performance_json=post_performance_str,
    )

    briefs = call_claude_json(prompt)

    opportunity_count = len(briefs.get("opportunities", []))
    print(f"[content_planner] Claude returned {opportunity_count} content briefs")

    return briefs


def save_briefs(briefs: dict[str, Any], output_dir: str | None = None) -> Path:
    """Save content briefs to a dated output directory.

    Writes the briefs JSON to outputs/content_briefs/YYYY-MM-DD/briefs.json,
    or to a custom directory if specified.

    Args:
        briefs: The content briefs dict from generate_briefs().
        output_dir: Optional custom output directory path.

    Returns:
        The Path where the briefs file was written.
    """
    if output_dir:
        out_path = Path(output_dir)
    else:
        today = date.today().isoformat()
        out_path = Path("outputs") / "content_briefs" / today

    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / "briefs.json"
    file_path.write_text(json.dumps(briefs, indent=2), encoding="utf-8")

    print(f"[content_planner] Briefs saved to {file_path}")
    return file_path


def main() -> None:
    """CLI entry point for the content planner."""
    parser = argparse.ArgumentParser(
        description="Generate content briefs from Search Console query data."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to GSC data JSON file (output of search_console_fetcher.py).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample GSC data instead of reading from file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory. Defaults to outputs/content_briefs/YYYY-MM-DD/.",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Print the populated prompt and exit without calling Claude.",
    )
    args = parser.parse_args()

    # Load GSC data
    if args.dry_run:
        gsc_data = fetch_queries_dry_run()
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"[content_planner] Error: input file not found: {input_path}")
            sys.exit(1)
        gsc_data = json.loads(input_path.read_text(encoding="utf-8"))
    else:
        print("[content_planner] Error: provide --input <file> or --dry-run")
        sys.exit(1)

    # --print-prompt mode: show the populated prompt without calling Claude
    if args.print_prompt:
        query_data_str = json.dumps(gsc_data.get("queries", []), indent=2)
        prompt = load_prompt(
            "content_brief_template.md",
            query_data=query_data_str,
            site_url=gsc_data.get("site_url", ""),
        )
        print(prompt)
        return

    # Generate and save briefs
    briefs = generate_briefs(gsc_data)
    save_briefs(briefs, output_dir=args.output)

    # Print summary to stdout
    for opp in briefs.get("opportunities", []):
        print(
            f"  #{opp['rank']}: \"{opp['target_query']}\" "
            f"(pos {opp['current_position']}, {opp['impressions']} imp) "
            f"→ {opp['content_action']}"
        )


if __name__ == "__main__":
    main()
