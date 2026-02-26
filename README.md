# my-agents

An open-source agent orchestration framework for automating content planning, SEO auditing, and site maintenance on a personal portfolio or blog. You configure it once, point it at your site and repo, and scheduled GitHub Actions pipelines handle the rest: generating content briefs, auditing pages for SEO/AEO issues, and opening PRs with generated fixes — all routed through GitHub Issues for human review before anything changes.

Built for developers who want to automate the repetitive parts of site maintenance without giving up control. Uses Claude as the AI backend, Google Search Console for query data, and GitHub Actions for scheduling. Everything runs in your own repo — no third-party automation platform required.

## Architecture

The orchestrator coordinates 5 pipelines. Each pipeline chains data-fetching agents with Claude-powered analysis agents. No agent calls another directly — the orchestrator passes JSON outputs forward.

```
                              orchestrator.py
                                    │
          ┌─────────────────────────┼──────────────────────────┐
          │                         │                          │
     (schedule)                (schedule)              (schedule / trigger)


  CONTENT PIPELINE · monthly
  ─────────────────────────────────────────────────────────────────────
  search_console_fetcher + sitemap fetch
        │                                    │
        ▼                                    ▼
  content_planner · Claude ·        site_crawler (stale ≥ 10 mo)
  4 briefs + internal linking map          │
  (existing + new posts)                   ▼
        │                         content_freshness_checker · Claude ·
        ▼                         stale page findings
  create_portfolio_drafts
  writes .md drafts → [your-portfolio-repo]/src/content/blog/drafts/


  SEO/AEO AUDIT · monthly, 1st
  ─────────────────────────────────────────────────────────────────────
  analytics_fetcher + page fetch
        │
        ▼
  seo_auditor · Claude ·
  scored findings per page


  PORTFOLIO AUDIT · monthly, 7th
  ─────────────────────────────────────────────────────────────────────
  pagespeed_fetcher · PSI API ·
        │
        ▼
  portfolio_auditor · Claude ·  ──►  memory/last_audit_state.json
  scores + findings                  (month-over-month trend history)


  SITE AUDIT · monthly, 1st
  ─────────────────────────────────────────────────────────────────────
  site_crawler
        │
        ▼
  seo_auditor × page · Claude ·
  per-page reports + site summary
        │
        └─────────────────────────────────────────────┐
                                                      │ triggers
  APPLY FIXES · auto after site audit, or manual      │
  ────────────────────────────────────────────────────▼────────────────
  fix_applier × category · Claude · (build-validated)
        │
        ▼
  single combined PR → [your-portfolio-repo]
```

## Repo structure

```
my-agents/
├── orchestrator.py                          # CLI entry point — chains agents into pipelines
├── agents/
│   ├── search_console_fetcher.py            # Pulls query data from Google Search Console
│   ├── analytics_fetcher.py                 # Pulls per-page query data from GSC
│   ├── content_planner.py                   # Generates 4 content briefs + internal linking via Claude
│   ├── content_freshness_checker.py         # Flags existing pages ≥10 months old via Claude
│   ├── pagespeed_fetcher.py                 # Fetches Lighthouse scores via PageSpeed Insights API
│   ├── seo_auditor.py                       # Audits a page for SEO/AEO via Claude
│   ├── portfolio_auditor.py                 # Synthesizes PSI scores + page content via Claude
│   ├── site_crawler.py                      # Fetches and filters XML sitemaps
│   └── fix_applier.py                       # Generates code patches from audit findings
├── prompts/
│   ├── content_brief_template.md            # 4 new content briefs + internal linking map
│   ├── content_freshness_template.md        # Stale page identification and refresh suggestions
│   ├── seo_audit_template.md                # SEO/AEO audit per page
│   ├── portfolio_audit_template.md          # PSI scores + content freshness synthesis
│   ├── portfolio_freshness_template.md      # Legacy content-only freshness prompt
│   ├── fix_applier_template.md              # Code patch generation
│   └── fix_build_repair_template.md         # Build error correction
├── utils/
│   ├── claude_client.py                     # Reusable Claude API wrapper
│   └── prompt_loader.py                     # Loads prompt templates with {{variable}} substitution
├── outputs/                                 # Generated reports (gitignored)
│   ├── content_briefs/YYYY-MM-DD/
│   │   ├── gsc_data.json                    # Raw Search Console queries
│   │   ├── briefs.json                      # 4 content briefs + internal linking
│   │   └── freshness_report.json            # Stale page findings
│   ├── seo_audits/YYYY-MM-DD/
│   ├── portfolio_audits/YYYY-MM-DD/
│   │   ├── psi_data.json                    # Raw PageSpeed Insights response
│   │   ├── page_content.txt                 # Fetched page text
│   │   └── portfolio_report.json            # Scored findings + quick wins
│   ├── site_audits/YYYY-MM-DD/
│   └── fix_patches/YYYY-MM-DD/
├── config/
│   └── seed_queries.json                    # Fallback queries when GSC returns no data
├── memory/
│   └── last_audit_state.json                # Portfolio audit score history for trend detection
├── .github/workflows/
│   ├── weekly-content-pipeline.yml          # Monthly, 1st of month, 8:00 AM UTC
│   ├── weekly-portfolio-audit.yml           # Monthly, 7th of month, 9:00 AM UTC
│   ├── monthly-seo-audit.yml                # Monthly, 1st of month, 9:00 AM UTC
│   └── monthly-apply-fixes.yml              # After site-audit completes (or manual dispatch)
├── BRIEF.md                                 # Claude Code session context
├── NEXT_STEPS.md                            # Pending manual tasks and setup steps
└── README.md                                # This file
```

