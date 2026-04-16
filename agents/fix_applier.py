"""Fix Applier — generates code patches from SEO audit findings.

Takes grouped audit findings for a single category and the relevant source
file contents, sends them through Claude, and returns structured file patches
that can be applied to the portfolio repository.

Usage:
    # Usually called from the orchestrator, but can be run standalone:
    python agents/fix_applier.py --category robots_txt --findings findings.json --source-dir ../your-portfolio-repo
    python agents/fix_applier.py --dry-run --category title_meta
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Add project root to path so utils are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.claude_client import call_claude_json
from utils.prompt_loader import load_prompt


# Mapping of human-readable category names for prompts
CATEGORY_LABELS = {
    "robots_txt": "robots.txt domain references",
    "title_meta": "title tags and meta descriptions",
    "schema": "structured data / JSON-LD schema",
}


def generate_fixes(
    category: str,
    findings: list[dict[str, Any]],
    source_files: dict[str, str],
    site_url: str = os.environ.get("PORTFOLIO_URL", "https://yoursite.com"),
) -> dict[str, Any]:
    """Generate code patches for a category of SEO findings.

    Calls Claude with the findings and current source files, requesting
    minimal file patches that address the identified issues.

    Args:
        category: The fix category (robots_txt, title_meta, schema).
        findings: List of finding dicts from SEO audit reports.
        source_files: Dict of {relative_path: file_content} for relevant files.
        site_url: The target site URL for context.

    Returns:
        Parsed JSON dict with category, pr_title, pr_description, and patches.

    Raises:
        json.JSONDecodeError: If Claude's response is not valid JSON.
    """
    label = CATEGORY_LABELS.get(category, category)
    print(f"[fix_applier] Generating fixes for: {label}")

    # Format source files for the prompt
    source_block = _format_source_files(source_files)

    prompt = load_prompt(
        "fix_applier_template.md",
        category=label,
        findings_json=json.dumps(findings, indent=2),
        source_files=source_block,
        site_url=site_url,
    )

    result = call_claude_json(prompt, max_tokens=16384)

    patch_count = len(result.get("patches", []))
    print(f"[fix_applier] Generated {patch_count} file patch(es)")
    return result


def generate_fixes_dry_run(category: str) -> dict[str, Any]:
    """Return sample patches for dry-run mode without API calls.

    Produces structurally valid output matching the Claude response schema
    so the pipeline can be tested end-to-end.

    Args:
        category: The fix category (robots_txt, title_meta, schema).

    Returns:
        A dict matching the fix applier JSON schema with sample patches.
    """
    print(f"[fix_applier] DRY RUN — generating sample patches for: {category}")

    if category == "robots_txt":
        return {
            "category": "robots_txt",
            "pr_title": "Fix robots.txt domain references",
            "pr_description": (
                "## Summary\n"
                "- Replace `https://old.example.com` with `https://example.com` "
                "in Host and Sitemap directives\n\n"
                "Fixes robots.txt referencing the wrong domain, which could "
                "confuse search engine crawlers about the canonical host."
            ),
            "patches": [
                {
                    "file": "public/robots.txt",
                    "action": "replace",
                    "content": (
                        "User-agent: *\n"
                        "Allow: /\n"
                        "\n"
                        "Sitemap: https://example.com/sitemap-index.xml\n"
                    ),
                }
            ],
        }

    if category == "title_meta":
        return {
            "category": "title_meta",
            "pr_title": "Improve title tags and meta descriptions across pages",
            "pr_description": (
                "## Summary\n"
                "- Update generic title tags with keyword-focused alternatives\n"
                "- Improve meta descriptions with specific services and CTAs\n"
                "- Fix duplicate H1 tags on blog posts\n\n"
                "Addresses on-page SEO findings from the site audit regarding "
                "generic titles and weak meta descriptions across 7+ pages."
            ),
            "patches": [
                {
                    "file": "src/pages/index.astro",
                    "action": "replace",
                    "content": "[MOCK] Updated index.astro with improved title and description props",
                }
            ],
        }

    if category == "schema":
        return {
            "category": "schema",
            "pr_title": "Add BreadcrumbList schema and improve structured data",
            "pr_description": (
                "## Summary\n"
                "- Add BreadcrumbList JSON-LD schema to page layouts\n"
                "- Preserve existing Person and WebSite schema\n\n"
                "Addresses missing BreadcrumbList schema identified in the "
                "site audit across all pages."
            ),
            "patches": [
                {
                    "file": "src/components/layout/BaseHead.astro",
                    "action": "replace",
                    "content": "[MOCK] Updated BaseHead.astro with BreadcrumbList schema addition",
                }
            ],
        }

    # Fallback for unknown categories
    return {
        "category": category,
        "pr_title": f"[MOCK] Fix {category} issues",
        "pr_description": f"[MOCK] Addresses {category} findings from SEO audit.",
        "patches": [],
    }


PORTFOLIO_CATEGORY_LABELS = {
    "accessibility": "accessibility fixes",
    "performance": "performance improvements",
    "seo": "SEO improvements",
    "best_practices": "best practices improvements",
}


def generate_portfolio_fixes(
    category: str,
    findings: list[dict[str, Any]],
    source_files: dict[str, str],
    site_url: str = os.environ.get("PORTFOLIO_URL", "https://yoursite.com"),
) -> dict[str, Any]:
    """Generate code patches for a category of PSI/Lighthouse portfolio findings.

    Like generate_fixes() but uses portfolio_fix_applier_template.md and the
    PSI finding schema (audit_id, current_value, detail).

    Args:
        category: The fix category (accessibility, performance, seo, best_practices).
        findings: List of finding dicts from the portfolio audit report.
        source_files: Dict of {relative_path: file_content} for relevant files.
        site_url: The target site URL for context.

    Returns:
        Parsed JSON dict with category, pr_title, pr_description, and patches.
    """
    label = PORTFOLIO_CATEGORY_LABELS.get(category, category)
    print(f"[fix_applier] Generating portfolio fixes for: {label}")

    source_block = _format_source_files(source_files)

    prompt = load_prompt(
        "portfolio_fix_applier_template.md",
        category=label,
        findings_json=json.dumps(findings, indent=2),
        source_files=source_block,
        site_url=site_url,
    )

    result = call_claude_json(prompt, max_tokens=16384)

    patch_count = len(result.get("patches", []))
    print(f"[fix_applier] Generated {patch_count} portfolio patch(es)")
    return result


def generate_portfolio_fixes_dry_run(category: str) -> dict[str, Any]:
    """Return sample patches for dry-run testing of the portfolio fix pipeline.

    Produces structurally valid output matching the Claude response schema.

    Args:
        category: The fix category (accessibility, performance, seo, best_practices).

    Returns:
        A dict matching the fix applier JSON schema with sample patches.
    """
    print(f"[fix_applier] DRY RUN — generating sample portfolio patches for: {category}")

    if category == "accessibility":
        return {
            "category": "accessibility",
            "pr_title": "Fix color contrast accessibility issues",
            "pr_description": (
                "## Summary\n"
                "- Darken text colors in global stylesheet to meet WCAG AA "
                "contrast ratio (4.5:1)\n"
                "- Targets elements with insufficient contrast identified by PSI audit\n\n"
                "Addresses `color-contrast` audit failure reported by Lighthouse."
            ),
            "patches": [
                {
                    "file": "src/styles/global.css",
                    "action": "replace",
                    "content": "[MOCK] Updated global.css with improved color contrast values",
                }
            ],
        }

    if category == "performance":
        return {
            "category": "performance",
            "pr_title": "Add preload hints for critical resources",
            "pr_description": (
                "## Summary\n"
                "- Add `<link rel=\"preload\">` hints for critical fonts in head template\n"
                "- Enable image optimization in build config\n\n"
                "Addresses source-addressable performance findings from PSI audit. "
                "Redirect chain and JS bundle size issues require infrastructure changes "
                "and are not included."
            ),
            "patches": [
                {
                    "file": "src/layouts/base.html",
                    "action": "replace",
                    "content": "[MOCK] Updated base layout with resource preload hints",
                }
            ],
        }

    # Fallback for seo, best_practices, and unknown categories
    return {
        "category": category,
        "pr_title": f"[MOCK] Fix {category} issues",
        "pr_description": f"[MOCK] Addresses {category} findings from portfolio PSI audit.",
        "patches": [],
    }


def fix_build_errors(
    category: str,
    patches: list[dict[str, Any]],
    build_output: str,
    source_files: dict[str, str],
) -> dict[str, Any]:
    """Send failed patches and build errors back to Claude for correction.

    Args:
        category: The fix category (robots_txt, title_meta, schema).
        patches: The patches that caused the build failure.
        build_output: The stderr/stdout from the failed `pnpm build`.
        source_files: Dict of {relative_path: file_content} for the original files.

    Returns:
        Parsed JSON dict with category, pr_title, pr_description, and patches.
    """
    label = CATEGORY_LABELS.get(category, category)
    print(f"[fix_applier] Requesting build error repair for: {label}")

    source_block = _format_source_files(source_files)

    prompt = load_prompt(
        "fix_build_repair_template.md",
        category=label,
        source_files=source_block,
        patches_json=json.dumps(patches, indent=2),
        build_output=build_output,
    )

    result = call_claude_json(prompt, max_tokens=16384)

    patch_count = len(result.get("patches", []))
    print(f"[fix_applier] Repair generated {patch_count} corrected patch(es)")
    return result


def _format_source_files(source_files: dict[str, str]) -> str:
    """Format source files dict into a readable block for the prompt.

    Args:
        source_files: Dict of {relative_path: file_content}.

    Returns:
        Formatted string with file paths and contents.
    """
    parts = []
    for path, content in source_files.items():
        parts.append(f"### `{path}`\n```\n{content}\n```")
    return "\n\n".join(parts)


def main() -> None:
    """CLI entry point for the fix applier agent."""
    parser = argparse.ArgumentParser(
        description="Generate code patches from SEO audit findings."
    )
    parser.add_argument(
        "--category",
        type=str,
        required=True,
        choices=["robots_txt", "title_meta", "schema"],
        help="The fix category to generate patches for.",
    )
    parser.add_argument(
        "--findings",
        type=str,
        help="Path to a JSON file containing the findings list.",
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        help="Path to the portfolio repository root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample patches, skip Claude API call.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path. If not set, prints to stdout.",
    )
    args = parser.parse_args()

    if args.dry_run:
        result = generate_fixes_dry_run(args.category)
    else:
        if not args.findings or not args.source_dir:
            parser.error("--findings and --source-dir are required unless --dry-run is set")

        findings = json.loads(Path(args.findings).read_text(encoding="utf-8"))
        # Read source files based on category — simplified for standalone use
        source_files: dict[str, str] = {}
        source_dir = Path(args.source_dir)
        if source_dir.exists():
            # Read all .astro, .txt, and config files in src/
            for ext in ("*.astro", "*.txt"):
                for f in source_dir.rglob(ext):
                    rel = str(f.relative_to(source_dir))
                    source_files[rel] = f.read_text(encoding="utf-8")

        result = generate_fixes(args.category, findings, source_files)

    output_json = json.dumps(result, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"[fix_applier] Patches written to {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
