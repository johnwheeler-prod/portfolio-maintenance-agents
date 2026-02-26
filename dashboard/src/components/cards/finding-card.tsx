import type { Finding } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { severityColor, categoryLabel } from "@/lib/utils";

export function FindingCard({ finding }: { finding: Finding }) {
  return (
    <div className="bg-surface-2 border border-surface-4 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Badge className={severityColor(finding.severity)}>
              {finding.severity}
            </Badge>
            <Badge className="bg-surface-3 text-neutral-400">
              {categoryLabel(finding.category)}
            </Badge>
            <Badge className="bg-surface-3 text-neutral-500">
              effort: {finding.effort}
            </Badge>
          </div>
          <h4 className="text-sm font-medium text-neutral-200">
            {finding.title}
          </h4>
          <p className="mt-1 text-xs text-neutral-400">{finding.description}</p>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div className="bg-surface-3 rounded p-2.5">
          <p className="text-[10px] uppercase text-neutral-500 tracking-wider mb-1">
            Current
          </p>
          <p className="text-xs text-neutral-400">{finding.current_state}</p>
        </div>
        <div className="bg-surface-3 rounded p-2.5">
          <p className="text-[10px] uppercase text-pine-500 tracking-wider mb-1">
            Suggested Fix
          </p>
          <p className="text-xs text-neutral-300">{finding.suggested_fix}</p>
        </div>
      </div>
    </div>
  );
}
