"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Play, Loader2 } from "lucide-react";

interface PipelineFormProps {
  name: string;
  workflowFile: string;
  fields: { name: string; label: string; type: "text" | "checkbox" | "select"; options?: string[]; defaultValue?: string }[];
}

export function PipelineForm({ name, workflowFile, fields }: PipelineFormProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setResult(null);

    const formData = new FormData(e.currentTarget);
    const inputs: Record<string, string> = {};
    for (const field of fields) {
      if (field.type === "checkbox") {
        inputs[field.name] = formData.has(field.name) ? "true" : "false";
      } else {
        inputs[field.name] = (formData.get(field.name) as string) || "";
      }
    }

    try {
      const res = await fetch("/api/github/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflowFile, inputs }),
      });
      const data = await res.json();
      setResult(data.ok
        ? { ok: true, message: "Workflow triggered successfully" }
        : { ok: false, message: data.error || "Failed to trigger workflow" }
      );
    } catch {
      setResult({ ok: false, message: "Network error" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-surface-2 border border-surface-4 rounded-lg p-5">
      <h3 className="text-sm font-medium text-neutral-200 mb-4">{name}</h3>
      <form onSubmit={handleSubmit} className="space-y-3">
        {fields.map((field) => (
          <div key={field.name}>
            <label className="block text-xs text-neutral-500 mb-1">
              {field.label}
            </label>
            {field.type === "checkbox" ? (
              <input
                type="checkbox"
                name={field.name}
                className="rounded border-surface-4 bg-surface-3 text-pine-500 focus:ring-pine-500"
              />
            ) : field.type === "select" ? (
              <select
                name={field.name}
                defaultValue={field.defaultValue}
                className="w-full bg-surface-3 border border-surface-4 rounded px-3 py-1.5 text-sm text-neutral-200 focus:outline-none focus:border-pine-500"
              >
                {field.options?.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                name={field.name}
                defaultValue={field.defaultValue}
                className="w-full bg-surface-3 border border-surface-4 rounded px-3 py-1.5 text-sm text-neutral-200 focus:outline-none focus:border-pine-500"
              />
            )}
          </div>
        ))}
        <Button type="submit" disabled={loading}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {loading ? "Triggering..." : "Run"}
        </Button>
      </form>
      {result && (
        <p className={`mt-3 text-xs ${result.ok ? "text-score-green" : "text-score-red"}`}>
          {result.message}
        </p>
      )}
    </div>
  );
}
