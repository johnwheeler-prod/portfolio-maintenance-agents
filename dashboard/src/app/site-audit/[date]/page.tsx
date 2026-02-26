import { notFound } from "next/navigation";
import { Header } from "@/components/layout/header";
import { StatCard } from "@/components/cards/stat-card";
import { DistributionBar } from "@/components/charts/distribution-bar";
import { PagesTable } from "@/components/tables/pages-table";
import { FindingsTable } from "@/components/tables/findings-table";
import { getSiteAuditSummary } from "@/lib/data";
import { formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function SiteAuditDatePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const summary = await getSiteAuditSummary(date);
  if (!summary) notFound();

  return (
    <>
      <Header
        title={`Site Audit — ${formatDate(date)}`}
        description={`Audited ${summary.audited_pages} of ${summary.filtered_urls} filtered pages`}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Mean Score" value={summary.mean_score} />
        <StatCard label="Pages Audited" value={summary.audited_pages} />
        <StatCard label="Failed" value={summary.failed_pages} />
        <StatCard
          label="Sitemap URLs"
          value={summary.total_sitemap_urls}
          subValue={`${summary.filtered_urls} after filters`}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-surface-2 border border-surface-4 rounded-lg p-5">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Score Distribution
          </h2>
          <DistributionBar distribution={summary.score_distribution} />
        </div>
        <div>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Top Cross-Site Findings
          </h2>
          <FindingsTable findings={summary.top_cross_site_findings} />
        </div>
      </div>

      <h2 className="text-sm font-medium text-neutral-400 mb-3">
        Priority Pages
      </h2>
      <PagesTable pages={summary.priority_pages} dateParam={date} />
    </>
  );
}
