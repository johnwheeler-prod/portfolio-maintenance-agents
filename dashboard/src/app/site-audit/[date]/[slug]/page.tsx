import { notFound } from "next/navigation";
import { Header } from "@/components/layout/header";
import { StatCard } from "@/components/cards/stat-card";
import { FindingCard } from "@/components/cards/finding-card";
import { Badge } from "@/components/ui/badge";
import { getSiteAuditPageReport, getSiteAuditPageGsc } from "@/lib/data";
import { formatDate, severityColor } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function PageReportPage({
  params,
}: {
  params: Promise<{ date: string; slug: string }>;
}) {
  const { date, slug } = await params;
  const [report, gsc] = await Promise.all([
    getSiteAuditPageReport(date, slug),
    getSiteAuditPageGsc(date, slug),
  ]);

  if (!report) notFound();

  return (
    <>
      <Header
        title={slug.replace(/_/g, "/")}
        description={`Audit from ${formatDate(date)} — ${report.page_url}`}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Overall Score" value={report.overall_score} />
        <StatCard label="Findings" value={report.findings.length} />
        <StatCard
          label="AEO Ready"
          value={report.aeo_analysis.featured_snippet_ready ? "Yes" : "No"}
        />
        <StatCard
          label="Impressions"
          value={gsc?.page_metrics.total_impressions ?? "—"}
          subValue={gsc ? `${gsc.page_metrics.total_clicks} clicks` : undefined}
        />
      </div>

      <div className="bg-surface-2 border border-surface-4 rounded-lg p-4 mb-6">
        <p className="text-sm text-neutral-300">{report.summary}</p>
      </div>

      {report.quick_wins.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Quick Wins
          </h2>
          <div className="flex flex-wrap gap-2">
            {report.quick_wins.map((win) => (
              <Badge key={win} className="bg-pine-500/15 text-pine-400">
                {win}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <h2 className="text-sm font-medium text-neutral-400 mb-3">Findings</h2>
      <div className="space-y-3 mb-6">
        {report.findings.map((finding) => (
          <FindingCard key={finding.id} finding={finding} />
        ))}
      </div>

      {report.aeo_analysis.paa_targets.length > 0 && (
        <>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            People Also Ask Targets
          </h2>
          <div className="space-y-2 mb-6">
            {report.aeo_analysis.paa_targets.map((paa) => (
              <div
                key={paa.question}
                className="bg-surface-2 border border-surface-4 rounded-lg p-4"
              >
                <div className="flex items-center gap-2 mb-1">
                  <Badge
                    className={
                      paa.currently_addressed
                        ? "bg-score-green/15 text-score-green"
                        : "bg-score-orange/15 text-score-orange"
                    }
                  >
                    {paa.currently_addressed ? "Addressed" : "Missing"}
                  </Badge>
                </div>
                <h4 className="text-sm font-medium text-neutral-200">
                  {paa.question}
                </h4>
                <p className="mt-1 text-xs text-neutral-400">
                  {paa.suggested_answer}
                </p>
              </div>
            ))}
          </div>
        </>
      )}

      {report.aeo_analysis.schema_recommendations.length > 0 && (
        <>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Schema Recommendations
          </h2>
          <div className="flex flex-wrap gap-2">
            {report.aeo_analysis.schema_recommendations.map((rec) => (
              <div
                key={rec.type}
                className="bg-surface-2 border border-surface-4 rounded-lg p-3"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-mono text-neutral-200">
                    {rec.type}
                  </span>
                  <Badge className={severityColor(rec.priority)}>
                    {rec.priority}
                  </Badge>
                </div>
                <p className="text-xs text-neutral-400">{rec.rationale}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