---

## Prerequisites

Before setting up, make sure you have:

- **A public XML sitemap** at a stable URL (e.g. `https://yoursite.com/sitemap-index.xml`) with `<lastmod>` dates on each entry — these drive the freshness tracking in the content and site-audit pipelines.
- **Google Search Console** set up for your domain, with a service account that has Full access (see Setup step 3). This powers the content pipeline's query data. New sites without GSC data will fall back to `config/seed_queries.json`.
- **Blog posts as markdown files** with at least these frontmatter fields: `title` (string), `description` (string), `pubDate` (Date), `draft` (boolean). `updatedDate` (Date) is optional but improves freshness detection.
- **A portfolio repository** that this repo can read from and write to. The content pipeline writes draft `.md` files; the apply-fixes pipeline opens PRs. You'll need a fine-grained PAT (`PORTFOLIO_GITHUB_TOKEN`) with Contents read/write on that repo.

> **apply-fixes framework note:** The apply-fixes pipeline targets **Astro + pnpm** by default — the build step in `monthly-apply-fixes.yml` runs `pnpm build`, and `prompts/fix_applier_template.md` describes an Astro file structure. If your portfolio uses a different framework, update the build step in the workflow and the file structure description in the prompt template to match.

---

## Setup

### 1. Create a GitHub repository

**Option A: Using the GitHub CLI (fastest)**

```bash
cd /path/to/my-agents
gh repo create my-agents --private --source=. --push
```

**Option B: Manual setup on github.com**

1. Go to https://github.com/new
2. Name it `my-agents`, set to **Private**, do not initialize with README/.gitignore/license
3. In your terminal:

```bash
cd /path/to/my-agents
git remote add origin git@github.com:YOUR_GITHUB_USERNAME/my-agents.git
git push -u origin main
```

Verify with `git remote -v`.

### 2. Get your Anthropic API key

1. Go to https://console.anthropic.com/ and sign in
2. **API Keys** in the sidebar → **Create Key**
3. Name it `my-agents`, copy the key (`sk-ant-...`) — you won't see it again

### 3. Set up Google Search Console API access

#### 3a. Create a Google Cloud project

1. Go to https://console.cloud.google.com/
2. Project dropdown → **New Project** → name it `my-agents` → **Create**

#### 3b. Enable the Search Console API

1. **APIs & Services > Library** → search **Google Search Console API** → **Enable**

#### 3c. Create a service account

1. **IAM & Admin > Service Accounts** → **Create Service Account**
2. Name it `seo-pipeline`, click **Create and Continue**, skip optional roles, click **Done**
3. Click on the new service account → **Keys** tab → **Add Key > Create new key** → **JSON** → **Create**
4. A `.json` file downloads — keep it safe

