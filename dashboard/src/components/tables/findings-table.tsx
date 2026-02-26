import type { CrossSiteFinding } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { severityColor } from "@/lib/utils";

export function FindingsTable({ findings }: { findings: CrossSiteFinding[] }) {
  return (
    <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-surface-4">
            <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Finding
            </th>
            <th className="text-right px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Pages
            </th>
            <th className="text-right px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Severity
            </th>
          </tr>
        </thead>
        <tbody>
          {findings.map((finding) => {
            const topSeverity = finding.pages[0]?.severity ?? "low";
            return (
              <tr
                key={finding.title}
                className="border-b border-surface-4 last:border-0"
              >
                <td className="px-4 py-3 text-neutral-300">{finding.title}</td>
                <td className="px-4 py-3 text-right font-mono text-neutral-400">
                  {finding.count}
                </td>
                <td className="px-4 py-3 text-right">
                  <Badge className={severityColor(topSeverity)}>
                    {topSeverity}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
