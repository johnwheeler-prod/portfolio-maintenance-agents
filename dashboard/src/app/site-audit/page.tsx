import Link from "next/link";
import { Header } from "@/components/layout/header";
import { ScoreTrend } from "@/components/charts/score-trend";
import { getSiteAuditDates, getSiteAuditSummary, getSiteAuditTrend } from "@/lib/data";
import { Badge } from "@/components/ui/badge";
import { scoreBg, formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function SiteAuditPage() {
  const [dates, trend] = await Promise.all([
    getSiteAuditDates(),
    getSiteAuditTrend(),
  ]);

  const summaries = await Promise.all(
    dates.map(async (date) => {
      const summary = await getSiteAuditSummary(date);
      return { date, summary };
    })
  );

  return (
    <>
      <Header
        title="Site Audit"
        description="Sitemap-based multi-page SEO/AEO audits"
      />

      {trend.length > 1 && (
        <div className="bg-surface-2 border border-surface-4 rounded-lg p-5 mb-6">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Mean Score Trend
          </h2>
          <ScoreTrend data={trend} />
        </div>
      )}

      <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-4">
              <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
                Date
              </th>
              <th className="text-right px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
                Pages
              </th>
              <th className="text-right px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
                Mean Score
              </th>
            </tr>
          </thead>
          <tbody>
            {summaries.map(({ date, summary }) => (
              <tr
                key={date}
                className="border-b border-surface-4 last:border-0 hover:bg-surface-3 transition-colors"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/site-audit/${date}`}
                    className="text-pine-400 hover:text-pine-400/80 font-mono"
                  >
                    {formatDate(date)}
                  </Link>
                </td>
                <td className="px-4 py-3 text-right font-mono text-neutral-400">
                  {summary?.audited_pages ?? "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  {summary ? (
                    <Badge className={scoreBg(summary.mean_score)}>
                      {summary.mean_score}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {dates.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-neutral-500">
            No site audit runs found. Trigger one from the Run page.
          </div>
        )}
      </div>
    </>
  );
}
