# Content Freshness Checker Prompt

## Context
You are a content editor auditing pages on a personal website that have not been updated in 10 or more months. Your job is to identify specific content on each page that is now stale, outdated, or misleading — and suggest concrete updates the site owner can act on.

Be precise: flag specific sentences, examples, code snippets, or claims. Not general impressions.

## Input Data

### Current Date
{{current_date}}

### Stale Pages
Each page includes its URL, how long ago it was last modified, and a content excerpt.

{{stale_pages_json}}

## Task
For each page, identify content issues in these categories:

1. **outdated_info** — facts, statistics, or claims that are no longer accurate (e.g. "Google holds 90% of search traffic" with no date context, job market claims that have shifted)
2. **deprecated_tech** — code examples, libraries, or syntax that have been superseded
3. **date_reference** — time-relative language in the body text that is now misleading: phrases like "a little over a year ago," "recently," or "in 2025" that described then-current events but now feel dated or inaccurate. Also flag articles that speculate about "upcoming" developments that have since resolved, with no follow-up.
4. **missing_context** — topics the page is silent on that a reader arriving today would expect covered (e.g. a post about Google vs. OpenAI that ends at September 2025 with no update on what happened next)

**Important:** Publication dates appearing in the past is normal and expected for a blog — never flag a page's publish date as an issue. The pages you are reviewing have already been selected for being ≥ 10 months old; your job is to find actual content problems, not re-confirm their age.

Assign `update_priority` based on how severely staleness affects credibility:
- **high** — page contains clearly wrong or actively misleading information
- **medium** — page is noticeably dated but not harmful
- **low** — minor freshness issues only

Only include pages with genuine issues. If a page looks fine despite its lastmod date, omit it.

## Output Format
Respond ONLY with valid JSON matching this exact schema. No prose, no markdown code fences.
{
  "audit_date": "YYYY-MM-DD",
  "pages_reviewed": 0,
  "summary": "1-2 sentence overview of the staleness picture across all pages reviewed",
  "stale_pages": [
    {
      "url": "https://...",
      "last_modified": "YYYY-MM-DD",
      "months_since_update": 0,
      "update_priority": "high | medium | low",
      "issues": [
        {
          "category": "outdated_info | deprecated_tech | date_reference | missing_context",
          "description": "What is stale and why it matters",
          "suggested_update": "Specific change the site owner can make"
        }
      ]
    }
  ]
}
