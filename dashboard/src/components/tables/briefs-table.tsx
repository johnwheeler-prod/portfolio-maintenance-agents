import type { ContentBrief } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { severityColor } from "@/lib/utils";

export function BriefsTable({ briefs }: { briefs: ContentBrief[] }) {
  return (
    <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-surface-4">
            <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Title
            </th>
            <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Keyword
            </th>
            <th className="text-left px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Intent
            </th>
            <th className="text-right px-4 py-3 text-xs text-neutral-500 font-medium uppercase tracking-wider">
              Priority
            </th>
          </tr>
        </thead>
        <tbody>
          {briefs.map((brief) => (
            <tr
              key={brief.title}
              className="border-b border-surface-4 last:border-0"
            >
              <td className="px-4 py-3 text-neutral-200">{brief.title}</td>
              <td className="px-4 py-3 font-mono text-xs text-neutral-400">
                {brief.target_keyword}
              </td>
              <td className="px-4 py-3 text-xs text-neutral-400">
                {brief.search_intent}
              </td>
              <td className="px-4 py-3 text-right">
                <Badge className={severityColor(brief.priority)}>
                  {brief.priority}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
