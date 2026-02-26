import { Header } from "@/components/layout/header";
import { PipelineCard } from "@/components/cards/pipeline-card";
import {
  PIPELINES,
  getSiteAuditDates,
  getSiteAuditSummary,
  getSiteAuditTrend,
  getPortfolioState,
  getPortfolioTrend,
  getSeoAuditDates,
  getSeoAuditReport,
  getSeoAuditTrend,
} from "@/lib/data";
import type { TrendPoint } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const [siteAuditDates, seoAuditDates, portfolioState] = await Promise.all([
    getSiteAuditDates(),
    getSeoAuditDates(),
    getPortfolioState(),
  ]);

  const latestSiteAudit = siteAuditDates[0]
    ? await getSiteAuditSummary(siteAuditDates[0])
    : null;
  const latestSeoAudit = seoAuditDates[0]
    ? await getSeoAuditReport(seoAuditDates[0])
    : null;

  const [siteAuditTrend, seoAuditTrend, portfolioTrend] = await Promise.all([
    getSiteAuditTrend(),
    getSeoAuditTrend(),
    getPortfolioTrend(),
  ]);

  const pipelineData: Record<string, { score: number | null; date: string | null; trend: TrendPoint[] }> = {
    "site-audit": {
      score: latestSiteAudit?.mean_score ?? null,
      date: siteAuditDates[0] ?? null,
      trend: siteAuditTrend,
    },
    "seo-audit": {
      score: latestSeoAudit?.overall_score ?? null,
      date: seoAuditDates[0] ?? null,
      trend: seoAuditTrend,
    },
    "portfolio-audit": {
      score: portfolioState?.overall_freshness_score ?? null,
      date: portfolioState?.last_audit_date ?? null,
      trend: portfolioTrend,
    },
    "content-plan": {
      score: null,
      date: null,
      trend: [],
    },
  };

  return (
    <>
      <Header
        title="Pipeline Overview"
        description="Latest results across all agent pipelines"
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {PIPELINES.map((pipeline) => {
          const data = pipelineData[pipeline.id];
          return (
            <PipelineCard
              key={pipeline.id}
              pipeline={pipeline}
              latestScore={data?.score ?? null}
              latestDate={data?.date ?? null}
              trend={data?.trend ?? []}
            />
          );
        })}
      </div>
    </>
  );
}
