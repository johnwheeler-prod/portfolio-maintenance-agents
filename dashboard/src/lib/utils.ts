import type { Severity } from "./types";

export function scoreColor(score: number): string {
  if (score >= 80) return "text-score-green";
  if (score >= 60) return "text-score-yellow";
  if (score >= 40) return "text-score-orange";
  return "text-score-red";
}

export function scoreBg(score: number): string {
  if (score >= 80) return "bg-score-green/15 text-score-green";
  if (score >= 60) return "bg-score-yellow/15 text-score-yellow";
  if (score >= 40) return "bg-score-orange/15 text-score-orange";
  return "bg-score-red/15 text-score-red";
}

export function severityColor(severity: Severity): string {
  switch (severity) {
    case "high":
      return "bg-score-red/15 text-score-red";
    case "medium":
      return "bg-score-orange/15 text-score-orange";
    case "low":
      return "bg-score-yellow/15 text-score-yellow";
  }
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function categoryLabel(cat: string): string {
  return cat
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function slugFromUrl(url: string): string {
  try {
    const path = new URL(url).pathname.replace(/^\/|\/$/g, "");
    return path.replace(/\//g, "_") || "index";
  } catch {
    return url;
  }
}