#### 3d. Grant the service account access to Search Console

1. Go to https://search.google.com/search-console
2. Select your property → **Settings** → **Users and permissions** → **Add User**
3. Paste the service account email (`...@...iam.gserviceaccount.com`), set to **Full**, click **Add**

#### 3e. Base64-encode the credentials

```bash
cat ~/Downloads/YOUR_KEY_FILE.json | base64 | tr -d '\n'
```

Copy the output. On Linux, use `base64 -w 0` instead of `base64 | tr -d '\n'`.

The JSON key file should **not** be copied into this repo. Delete it once the base64 string is saved in `.env` and GitHub Secrets.

### 4. Configure your local environment

```bash
cp .env.example .env
```

Fill in the values:

```
ANTHROPIC_API_KEY=sk-ant-PASTE_YOUR_KEY_HERE
GOOGLE_SERVICE_ACCOUNT_JSON=PASTE_YOUR_BASE64_STRING_HERE
GSC_PROPERTY_URL=https://yoursite.com
```

Notes:
- `GSC_PROPERTY_URL` must match exactly how your site appears in Search Console (`https://yoursite.com` vs `https://www.yoursite.com` are different properties)
- No quotes around values
- `.env` is gitignored

### 5. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Verify: `python orchestrator.py --help` should show all subcommands.

### 6. Install and authenticate the GitHub CLI

```bash
brew install gh    # or see https://cli.github.com/ for other methods
gh auth login      # follow the interactive prompts
```

Create the issue labels used by `--create-issue`:

```bash
gh label create content-opportunity --color 0E8A16 --description "Content planning opportunities"
gh label create seo-audit --color 1D76DB --description "SEO/AEO audit findings"
gh label create portfolio-audit --color D93F0B --description "Portfolio freshness audit findings"
```

### 7. Set Anthropic spending guardrails

| Pipeline | Claude calls per run | Automated frequency |
|---|---|---|
| Content pipeline | 1 | Biweekly |
| SEO audit (single page) | 1 | Manual |
| Portfolio audit | 1 | Weekly |
| Site audit | 1 per page | Monthly |
| Apply fixes | 1 per category | Monthly (after site-audit) |

A single Sonnet call typically costs $0.01–$0.05. The automated runs cost roughly **$0.20–$0.60/month** combined.

1. Go to https://console.anthropic.com/settings/limits
2. Set **Monthly spend limit** to **$5.00** (more than enough)
3. Add a **usage alert** at $3.00

---

## Customizing for Your Site

### BRIEF.md

`BRIEF.md` is the Claude Code session context file — it gives Claude background on your project whenever you start a new session. Load it by telling Claude: `"Read BRIEF.md and use it as context for everything we build in this session"`.

Before using it, update two sections with your own details:

- **Who I Am and What We're Building** — describe your site, your goals, and what you want to automate
- **My Tool Stack** — list the tools and services you have access to (GSC, GA4, etc.)

Everything else (architecture patterns, pipeline descriptions, session instructions) is generic and doesn't need to change.

### seed_queries.json

`config/seed_queries.json` is used by the content pipeline when Google Search Console returns no data — typically on new sites or newly-created blog sections where GSC hasn't collected enough impressions yet.

Add target topics, keywords you want to rank for, and content areas you're interested in. The content planner uses these as seed inputs to generate briefs when live GSC data isn't available.

```json
{
  "queries": [
    "your target keyword",
    "topic you want to write about",
    "question your audience is asking"
  ]
}
```

### memory/last_audit_state.json

This file ships with example data. Run `python orchestrator.py portfolio-audit` once (with `--dry-run` first to verify the setup, then live) to populate it with your site's actual Lighthouse scores. From that point on, the portfolio audit uses this file for month-over-month trend detection.

---

## Pipelines

### Content pipeline

Two sub-agents run after the GSC fetch: **content_planner** generates 4 new content briefs with an internal linking map (referencing both new briefs and all existing blog posts by title/slug); **content_freshness_checker** crawls the sitemap, finds pages not updated in 10+ months, and flags stale body-text language. After briefs are generated, **create_portfolio_drafts** writes skeleton `.md` draft files to your portfolio's `src/content/blog/drafts/` with `draft: true` frontmatter. Both outputs are saved and optionally posted as GitHub issues. If GSC returns no data, the pipeline falls back to seed queries from `config/seed_queries.json`.

