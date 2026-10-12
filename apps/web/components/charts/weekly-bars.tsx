"use client";

import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { WeekPerformance } from "@nflpi/shared";
import { AXIS_LINE, AXIS_TICK, ChartTooltip, GRID_STROKE, LegendSwatch } from "@/components/charts/common";

const rate = (c: number, t: number) => (t > 0 ? c / t : null);

export const SERIES = {
  me: { label: "Me", color: "var(--series-me)" },
  model: { label: "Model", color: "var(--series-model)" },
  modelBackfill: { label: "Model, backfilled", color: "var(--series-model)" },
  market: { label: "Market", color: "var(--series-market)" },
} as const;

/**
 * Grouped weekly accuracy. Bars are thin with a 4px rounded top and a 2px gap between neighbors.
 * The Model bar is live picks only; backfilled picks are a separate hollow bar (design.md § 13).
 */
export function WeeklyBars({ weeks, leader }: { weeks: WeekPerformance[]; leader?: number | null }) {
  const count = (c: number, t: number) => `${c}/${t}`;
  const data = weeks.map((w) => ({
    week: `W${w.week}`,
    me: rate(w.my_correct, w.my_total),
    model: rate(w.model_live_correct, w.model_live_total),
    modelBackfill: rate(w.model_backfill_correct, w.model_backfill_total),
    market: rate(w.market_correct, w.market_total),
    counts: {
      [SERIES.me.label]: count(w.my_correct, w.my_total),
      [SERIES.model.label]: count(w.model_live_correct, w.model_live_total),
      [SERIES.modelBackfill.label]: count(w.model_backfill_correct, w.model_backfill_total),
      [SERIES.market.label]: count(w.market_correct, w.market_total),
    } as Record<string, string>,
  }));
  const keys = Object.keys(SERIES) as (keyof typeof SERIES)[];
  // The chart's text alternative is built from the same `data` the bars render (en dash = none graded), so they cannot disagree.
  const whole = (v: number | null) => (v === null ? "–" : `${Math.round(v * 100)}%`);
  const described = data.map((d) => `${d.week}: me ${whole(d.me)}, model live ${whole(d.model)}, model backfilled ${whole(d.modelBackfill)}, market ${whole(d.market)}`).join("; ");

  return (
    <div>
      <div role="img" aria-label={`Grouped bar chart of weekly accuracy for you, the live model, the backfilled model and the market. ${described}`} className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 12, right: 8, bottom: 0, left: 0 }} barGap={2} barCategoryGap="22%">
            <CartesianGrid stroke={GRID_STROKE} vertical={false} />
            <XAxis dataKey="week" tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} />
            <YAxis domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={AXIS_TICK} axisLine={false} tickLine={false} width={40} />
            {leader != null && (
              <ReferenceLine y={leader} stroke="var(--warn)" strokeDasharray="4 3" label={{ value: `League leader ${Math.round(leader * 100)}%`, position: "insideTopRight", fill: "var(--text-2)", fontSize: 11 }} />
            )}
            <Tooltip
              cursor={{ fill: "var(--elevated)", opacity: 0.6 }}
              content={(p) => {
                const counts = (p.payload?.[0]?.payload as (typeof data)[number] | undefined)?.counts;
                return (
                  <ChartTooltip
                    {...p}
                    formatLabel={(l) => `Week ${String(l).slice(1)}`}
                    formatValue={(v, name) => `${(v * 100).toFixed(0)}%${counts ? ` (${counts[name]})` : ""}`}
                  />
                );
              }}
            />
            {keys.map((k) => (
              <Bar
                key={k}
                dataKey={k}
                name={SERIES[k].label}
                fill={k === "modelBackfill" ? "none" : SERIES[k].color}
                stroke={k === "modelBackfill" ? SERIES[k].color : undefined}
                strokeWidth={k === "modelBackfill" ? 1.5 : undefined}
                maxBarSize={14}
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2">
        <LegendSwatch items={keys.map((k) => ({ label: SERIES[k].label, color: SERIES[k].color, hollow: k === "modelBackfill" }))} />
      </div>
    </div>
  );
}
