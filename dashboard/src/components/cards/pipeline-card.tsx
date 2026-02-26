import Link from "next/link";
import type { PipelineInfo, TrendPoint } from "@/lib/types";
import { ScoreTrendMini } from "@/components/charts/score-trend";
import { scoreColor } from "@/lib/utils";

export function PipelineCard({
  pipeline,
  latestScore,
  latestDate,
  trend,
}: {
  pipeline: PipelineInfo;
  latestScore: number | null;
  latestDate: string | null;
  trend: TrendPoint[];
}) {
  return (
    <Link
      href={`/${pipeline.id}`}
      className="block bg-surface-2 border border-surface-4 rounded-lg p-5 hover:border-pine-500/50 transition-colors"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-medium text-neutral-200">
            {pipeline.name}
          </h3>
          <p className="mt-0.5 text-xs text-neutral-500">
            {pipeline.description}
          </p>
        </div>
        {latestScore !== null && (
          <span className={`text-2xl font-mono font-bold ${scoreColor(latestScore)}`}>
            {latestScore}
          </span>
        )}
      </div>
      {trend.length > 1 && (
        <div className="mt-4 h-12">
          <ScoreTrendMini data={trend} />
        </div>
      )}
      {latestDate && (
        <p className="mt-3 text-xs text-neutral-600 font-mono">{latestDate}</p>
      )}
    </Link>
  );
}
