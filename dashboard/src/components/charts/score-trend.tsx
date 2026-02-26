"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { TrendPoint } from "@/lib/types";

export function ScoreTrend({ data }: { data: TrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "#737373" }}
          axisLine={{ stroke: "#232323" }}
          tickLine={false}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "#737373" }}
          axisLine={{ stroke: "#232323" }}
          tickLine={false}
          width={30}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "#141414",
            border: "1px solid #232323",
            borderRadius: 6,
            fontSize: 12,
          }}
          labelStyle={{ color: "#737373" }}
          itemStyle={{ color: "#4A9E5F" }}
        />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#4A9E5F"
          strokeWidth={2}
          dot={{ fill: "#2D6B3F", r: 3 }}
          activeDot={{ fill: "#4A9E5F", r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ScoreTrendMini({ data }: { data: TrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="score"
          stroke="#4A9E5F"
          strokeWidth={1.5}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
