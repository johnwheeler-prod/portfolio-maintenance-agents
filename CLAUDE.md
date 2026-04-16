# Agent Orchestration Project — Claude Code Context
> **New users:** Update the "Who I Am" and "Tool Stack" sections below with your own context before using this file.
>
> This file is automatically read by Claude Code at the start of every session.

---

## Who I Am and What We're Building

I'm a web developer and solutions architect building a personal agent orchestration framework to automate website maintenance, content planning, and SEO/AEO optimization. This repo is also a learning project — I want to deeply understand agent orchestration patterns so I can apply them professionally.

This is not a throwaway experiment. Code should be clean, well-commented, and structured so it can grow over time and be shown as portfolio work.

---

## My Tool Stack

| Tool | Access Level | Purpose in This Project |
|------|-------------|------------------------|
| Claude API | Anthropic Pro subscription + API key | The AI brain for all agents |
| Claude Code | Anthropic Pro subscription | Primary development environment |
| Google Search Console | Full access | Query data, impressions, rankings, CTR |
| Google Analytics 4 | Full access | Per-post pageview data for brief allocation |
| PageSpeed Insights | API key | Lighthouse scores for portfolio audit |
| HubSpot | Employee personal portal | Workflow triggers, contact data, webhooks |
| Personal website | Full ownership (`[your-portfolio-repo]`) | Primary target for maintenance and SEO agents |
| GitHub + GitHub Actions | Free | Scheduling, triggers, CI/CD for agent runs |

**Constraints:**
- No paid third-party automation tools (no Zapier, no n8n, no Make)
- Everything must work within free tiers or tools I already have
- Python for scripts

---

## Repo Structure

```
portfolio-maintenance-agents/
├── .github/workflows/
│   ├── weekly-content-pipeline.yml          # Monthly, 1st of month, 8:00 AM UTC
│   ├── weekly-portfolio-audit.yml           # Monthly, 7th of month, 9:00 AM UTC
│   ├── monthly-seo-audit.yml                # Monthly, 1st of month, 9:00 AM UTC
│   ├── monthly-apply-fixes.yml              # After site-audit completes (or manual dispatch)
│   └── monthly-apply-portfolio-fixes.yml    # After portfolio-audit completes (or manual dispatch)
├── agents/
│   ├── search_console_fetcher.py            # Pulls query data from GSC API
│   ├── analytics_fetcher.py                 # Pulls per-page query data from GSC
│   ├── ga4_fetcher.py                       # Pulls per-post pageview data from GA4
│   ├── content_planner.py                   # Generates 4 content briefs + internal linking via Claude
│   ├── content_freshness_checker.py         # Flags pages ≥10 months old for refresh via Claude
│   ├── pagespeed_fetcher.py                 # Fetches Lighthouse scores via PSI API
│   ├── seo_auditor.py                       # Audits pages for SEO/AEO via Claude
│   ├── portfolio_auditor.py                 # Synthesizes PSI scores + page content via Claude
│   ├── site_crawler.py                      # Fetches and filters XML sitemaps
│   └── fix_applier.py                       # Generates code patches from audit findings
├── prompts/
│   ├── content_brief_template.md            # 4 briefs + internal linking map
│   ├── content_freshness_template.md        # Stale page refresh findings
│   ├── seo_audit_template.md                # SEO/AEO audit per page
│   ├── portfolio_audit_template.md          # PSI scores + content freshness synthesis
│   ├── portfolio_freshness_template.md      # Legacy content-only prompt
│   ├── fix_applier_template.md              # Code patch generation (SEO findings)
│   ├── portfolio_fix_applier_template.md    # Code patch generation (PSI/Lighthouse findings)
│   └── fix_build_repair_template.md         # Build error correction
├── utils/
│   ├── claude_client.py                     # Reusable Claude API wrapper
│   └── prompt_loader.py                     # Loads prompt templates with {{variable}} substitution
├── outputs/                                 # Generated reports (gitignored)
├── config/
│   ├── seed_queries.json                    # Fallback queries when GSC returns no data
│   └── portfolio_source_files.json          # Maps PSI categories → source files to patch
├── memory/
│   └── last_audit_state.json                # Portfolio audit score history for trend detection
├── orchestrator.py                          # CLI entry point — chains agents into pipelines
├── CLAUDE.md                                # This file — auto-loaded by Claude Code each session
├── NEXT_STEPS.md                            # Pending manual tasks and setup steps
└── README.md                                # Comprehensive setup and usage docs
```

---

## Core Architectural Patterns

### 1. Structured Prompts with Variable Slots
Prompts live in `/prompts/` as markdown files with `{{variable_name}}` placeholders.
A utility function loads the template and substitutes variables before calling Claude.

### 2. Structured JSON Outputs
Every agent prompt instructs Claude to return valid JSON, not prose.
This makes outputs machine-readable and chainable to the next agent.

### 3. Plan-Then-Execute Pattern
For agents that make changes (vs. just reporting), split into two steps:
1. Agent produces a plan as JSON
2. Human reviews the plan (via PR or issue)
3. Execution only happens after validation

### 4. Orchestrator Passes Outputs as Inputs
`orchestrator.py` reads the JSON output of each agent and passes relevant fields
as variables into the next agent's prompt template. Data flows forward through
the pipeline — no agent calls another agent directly.

### 5. Human-in-the-Loop for Production Changes
Anything that touches the live website goes through a GitHub PR or creates a
GitHub Issue for review. Agents prepare changes; humans approve them.

