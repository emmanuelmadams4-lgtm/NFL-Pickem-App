"use client";

import { CartesianGrid, ComposedChart, LabelList, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { components } from "@nflpi/shared";
import { AXIS_LINE, AXIS_TICK, ChartTooltip, GRID_STROKE } from "@/components/charts/common";
import { pctOr } from "@/lib/fmt";

type Bucket = components["schemas"]["CalibrationBucket"];

const pctTick = (v: number) => `${Math.round(v * 100)}%`;

const usable = (buckets: Bucket[]) =>
  buckets.filter((b) => b.n > 0 && b.predicted !== null && b.observed !== null).map((b) => ({ ...b, predicted: b.predicted as number, observed: b.observed as number }));

type Row = ReturnType<typeof usable>[number] & { live: number | null; backfilled: number | null; source: string };

/** One calibration series. Solid dots for live picks, hollow (surface-filled, outlined) for backfilled ones. */
function seriesLine(rows: Row[], dataKey: "live" | "backfilled", name: string, color: string) {
  const hollow = dataKey === "backfilled";
  const dot = { r: 5, fill: hollow ? "var(--surface)" : color, stroke: hollow ? color : "var(--surface)", strokeWidth: 2 };
  return (
    <Line
      key={dataKey}
      type="linear"
      dataKey={dataKey}
      name={name}
      stroke={color}
      strokeWidth={hollow ? 1.5 : 2}
      strokeLinecap="round"
      connectNulls
      dot={dot}
      activeDot={{ ...dot, r: 6 }}
      isAnimationActive={false}
    >
      <LabelList
        dataKey="n"
        content={(p) => {
          const { x, y, index } = p as { x?: number; y?: number; index?: number };
          const row = index !== undefined ? rows[index] : undefined;
          if (x === undefined || y === undefined || !row || row[dataKey] === null) return null;
          const below = row.observed < row.predicted;
          return (
            <text x={x} y={below ? y + 20 : y - 12} textAnchor="middle" fill="var(--text-2)" fontSize={11}>
              n={row.n}
            </text>
          );
        }}
      />
    </Line>
  );
}

/**
 * Predicted vs observed per bucket. The dashed diagonal is perfect calibration.
 * `buckets` are solid points; `backfill` (when the caller has any to show apart) are hollow points (design.md § 13).
 */
export function CalibrationChart({
  buckets,
  backfill,
  color,
  name,
  backfillName,
  leader,
}: {
  buckets: Bucket[];
  backfill?: Bucket[];
  color: string;
  name: string;
  backfillName?: string;
  leader?: number | null;
}) {
  const live = usable(buckets);
  const apart = usable(backfill ?? []);
  if (live.length === 0 && apart.length === 0) return <p className="text-sm text-text-2">No graded predictions to calibrate yet.</p>;
  // One row per point, left to right, each carrying its value under its own series key so each Line joins only its points.
  const pts = [
    ...live.map((b) => ({ ...b, live: b.observed, backfilled: null as number | null, source: name })),
    ...apart.map((b) => ({ ...b, live: null as number | null, backfilled: b.observed, source: backfillName ?? "Backfilled" })),
  ].sort((a, b) => a.predicted - b.predicted);
  const lo = Math.max(0, Math.floor((Math.min(...pts.map((p) => Math.min(p.predicted, p.observed))) - 0.05) * 10) / 10);
  const small = pts.some((p) => p.n < 10);
  const games = (b: Bucket[]) => b.reduce((n, x) => n + x.n, 0);
  const counts = backfill !== undefined ? `; live: ${games(buckets)} games, backfilled: ${games(backfill)} games` : `; ${games(buckets)} games`;
  const ticks = Array.from({ length: Math.round((1 - lo) * 10) + 1 }, (_, i) => Math.round((lo + i / 10) * 10) / 10);

  return (
    <div>
      <div role="img" aria-label={`Calibration chart for ${name}: predicted versus observed win rate across ${pts.length} probability buckets${counts}`} className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={pts} margin={{ top: 24, right: 20, bottom: 24, left: 0 }}>
            <CartesianGrid stroke={GRID_STROKE} />
            <XAxis
              type="number"
              dataKey="predicted"
              domain={[lo, 1]}
              ticks={ticks}
              tickFormatter={pctTick}
              tick={AXIS_TICK}
              axisLine={AXIS_LINE}
              tickLine={false}
              label={{ value: "Predicted win probability", position: "insideBottom", offset: -14, fill: "var(--text-2)", fontSize: 11 }}
            />
            <YAxis type="number" domain={[lo, 1]} ticks={ticks} tickFormatter={pctTick} tick={AXIS_TICK} axisLine={false} tickLine={false} width={40} />
            <ReferenceLine segment={[{ x: lo, y: lo }, { x: 1, y: 1 }]} stroke="var(--muted)" strokeDasharray="5 4" strokeWidth={1.5} ifOverflow="hidden" />
            {leader != null && <ReferenceLine y={leader} stroke="var(--warn)" strokeDasharray="2 3" label={{ value: `League leader ${pctTick(leader)}`, position: "insideBottomRight", fill: "var(--text-2)", fontSize: 11 }} />}
            <Tooltip
              content={(p) => {
                const row = p.payload?.[0]?.payload as (typeof pts)[number] | undefined;
                return (
                  <div className="rounded-ctl border border-border bg-elevated px-3 py-2 text-xs shadow-[var(--shadow-pop)]">
                    {p.active && row ? (
                      <>
                        <p className="mb-1 font-medium text-text">
                          {row.bucket}
                          {backfill !== undefined && `, ${row.source.toLowerCase()}`}
                        </p>
                        <p className="text-text-2">Predicted {pctOr(row.predicted, 1)}</p>
                        <p className="text-text-2">Observed {pctOr(row.observed, 1)}</p>
                        <p className="text-text-2">{row.n} games</p>
                      </>
                    ) : null}
                  </div>
                );
              }}
            />
            {live.length > 0 && seriesLine(pts, "live", name, color)}
            {apart.length > 0 && seriesLine(pts, "backfilled", backfillName ?? "Backfilled", color)}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-text-2">
        {live.length > 0 ? (
          <span className="flex items-center gap-1.5">
            <span aria-hidden className="size-2.5 rounded-full" style={{ background: color }} />
            {name}: observed win rate (vertical) by predicted probability (horizontal)
          </span>
        ) : (
          <span>{name}: no graded games yet</span>
        )}
        {apart.length > 0 && (
          <span className="flex items-center gap-1.5">
            <span aria-hidden className="size-2.5 rounded-full" style={{ boxShadow: `inset 0 0 0 2px ${color}` }} />
            {backfillName ?? "Backfilled"}: computed after the fact
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="h-0 w-4 border-t-2 border-dashed border-muted" />
          Perfect calibration
        </span>
      </div>
      <p className="mt-2 text-[11px] text-subtle">
        On the dashed line, a stated probability matches how often those picks actually won.{small ? " Buckets with fewer than 10 games are noisy." : ""}
      </p>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-xs text-text-2 hover:text-text">Table view</summary>
        <table className="mt-2 w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-[11px] text-subtle">
              <th scope="col" className="py-1.5 font-medium">Bucket</th>
              {backfill !== undefined && <th scope="col" className="py-1.5 font-medium">Source</th>}
              <th scope="col" className="py-1.5 text-right font-medium">Games</th>
              <th scope="col" className="py-1.5 text-right font-medium">Predicted</th>
              <th scope="col" className="py-1.5 text-right font-medium">Observed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {[...buckets.map((b) => ({ b, source: name })), ...(backfill ?? []).map((b) => ({ b, source: backfillName ?? "Backfilled" }))].map(({ b, source }) => (
              <tr key={`${source}-${b.bucket}`}>
                <td className="py-1.5">{b.bucket}</td>
                {backfill !== undefined && <td className="py-1.5">{source}</td>}
                <td className="py-1.5 text-right">{b.n}</td>
                <td className="py-1.5 text-right">{pctOr(b.predicted, 1)}</td>
                <td className="py-1.5 text-right">{pctOr(b.observed, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
