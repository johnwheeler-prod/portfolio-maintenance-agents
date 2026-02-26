import { notFound } from "next/navigation";
import { Header } from "@/components/layout/header";
import { StatCard } from "@/components/cards/stat-card";
import { Badge } from "@/components/ui/badge";
import { getPortfolioReport } from "@/lib/data";
import { formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function PortfolioAuditDatePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const report = await getPortfolioReport(date);
  if (!report) notFound();

  return (
    <>
      <Header
        title={`Portfolio Audit — ${formatDate(date)}`}
        description="Portfolio freshness report"
      />

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
        <StatCard
          label="Freshness Score"
          value={report.overall_freshness_score}
        />
        <StatCard label="Findings" value={report.finding_count} />
        <StatCard label="Quick Wins" value={report.quick_wins.length} />
      </div>

      {report.finding_titles.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Findings
          </h2>
          <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
            {report.finding_titles.map((title) => (
              <div
                key={title}
                className="px-4 py-3 border-b border-surface-4 last:border-0 text-sm text-neutral-300"
              >
                {title}
              </div>
            ))}
          </div>
        </div>
      )}

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
    </>
  );
}
