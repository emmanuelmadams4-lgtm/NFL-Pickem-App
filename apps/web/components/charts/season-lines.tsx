"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS_LINE, AXIS_TICK, ChartTooltip, GRID_STROKE, Legend } from "@/components/charts/common";

export interface SeasonRow {
  season: number;
  n: number;
  [model: string]: number;
}

export const MODEL_STYLE: Record<string, { label: string; color: string }> = {
  home: { label: "Always home", color: "var(--series-home)" },
  elo: { label: "Elo only", color: "var(--series-elo)" },
  logistic: { label: "Stats model", color: "var(--series-stats)" },
  market: { label: "Betting market", color: "var(--series-market)" },
  blend: { label: "Blend", color: "var(--series-model)" },
};
const ORDER = ["home", "elo", "logistic", "market", "blend"];

export function SeasonLines({ rows }: { rows: SeasonRow[] }) {
  const keys = ORDER.filter((k) => rows.some((r) => typeof r[k] === "number"));
  const vals = rows.flatMap((r) => keys.map((k) => r[k]).filter((v): v is number => typeof v === "number"));
  const lo = Math.floor((Math.min(...vals) - 0.02) * 20) / 20;
  const hi = Math.ceil((Math.max(...vals) + 0.02) * 20) / 20;
  const ticks = Array.from({ length: Math.round((hi - lo) / 0.05) + 1 }, (_, i) => Math.round((lo + i * 0.05) * 100) / 100);

  return (
    <div>
      <div role="img" aria-label="Line chart of accuracy by season for each model" className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -4 }}>
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey="season" type="number" domain={["dataMin", "dataMax"]} tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} allowDecimals={false} tickCount={Math.min(rows.length, 8)} />
            <YAxis domain={[lo, hi]} ticks={ticks} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={AXIS_TICK} axisLine={false} tickLine={false} width={44} />
            <Tooltip content={(p) => <ChartTooltip {...p} formatLabel={(l) => `${l} season`} formatValue={(v) => `${(v * 100).toFixed(1)}%`} />} />
            {keys.map((k) => (
              <Line
                key={k}
                type="linear"
                dataKey={k}
                name={MODEL_STYLE[k].label}
                stroke={MODEL_STYLE[k].color}
                strokeWidth={k === "home" ? 1.5 : 2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={false}
                activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2">
        <Legend items={keys.map((k) => ({ label: MODEL_STYLE[k].label, color: MODEL_STYLE[k].color }))} />
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-text-2 hover:text-text">Table view</summary>
        <table className="mt-2 w-full text-sm">
          <thead>
            <tr className="border-b border-border text-[11px] text-subtle">
              <th scope="col" className="py-1.5 text-left font-medium">Season</th>
              {keys.map((k) => (
                <th key={k} scope="col" className="py-1.5 text-right font-medium">
                  {MODEL_STYLE[k].label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr key={r.season}>
                <th scope="row" className="py-1.5 text-left font-medium">{r.season}</th>
                {keys.map((k) => (
                  <td key={k} className="py-1.5 text-right">
                    {typeof r[k] === "number" ? `${(r[k] * 100).toFixed(1)}%` : "–"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
