# Next Steps

---

## Current Action Items

All pipelines are set up and tested. Nothing blocking.

---

## Planned / Future

Items queued for later — not blocking current pipelines.

### Deploy dashboard to Vercel

The Next.js dashboard in `dashboard/` currently only runs locally. Once a few months of pipeline data are flowing and the local view isn't cutting it, deploy to Vercel.

- Connect this repo to Vercel, point build at `dashboard/`
- Dashboard auto-updates as pipeline runs commit new data

Hold off until pipelines are stable and running regularly.

---

## Archive

Previously tracked items that are complete or no longer relevant.

### ✓ All pipelines tested end-to-end

PageSpeed Insights API key configured, `PORTFOLIO_GITHUB_TOKEN` PAT created (used by both apply-fixes and content pipeline), all secrets confirmed in GitHub Actions, all pipelines manually dispatched and verified.

### ✓ Repository and GitHub Actions setup

Repo created, GitHub Actions enabled, workflow permissions set to read/write.

### ✓ Biweekly content pipeline

Was biweekly (even ISO weeks). Converted to monthly with 4 briefs + internal linking map + content freshness sub-agent.

### ✓ Weekly portfolio audit

Was weekly freshness-only. Rebuilt as a monthly PSI-based audit covering performance, accessibility, best practices, and SEO with score trend detection.

### ✓ Apply-fixes merge conflict issue

Was creating one PR per category (3 PRs). Consolidated into a single combined PR on `fix/seo-YYYY-MM-DD` branch, eliminating merge conflicts.

### ✓ Content drafter agent

Content briefs are now written directly as skeleton draft `.md` files to `[your-portfolio-repo]/src/content/blog/drafts/` by `create_portfolio_drafts()` in `orchestrator.py`. The content pipeline workflow (`weekly-content-pipeline.yml`) checks out the portfolio repo using `PORTFOLIO_GITHUB_TOKEN` and commits the drafts after each run. Each draft includes frontmatter (`draft: true`), an HTML comment with brief details and internal linking notes (to both new and existing posts), and H2 skeleton sections.

### ✓ Apply-fixes audit churn

Added severity filter (`high`/`medium` only) to `_filter_findings_for_category()` — low-severity findings are reported but never patched. Tightened `fix_applier_template.md` (allow empty patches, stricter `title_meta` constraint) and `seo_audit_template.md` (confidence threshold, severity definitions).

### ✓ Content freshness date handling

Clarified `content_freshness_template.md`: publication dates in the past are normal and expected — only flag stale *body text* temporal language (e.g. "a little over a year ago", unresolved forward-looking claims).

### ✓ Internal linking across full sitemap

Content briefs now include linking opportunities to all existing blog posts, not just the 4 new briefs. The sitemap is fetched once and `_extract_blog_posts()` derives slug + title for use in the `content_brief_template.md` prompt via `{{existing_posts_json}}`.

### ✓ Sitemap with lastmod support

The pipeline requires a sitemap with `<lastmod>` dates for freshness tracking. Blog posts should emit `<lastmod>` from an `updatedDate` field (falling back to `pubDate`). See Prerequisites in README for details.
