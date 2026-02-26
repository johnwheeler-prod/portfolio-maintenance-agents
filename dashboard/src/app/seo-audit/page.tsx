import Link from "next/link";
import { Header } from "@/components/layout/header";
import { ScoreTrend } from "@/components/charts/score-trend";
import { getSeoAuditDates, getSeoAuditReport, getSeoAuditTrend } from "@/lib/data";
import { Badge } from "@/components/ui/badge";
import { scoreBg, formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function SeoAuditPage() {
  const [dates, trend] = await Promise.all([
    getSeoAuditDates(),
    getSeoAuditTrend(),
  ]);

  const reports = await Promise.all(
    dates.map(async (date) => {
      const report = await getSeoAuditReport(date);
      return { date, report };
    })
  );

  return (
    <>
      <Header
        title="SEO Audit"
        description="Single-page SEO/AEO deep analysis"
      />

      {trend.length > 1 && (
        <div className="bg-surface-2 border border-surface-4 rounded-lg p-5 mb-6">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Score Trend
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
              <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
                Page
              </th>
              <th className="text-right px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
                Score
              </th>
            </tr>
          </thead>
          <tbody>
            {reports.map(({ date, report }) => (
              <tr
                key={date}
                className="border-b border-surface-4 last:border-0 hover:bg-surface-3 transition-colors"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/seo-audit/${date}`}
                    className="text-pine-400 hover:text-pine-400/80 font-mono"
                  >
                    {formatDate(date)}
                  </Link>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-neutral-400">
                  {report?.page_url ?? "—"}
                </td>
                <td className="px-4 py-3 text-right">
                  {report ? (
                    <Badge className={scoreBg(report.overall_score)}>
                      {report.overall_score}
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
            No SEO audit runs found. Trigger one from the Run page.
          </div>
        )}
      </div>
    </>
  );
}
