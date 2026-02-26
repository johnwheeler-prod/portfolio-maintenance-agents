"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import type { WorkflowRun } from "@/lib/github";

function statusColor(status: string | null, conclusion: string | null): string {
  if (status === "in_progress" || status === "queued") return "bg-score-yellow/15 text-score-yellow";
  if (conclusion === "success") return "bg-score-green/15 text-score-green";
  if (conclusion === "failure") return "bg-score-red/15 text-score-red";
  return "bg-surface-3 text-neutral-400";
}

export function RunStatus({ workflowFile }: { workflowFile: string }) {
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    fetch(`/api/github/runs?workflow=${encodeURIComponent(workflowFile)}`)
      .then((res) => {
        if (!res.ok) throw new Error("Request failed");
        return res.json();
      })
      .then((data) => {
        if (data.error) throw new Error(data.error);
        setRuns(data.runs ?? []);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, [workflowFile]);

  return (
    <div className="mt-4">
      <h4 className="text-xs text-neutral-500 mb-2">Recent Runs</h4>
      {loading ? (
        <div className="flex items-center gap-1.5 text-xs text-neutral-500">
          <Loader2 size={12} className="animate-spin" />
          Loading...
        </div>
      ) : error ? (
        <p className="text-xs text-score-red">Failed to load runs</p>
      ) : runs.length === 0 ? (
        <p className="text-xs text-neutral-500">No runs found</p>
      ) : (
        <div className="space-y-1.5">
          {runs.slice(0, 5).map((run) => (
            <div key={run.id} className="flex items-center justify-between text-xs">
              <a
                href={run.html_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-neutral-400 hover:text-pine-400 font-mono"
              >
                {new Date(run.created_at).toLocaleDateString()}
              </a>
              <Badge className={statusColor(run.status, run.conclusion)}>
                {run.conclusion ?? run.status ?? "unknown"}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
