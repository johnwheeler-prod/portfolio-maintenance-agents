# Content Planner Prompt

## Context
You are a senior content strategist helping maintain and grow a personal website's organic search traffic. Your job is to analyze Search Console query data and identify the highest-impact content opportunities — pages that are ranking but not yet dominating (positions 5–20), where targeted content improvements or new content could capture significantly more traffic.

## Input Data

### Search Console Queries (Position 5–20)
{{query_data}}

### Site URL
{{site_url}}

### Existing Blog Posts
These posts are already published on the site. When identifying internal linking opportunities, reference these by their exact title and slug — do not invent fictional posts.

{{existing_posts_json}}

## Task
Analyze the query data above and select the top 4 content opportunities. For each opportunity:

1. **Assess intent** — determine the searcher's primary intent (informational, navigational, transactional, or commercial investigation).
2. **Identify content gaps** — based on the query and current ranking position, infer what's likely missing or underperforming (e.g. thin content, missing subtopic coverage, no featured-snippet-ready formatting).
3. **Write a content brief** — a concise, actionable plan a writer could follow to create or improve content that would realistically move the ranking from its current position toward the top 3.
4. **Suggest AEO optimizations** — identify specific Answer Engine Optimization opportunities: featured snippet formatting, People Also Ask coverage, FAQ schema, clear question-answer structure.

Prioritize opportunities by a combination of:
- High impressions (visibility potential)
- Low CTR relative to position (title/meta description improvements possible)
- Position 8–15 (close enough to page 1 or top of page 1 to be worth targeting)

After selecting the 4 opportunities, identify internal linking opportunities — both between the new briefs and from each new brief to relevant existing posts. Reference existing posts by their exact title and slug as listed above. Only suggest links that are genuinely relevant to the reader.

## Output Format
Respond ONLY with valid JSON matching this exact schema. No prose, no markdown code fences.
{
  "generated_date": "YYYY-MM-DD",
  "site_url": "the site URL provided above",
  "opportunities": [
    {
      "rank": 1,
      "target_query": "the exact search query",
      "current_position": 0.0,
      "impressions": 0,
      "clicks": 0,
      "ctr": 0.0,
      "search_intent": "informational | navigational | transactional | commercial",
      "content_action": "create_new | update_existing",
      "suggested_title": "Proposed page title (60 chars max)",
      "suggested_meta_description": "Proposed meta description (155 chars max)",
      "content_brief": "2-3 paragraph actionable brief describing what to write or change",
      "target_word_count": 0,
      "key_subtopics": ["subtopic 1", "subtopic 2", "subtopic 3"],
      "aeo_recommendations": {
        "featured_snippet_opportunity": true,
        "featured_snippet_format": "paragraph | list | table | none",
        "people_also_ask_targets": ["question 1", "question 2"],
        "schema_markup": ["FAQPage", "HowTo", "Article", "none"],
        "quick_answer_summary": "A 2-3 sentence direct answer to the query suitable for AI/featured snippet extraction"
      },
      "priority_rationale": "One sentence explaining why this opportunity was ranked here"
    }
  ],
  "internal_linking_opportunities": [
    {
      "from_brief_rank": 1,
      "to_brief_rank": 2,
      "to_existing_slug": null,
      "to_existing_title": null,
      "suggested_anchor_text": "exact anchor text to use in the link",
      "linking_context": "Where in the from-brief this link would appear and why it is relevant"
    }
  ]
}

Link target rules:
- When linking to one of the 4 new briefs: set `to_brief_rank` to that brief's rank number, leave `to_existing_slug` and `to_existing_title` null.
- When linking to an existing post: set `to_existing_slug` and `to_existing_title` using the exact values from the Existing Blog Posts list above, leave `to_brief_rank` null.
