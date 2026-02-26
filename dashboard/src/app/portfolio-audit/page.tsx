import Link from "next/link";
import { Header } from "@/components/layout/header";
import { ScoreTrend } from "@/components/charts/score-trend";
import { StatCard } from "@/components/cards/stat-card";
import {
  getPortfolioAuditDates,
  getPortfolioState,
  getPortfolioTrend,
} from "@/lib/data";
import { Badge } from "@/components/ui/badge";
import { scoreBg, formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function PortfolioAuditPage() {
  const [dates, trend, currentState] = await Promise.all([
    getPortfolioAuditDates(),
    getPortfolioTrend(),
    getPortfolioState(),
  ]);

  return (
    <>
      <Header
        title="Portfolio Audit"
        description="Portfolio freshness checks with persistent memory"
      />

      {currentState && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Freshness Score"
            value={currentState.overall_freshness_score}
          />
          <StatCard label="Findings" value={currentState.finding_count} />
          <StatCard label="Quick Wins" value={currentState.quick_wins.length} />
          <StatCard
            label="Last Audit"
            value={formatDate(currentState.last_audit_date)}
          />
        </div>
      )}

      {currentState && currentState.quick_wins.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Current Quick Wins
          </h2>
          <div className="flex flex-wrap gap-2">
            {currentState.quick_wins.map((win) => (
              <Badge key={win} className="bg-pine-500/15 text-pine-400">
                {win}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {currentState && currentState.finding_titles.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Current Findings
          </h2>
          <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
            {currentState.finding_titles.map((title) => (
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

      {trend.length > 1 && (
        <div className="bg-surface-2 border border-surface-4 rounded-lg p-5 mb-6">
          <h2 className="text-sm font-medium text-neutral-400 mb-3">
            Freshness Score Trend
          </h2>
          <ScoreTrend data={trend} />
        </div>
      )}

      {dates.length > 0 && (
        <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-4">
                <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
                  Date
                </th>
              </tr>
            </thead>
            <tbody>
              {dates.map((date) => (
                <tr
                  key={date}
                  className="border-b border-surface-4 last:border-0 hover:bg-surface-3 transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/portfolio-audit/${date}`}
                      className="text-pine-400 hover:text-pine-400/80 font-mono"
                    >
                      {formatDate(date)}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
