import { getFileContent, listDirectory } from "./github";
import type {
  SiteSummary,
  SeoReport,
  PortfolioState,
  GscData,
  TrendPoint,
  PipelineInfo,
} from "./types";

export const PIPELINES: PipelineInfo[] = [
  {
    id: "site-audit",
    name: "Site Audit",
    description: "Sitemap-based multi-page SEO/AEO audit",
    workflowFile: "monthly-seo-audit.yml",
    outputDir: "outputs/site_audits",
  },
  {
    id: "seo-audit",
    name: "SEO Audit",
    description: "Single-page SEO/AEO deep analysis",
    workflowFile: "monthly-seo-audit.yml",
    outputDir: "outputs/seo_audits",
  },
  {
    id: "portfolio-audit",
    name: "Portfolio Audit",
    description: "Portfolio freshness check with memory",
    workflowFile: "weekly-portfolio-audit.yml",
    outputDir: "outputs/portfolio_audits",
  },
  {
    id: "content-plan",
    name: "Content Plan",
    description: "GSC-driven content opportunity planning",
    workflowFile: "weekly-content-pipeline.yml",
    outputDir: "outputs/content_briefs",
  },
];

export function getPipeline(id: string): PipelineInfo | undefined {
  return PIPELINES.find((p) => p.id === id);
}

// Generic date listing for any pipeline output directory
async function getDateDirs(outputDir: string): Promise<string[]> {
  const entries = await listDirectory(outputDir);
  return entries
    .filter((e) => e.type === "dir" && /^\d{4}-\d{2}-\d{2}$/.test(e.name))
    .map((e) => e.name)
    .sort()
    .reverse();
}

// --- Site Audit ---

export async function getSiteAuditDates(): Promise<string[]> {
  return getDateDirs("outputs/site_audits");
}

export async function getSiteAuditSummary(
  date: string
): Promise<SiteSummary | null> {
  return getFileContent<SiteSummary>(
    `outputs/site_audits/${date}/site_summary.json`
  );
}

export async function getSiteAuditPageSlugs(date: string): Promise<string[]> {
  const entries = await listDirectory(`outputs/site_audits/${date}/pages`);
  return entries.filter((e) => e.type === "dir").map((e) => e.name);
}

export async function getSiteAuditPageReport(
  date: string,
  slug: string
): Promise<SeoReport | null> {
  return getFileContent<SeoReport>(
    `outputs/site_audits/${date}/pages/${slug}/seo_report.json`
  );
}

export async function getSiteAuditPageGsc(
  date: string,
  slug: string
): Promise<GscData | null> {
  return getFileContent<GscData>(
    `outputs/site_audits/${date}/pages/${slug}/gsc_data.json`
  );
}

export async function getSiteAuditTrend(): Promise<TrendPoint[]> {
  const dates = await getSiteAuditDates();
  const points: TrendPoint[] = [];

  for (const date of dates.slice(0, 12)) {
    const summary = await getSiteAuditSummary(date);
    if (summary) {
      points.push({ date, score: summary.mean_score });
    }
  }

  return points.reverse();
}

// --- SEO Audit (single-page) ---

export async function getSeoAuditDates(): Promise<string[]> {
  return getDateDirs("outputs/seo_audits");
}

export async function getSeoAuditReport(
  date: string
): Promise<SeoReport | null> {
  // Single-page audits store the report directly in the date folder
  const entries = await listDirectory(`outputs/seo_audits/${date}`);
  const reportFile = entries.find((e) => e.name === "seo_report.json");
  if (reportFile) {
    return getFileContent<SeoReport>(reportFile.path);
  }
  // Or it might be in a page subfolder
  const dirs = entries.filter((e) => e.type === "dir");
  if (dirs.length > 0) {
    return getFileContent<SeoReport>(
      `${dirs[0].path}/seo_report.json`
    );
  }
  return null;
}

export async function getSeoAuditTrend(): Promise<TrendPoint[]> {
  const dates = await getSeoAuditDates();
  const points: TrendPoint[] = [];

  for (const date of dates.slice(0, 12)) {
    const report = await getSeoAuditReport(date);
    if (report) {
      points.push({ date, score: report.overall_score });
    }
  }

  return points.reverse();
}

// --- Portfolio Audit ---

export async function getPortfolioAuditDates(): Promise<string[]> {
  return getDateDirs("outputs/portfolio_audits");
}

export async function getPortfolioState(): Promise<PortfolioState | null> {
  return getFileContent<PortfolioState>("memory/last_audit_state.json");
}

export async function getPortfolioReport(
  date: string
): Promise<PortfolioState | null> {
  // Portfolio reports may store the audit state per date
  return getFileContent<PortfolioState>(
    `outputs/portfolio_audits/${date}/audit_report.json`
  );
}

export async function getPortfolioTrend(): Promise<TrendPoint[]> {
  const dates = await getPortfolioAuditDates();
  const points: TrendPoint[] = [];

  for (const date of dates.slice(0, 12)) {
    const report = await getPortfolioReport(date);
    if (report) {
      points.push({ date, score: report.overall_freshness_score });
    }
  }

  return points.reverse();
}

// --- Content Plan ---

export async function getContentPlanDates(): Promise<string[]> {
  return getDateDirs("outputs/content_briefs");
}

export async function getContentBriefs(date: string): Promise<unknown> {
  return getFileContent(`outputs/content_briefs/${date}/briefs.json`);
}