---

## The Six Pipelines

### Pipeline 1: Content Planning
**Trigger:** Monthly (1st of month) GitHub Actions cron, or manual
**Chain:** `search_console_fetcher` + `ga4_fetcher` (optional) → `content_planner` (4 briefs, GA4-split between popular/weak topics) + `content_freshness_checker` → writes draft `.md` files to portfolio drafts dir + GH issue

### Pipeline 2: SEO/AEO Audit (single page)
**Trigger:** Manual
**Chain:** `analytics_fetcher` + page fetch → `seo_auditor` → JSON report + GH issue

### Pipeline 3: Portfolio Audit
**Trigger:** Monthly (7th of month) GitHub Actions cron, or manual
**Chain:** `pagespeed_fetcher` (PSI API) + page fetch → `portfolio_auditor` (Claude) → scored findings + GH issue + memory state (score history for trend detection)

### Pipeline 4: Site Audit (full sitemap)
**Trigger:** Monthly (1st of month) GitHub Actions cron, or manual
**Chain:** `site_crawler` → per-page `seo_auditor` → JSON summary + GH issues

### Pipeline 5: Apply Fixes (SEO)
**Trigger:** Automatically after site-audit completes, or manual dispatch
**Chain:** reads site-audit findings → `fix_applier` (per SEO category, with build validation) → single combined PR on `[your-portfolio-repo]`

### Pipeline 6: Apply Portfolio Fixes (PSI/Lighthouse)
**Trigger:** Automatically after portfolio-audit completes, or manual dispatch
**Chain:** reads portfolio-audit findings → `fix_applier` using `portfolio_fix_applier_template.md` (per PSI category, with build validation) → single combined PR on `[your-portfolio-repo]`
Source files per category configured in `config/portfolio_source_files.json`.

All pipelines support `--dry-run` (sample data, no API calls) and `--output` (custom output directory).

---

## Environment Variables

Set as GitHub Actions secrets and in local `.env` (gitignored):

```
ANTHROPIC_API_KEY=               # Claude API key
GOOGLE_SERVICE_ACCOUNT_JSON=     # Base64-encoded service account JSON
GSC_PROPERTY_URL=                # e.g. https://yoursite.com
GA4_PROPERTY_ID=                 # Numeric GA4 property ID (optional — enables GA4-split briefs)
PAGESPEED_API_KEY=               # Google API key with PSI API enabled
PORTFOLIO_URL=                   # e.g. https://yoursite.com
PORTFOLIO_REPO=                  # e.g. your-username/your-portfolio
PORTFOLIO_GITHUB_TOKEN=          # Fine-grained PAT for [your-portfolio-repo] (Actions only)
SITEMAP_URL=                     # e.g. https://yoursite.com/sitemap-index.xml
GITHUB_TOKEN=                    # Auto-provided by GitHub Actions
```

---

## Session Instructions for Claude Code

**When starting a new session:**
1. Read this file first
2. Check what already exists in the repo before creating anything new
3. Follow the repo structure above — don't invent new directories
4. All prompts go in `/prompts/`, all agent logic in `/agents/`
5. When writing agent scripts, always include the Claude API call via `utils/claude_client.py`
6. Test scripts should be runnable locally with `python agents/[script].py --dry-run`

**Code standards:**
- Python 3.10+
- Type hints on all functions
- Docstrings on all classes and functions
- Error handling with informative messages (don't silently fail)
- Print progress to stdout so GitHub Actions logs are readable
- JSON outputs should be pretty-printed for readability

**When I ask you to build something new:**
- First confirm it fits the existing structure
- Write the prompt template before the agent script
- Test the prompt template with a hardcoded example before wiring up live data

**Maintaining NEXT_STEPS.md:**
- When a task is completed that had follow-up manual steps (secret creation, PAT setup, external service config, testing checklists), add those steps to `NEXT_STEPS.md`
- When completing work that resolves items in `NEXT_STEPS.md`, check them off or remove them
- `NEXT_STEPS.md` is the single place for "things the human needs to do outside Claude Code"
- Keep it concise and actionable — step-by-step instructions, not discussion

---

## Current Status

- [x] Content pipeline — working (monthly: GSC + GA4 + content_planner + content_freshness_checker + draft writer)
- [x] SEO/AEO audit (single page) — working locally + part of site audit
- [x] Portfolio audit — working (monthly: PSI API + Claude + score trend detection)
- [x] Site audit (full sitemap) — working (monthly)
- [x] Apply fixes (SEO) — working (after site-audit: per-category patches → single combined PR)
- [x] Apply portfolio fixes (PSI) — working (after portfolio-audit: per-category patches → single combined PR)
- [x] GA4 integration — working (content pipeline step 1b; graceful fallback if not configured)
- [ ] Dashboard (`dashboard/`) — Next.js, local only; Vercel deploy planned once pipelines have stable data

---

## Key Concepts

- **Prompt chaining** — outputs of one prompt become inputs to the next
- **Structured outputs** — always JSON, never prose, between agents
- **Tool use** — agents that call external APIs (Search Console, GA4, PSI) as "tools"
- **Memory and state** — `memory/last_audit_state.json` tracks month-over-month score trends
- **Human-in-the-loop** — GitHub Issues and PRs as review checkpoints
- **Orchestration vs. multi-agent** — `orchestrator.py` coordinates; individual scripts specialize
