# Agent Orchestration Project Brief
> **New users:** Update the "Who I Am" and "Tool Stack" sections below with your own context before using this as a session prompt.
>
> Feed this file to Claude Code at the start of every session:
> `"Read BRIEF.md and use it as context for everything we build in this session"`

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
| Google Analytics | Full access | Traffic, behavior, conversion data |
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
my-agents/
├── .github/workflows/
│   ├── weekly-content-pipeline.yml     # Monthly, 1st of month, 8:00 AM UTC
│   ├── weekly-portfolio-audit.yml      # Monthly, 7th of month, 9:00 AM UTC
│   ├── monthly-seo-audit.yml           # Monthly, 1st of month, 9:00 AM UTC
│   └── monthly-apply-fixes.yml         # After site-audit completes (or manual dispatch)
├── agents/
│   ├── search_console_fetcher.py       # Pulls query data from GSC API
│   ├── analytics_fetcher.py            # Pulls per-page query data from GSC
│   ├── content_planner.py              # Generates 4 content briefs + internal linking via Claude
│   ├── content_freshness_checker.py    # Flags pages ≥10 months old for refresh via Claude
│   ├── pagespeed_fetcher.py            # Fetches Lighthouse scores via PSI API
│   ├── seo_auditor.py                  # Audits pages for SEO/AEO via Claude
│   ├── portfolio_auditor.py            # Synthesizes PSI scores + page content via Claude
│   ├── site_crawler.py                 # Fetches and filters XML sitemaps
│   └── fix_applier.py                  # Generates code patches from audit findings
├── prompts/
│   ├── content_brief_template.md       # 4 briefs + internal linking map
│   ├── content_freshness_template.md   # Stale page refresh findings
│   ├── seo_audit_template.md           # SEO/AEO audit per page
│   ├── portfolio_audit_template.md     # PSI scores + content freshness synthesis
│   ├── portfolio_freshness_template.md # Legacy content-only prompt
│   └── fix_applier_template.md         # Code patch generation
├── utils/
│   ├── claude_client.py                # Reusable Claude API wrapper
│   └── prompt_loader.py                # Loads prompt templates with {{variable}} substitution
├── outputs/                            # Generated reports (gitignored)
├── memory/
│   └── last_audit_state.json           # Portfolio audit score history for trend detection
├── orchestrator.py                     # CLI entry point — chains agents into pipelines
├── BRIEF.md                            # This file — session context for Claude Code
├── NEXT_STEPS.md                       # Pending manual tasks and setup steps
└── README.md                           # Comprehensive setup and usage docs
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

## The Five Pipelines

### Pipeline 1: Content Planning
**Trigger:** Monthly (1st of month) GitHub Actions cron, or manual
**Chain:** `search_console_fetcher` → `content_planner` → JSON briefs (4 total, with internal linking map) + GH issue

### Pipeline 2: SEO/AEO Audit (single page)
**Trigger:** Manual
**Chain:** `analytics_fetcher` + page fetch → `seo_auditor` → JSON report + GH issue

### Pipeline 3: Portfolio Audit
**Trigger:** Monthly (7th of month) GitHub Actions cron, or manual
**Chain:** `pagespeed_fetcher` (PSI API) + page fetch → `portfolio_auditor` (Claude) → scored findings + GH issue + memory state (score history for trend detection)

### Pipeline 4: Site Audit (full sitemap)
**Trigger:** Monthly (1st of month) GitHub Actions cron, or manual
**Chain:** `site_crawler` → per-page `seo_auditor` → JSON summary + GH issues

### Pipeline 5: Apply Fixes
**Trigger:** Automatically after site-audit completes, or manual dispatch
**Chain:** reads site-audit findings → `fix_applier` (per category, with build validation) → single combined PR on `[your-portfolio-repo]`

All pipelines support `--dry-run` (sample data, no API calls) and `--output` (custom output directory).

---

## Environment Variables

Set as GitHub Actions secrets and in local `.env` (gitignored):

```
ANTHROPIC_API_KEY=               # Claude API key
GOOGLE_SERVICE_ACCOUNT_JSON=     # Base64-encoded service account JSON
GSC_PROPERTY_URL=                # e.g. https://yoursite.com
PORTFOLIO_GITHUB_TOKEN=          # Fine-grained PAT for [your-portfolio-repo] (Actions only)
GA4_PROPERTY_ID=                 # Not yet used
GITHUB_TOKEN=                    # Auto-provided by GitHub Actions
HUBSPOT_API_KEY=                 # For HubSpot webhook triggers (later phase)
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

- [x] Content pipeline — working locally + GitHub Actions (monthly: content_planner + content_freshness_checker)
- [x] SEO/AEO audit (single page) — working locally + part of site audit
- [x] Portfolio audit — working locally + GitHub Actions (monthly: PSI API + Claude)
- [x] Site audit (full sitemap) — working locally + GitHub Actions (monthly)
- [x] Apply fixes — working locally + GitHub Actions (after site-audit)
- [x] `PORTFOLIO_GITHUB_TOKEN` PAT — create and add as Actions secret (see README Prerequisites)
- [x] Apply-fixes end-to-end test via GitHub Actions

---

## Key Concepts

- **Prompt chaining** — outputs of one prompt become inputs to the next
- **Structured outputs** — always JSON, never prose, between agents
- **Tool use** — agents that call external APIs (Search Console, GA4) as "tools"
- **Memory and state** — using `memory/last_audit_state.json` to track what's changed
- **Human-in-the-loop** — GitHub Issues and PRs as review checkpoints
- **Orchestration vs. multi-agent** — `orchestrator.py` coordinates; individual scripts specialize
