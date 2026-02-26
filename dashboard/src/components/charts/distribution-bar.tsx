"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { ScoreDistribution } from "@/lib/types";

const COLORS: Record<string, string> = {
  excellent: "#4ADE80",
  good: "#FACC15",
  needs_work: "#FB923C",
  poor: "#F87171",
};

export function DistributionBar({
  distribution,
}: {
  distribution: ScoreDistribution;
}) {
  const data = [
    { name: "Excellent", value: distribution.excellent, key: "excellent" },
    { name: "Good", value: distribution.good, key: "good" },
    { name: "Needs Work", value: distribution.needs_work, key: "needs_work" },
    { name: "Poor", value: distribution.poor, key: "poor" },
  ];

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
        <XAxis
          dataKey="name"
          tick={{ fontSize: 11, fill: "#737373" }}
          axisLine={{ stroke: "#232323" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "#737373" }}
          axisLine={{ stroke: "#232323" }}
          tickLine={false}
          width={24}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#141414",
            border: "1px solid #232323",
            borderRadius: 6,
            fontSize: 12,
          }}
          labelStyle={{ color: "#737373" }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.key} fill={COLORS[entry.key]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