```bash
python orchestrator.py content-pipeline                                        # Live run
python orchestrator.py content-pipeline --dry-run                             # Sample data
python orchestrator.py content-pipeline --portfolio-dir ../your-portfolio-repo       # Also write drafts
python orchestrator.py content-pipeline --create-issue                        # Also open GitHub issue
python orchestrator.py content-pipeline --days 60                             # Custom lookback window
```

**Automated:** Monthly, 1st of the month at 8:00 AM UTC.

### SEO/AEO audit

Crawls the sitemap and runs a scored SEO/AEO audit on each page, producing per-page reports and a site-wide summary. Can also be run against a single page for targeted audits. Triggers the apply-fixes pipeline on completion.

```bash
python orchestrator.py site-audit --sitemap-url https://yoursite.com/sitemap-index.xml
python orchestrator.py site-audit --dry-run
python orchestrator.py seo-audit --page-url https://yoursite.com/blog/post   # single page
```

**Automated:** Monthly, 1st of the month at 9:00 AM UTC.

### Portfolio audit

Fetches Lighthouse scores from the PageSpeed Insights API (performance, accessibility, best practices, SEO), then asks Claude to prioritize the findings in the context of a developer portfolio. Also fetches the page content for a light content freshness check. Scores are persisted to memory for month-over-month trend detection.

```bash
python orchestrator.py portfolio-audit --url https://yoursite.com
python orchestrator.py portfolio-audit --dry-run
```

**Automated:** Monthly, 7th of the month at 9:00 AM UTC.

### Apply fixes

Reads the latest site-audit findings, generates code patches, and opens PRs against your portfolio repo.

> **Framework note:** The pipeline defaults to **Astro + pnpm**. For other frameworks, update the `pnpm build` step in `.github/workflows/monthly-apply-fixes.yml` and the file structure description in `prompts/fix_applier_template.md` to match your setup.

```bash
python orchestrator.py apply-fixes --dry-run
python orchestrator.py apply-fixes --portfolio-dir ../your-portfolio-repo
python orchestrator.py apply-fixes --categories robots_txt,title_meta
python orchestrator.py apply-fixes --audit-date 2026-01-15
```

**Automated:** Triggers after the monthly site-audit completes, or via manual dispatch.

All pipelines support `--dry-run` (sample data, no API calls) and `--output` (custom output directory). Most support `--create-issue` (opens a GitHub issue with findings).

---

## GitHub Actions

### Secrets

Add these in your repo's **Settings > Secrets and variables > Actions**:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Base64-encoded service account JSON |
| `GSC_PROPERTY_URL` | Your site URL exactly as it appears in GSC |
| `PAGESPEED_API_KEY` | Google API key with PageSpeed Insights API enabled |
| `PORTFOLIO_URL` | Your site's root URL (e.g. `https://yoursite.com`) — used by content pipeline and portfolio audit |
| `PORTFOLIO_REPO` | Your portfolio repo in `owner/repo` format (e.g. `your-username/your-portfolio`) — used by content pipeline and apply-fixes |
| `PORTFOLIO_GITHUB_TOKEN` | Fine-grained PAT for your portfolio repo — Contents read/write for apply-fixes PRs and content pipeline draft commits |
| `SITEMAP_URL` | Your sitemap URL (e.g. `https://yoursite.com/sitemap-index.xml`) — used by the site-audit workflow when no URL is provided at dispatch time |

`GITHUB_TOKEN` is provided automatically by GitHub Actions — no need to add it.

### Workflow permissions

1. Repo **Settings > Actions > General** → scroll to **Workflow permissions**
2. Select **Read and write permissions** → **Save**

### Workflows

| Workflow | Schedule | File |
|---|---|---|
| Monthly Content Pipeline | 1st of month, 8:00 AM UTC | `weekly-content-pipeline.yml` |
| Monthly Portfolio Audit | 7th of month, 9:00 AM UTC | `weekly-portfolio-audit.yml` |
| Monthly SEO/AEO Audit | 1st of month, 9:00 AM UTC | `monthly-seo-audit.yml` |
| Monthly Apply Fixes | After site-audit completes | `monthly-apply-fixes.yml` |

