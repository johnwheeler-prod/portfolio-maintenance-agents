// Site audit types
export interface SiteSummary {
  generated_date: string;
  total_sitemap_urls: number;
  filtered_urls: number;
  audited_pages: number;
  failed_pages: number;
  mean_score: number;
  score_distribution: ScoreDistribution;
  top_cross_site_findings: CrossSiteFinding[];
  priority_pages: PriorityPage[];
}

export interface ScoreDistribution {
  excellent: number;
  good: number;
  needs_work: number;
  poor: number;
}

export interface CrossSiteFinding {
  title: string;
  count: number;
  pages: { url: string; severity: Severity }[];
}

export interface PriorityPage {
  url: string;
  score: number;
}

// SEO report types (per-page)
export interface SeoReport {
  audit_date: string;
  page_url: string;
  overall_score: number;
  summary: string;
  findings: Finding[];
  aeo_analysis: AeoAnalysis;
  quick_wins: string[];
}

export interface Finding {
  id: number;
  category: FindingCategory;
  severity: Severity;
  effort: Effort;
  title: string;
  description: string;
  recommendation: string;
  current_state: string;
  suggested_fix: string;
}

export type FindingCategory =
  | "on_page_seo"
  | "content_quality"
  | "aeo_readiness"
  | "schema_markup"
  | "technical_seo";

export type Severity = "high" | "medium" | "low";
export type Effort = "low" | "medium" | "high";

export interface AeoAnalysis {
  featured_snippet_ready: boolean;
  featured_snippet_candidates: SnippetCandidate[];
  paa_targets: PaaTarget[];
  schema_recommendations: SchemaRecommendation[];
}

export interface SnippetCandidate {
  query: string;
  current_format: string;
  recommended_format: "paragraph" | "list" | "table";
  suggested_content: string;
}

export interface PaaTarget {
  question: string;
  currently_addressed: boolean;
  suggested_answer: string;
}

export interface SchemaRecommendation {
  type: string;
  rationale: string;
  priority: Severity;
}

// GSC data types
export interface GscData {
  page_url: string;
  site_url: string;
  date_range: { start: string; end: string };
  queries: GscQuery[];
  page_metrics: GscMetrics;
}

export interface GscQuery {
  query: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

export interface GscMetrics {
  total_clicks: number;
  total_impressions: number;
  average_ctr: number;
  average_position: number;
}

// Portfolio audit types
export interface PortfolioState {
  last_audit_date: string;
  overall_freshness_score: number;
  finding_count: number;
  finding_titles: string[];
  quick_wins: string[];
}

// Content brief types
export interface ContentBrief {
  title: string;
  target_keyword: string;
  search_intent: string;
  brief: string;
  priority: Severity;
}

// Sitemap types
export interface SitemapEntry {
  url: string;
  lastmod: string;
  priority: string;
  changefreq: string;
}

// Trend data for charts
export interface TrendPoint {
  date: string;
  score: number;
}

// Pipeline metadata
export type PipelineId = "site-audit" | "seo-audit" | "portfolio-audit" | "content-plan";

export interface PipelineInfo {
  id: PipelineId;
  name: string;
  description: string;
  workflowFile: string;
  outputDir: string;
}
