"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_LINE, AXIS_TICK, ChartTooltip, GRID_STROKE } from "@/components/charts/common";

export interface TimePoint {
  t: number;
  v: number;
}

const fmtTime = (t: number) => new Date(t).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
const fmtAxis = (t: number) => new Date(t).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric" });

/** One-series probability over time. Shown only when there are at least two points. */
export function TimeLine({
  data,
  name,
  color,
  label,
  height = 180,
}: {
  data: TimePoint[];
  name: string;
  color: string;
  label: string;
  height?: number;
}) {
  const values = data.map((d) => d.v);
  const lo = Math.max(0, Math.floor((Math.min(...values) - 0.05) * 20) / 20);
  const hi = Math.min(1, Math.ceil((Math.max(...values) + 0.05) * 20) / 20);
  return (
    <div role="img" aria-label={label} style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid stroke={GRID_STROKE} vertical={false} />
          <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={fmtAxis} tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} minTickGap={48} />
          <YAxis domain={[lo, hi]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={AXIS_TICK} axisLine={false} tickLine={false} width={48} />
          <Tooltip content={(p) => <ChartTooltip {...p} formatLabel={(l) => fmtTime(Number(l))} formatValue={(v) => `${(v * 100).toFixed(1)}%`} />} />
          <Line
            type="stepAfter"
            dataKey="v"
            name={name}
            stroke={color}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            dot={{ r: 4, fill: color, stroke: "var(--surface)", strokeWidth: 2 }}
            activeDot={{ r: 5, fill: color, stroke: "var(--surface)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