All workflows support **manual dispatch** from the Actions tab (click **Run workflow**). Use `dry_run: true` for test runs.

### Testing a workflow

1. Go to the **Actions** tab in your repo
2. Select the workflow → **Run workflow**
3. Check `dry_run` for a safe test run
4. Watch the run log; check **Artifacts** at the bottom for output files

---

## Dry runs

Dry runs use hardcoded sample data and skip all API calls — no charges, no external requests. Use them to verify everything is wired up.

```bash
python orchestrator.py content-pipeline --dry-run
python orchestrator.py seo-audit --page-url https://example.com --dry-run
python orchestrator.py portfolio-audit --dry-run
python orchestrator.py site-audit --dry-run
python orchestrator.py apply-fixes --dry-run
```

Each command should print step-by-step progress and end with `PIPELINE COMPLETE`. Output files appear in `outputs/`.

---

## Output structure

All pipeline outputs land in `outputs/` as structured JSON, organized by date:

```
outputs/
├── content_briefs/2025-06-15/
│   ├── gsc_data.json          # Raw Search Console data
│   └── content_briefs.json    # Ranked opportunities with briefs
├── seo_audits/2025-06-15/
│   ├── page_content.txt       # Fetched page HTML
│   ├── gsc_data.json          # Per-page query data
│   └── seo_report.json        # Scored findings + quick wins
├── portfolio_audits/2025-06-15/
│   └── portfolio_report.json  # Freshness score + suggested copy
├── site_audits/2025-06-15/
│   ├── sitemap_data.json      # Full sitemap
│   ├── filtered_urls.json     # URLs that passed freshness filter
│   ├── pages/                 # Per-page audit subdirectories
│   └── site_summary.json      # Aggregated scores + cross-site findings
└── fix_patches/2025-06-15/
    └── *.patch                # Generated code patches
```

---

## Cost

| Component | Estimated monthly cost |
|---|---|
| Monthly content pipeline (2–3 Claude calls + draft commits) | $0.02–$0.15 |
| Monthly portfolio audit (PSI free + 1 Claude call) | $0.01–$0.05 |
| Monthly site audit (1 Claude call per page) | $0.10–$0.50 |
| Monthly apply-fixes (1 Claude call per category) | $0.05–$0.25 |
| **Total** | **$0.18–$0.90** |

Set a $5/month hard cap on the [Anthropic dashboard](https://console.anthropic.com/settings/limits).

---

## Extending

To add a new agent:

1. Create the prompt template in `prompts/` with `{{variable}}` slots
2. Create the agent script in `agents/` — it should accept input data and return structured JSON
3. Wire it into `orchestrator.py` as a new subcommand or pipeline step
4. Add a `--dry-run` path with sample data for testing without API calls

Follow the existing pattern: agents are pure functions that take data in and return JSON out. The orchestrator handles all file I/O, sequencing, and issue creation.

---

## Troubleshooting

**"ANTHROPIC_API_KEY not found"** — Your `.env` file is missing or the key isn't set. Make sure the file exists at the project root and contains `ANTHROPIC_API_KEY=sk-ant-...` with no quotes.

**"ModuleNotFoundError: No module named 'dotenv'"** — Virtual environment isn't active. Run `source venv/bin/activate`.

**"gh: command not found"** — The `gh` CLI isn't installed or authenticated. Issue creation is optional — pipelines still save reports to `outputs/` without it.

**Google Search Console returns empty data** — Check that `GSC_PROPERTY_URL` matches your property exactly (`https://` vs `http://`, `www.` vs no `www.`). Verify the service account email has been added to your GSC property. New properties can take 24–48 hours to start collecting data. The content pipeline will automatically fall back to seed queries from `config/seed_queries.json` so it can still produce useful briefs — edit that file to match your target topics.

**Site audit finds 0 stale pages** — All pages have been updated within the `--stale-months` window (default 3). Try `--stale-months 12`.

**GitHub Actions workflow shows as disabled** — Go to the **Actions** tab and click the enable button if prompted. Newly pushed repos sometimes need manual activation.
