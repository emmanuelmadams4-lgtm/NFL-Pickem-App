"use client";

import type { TooltipContentProps } from "recharts";

export const AXIS_TICK = { fill: "var(--text-2)", fontSize: 11 } as const;
export const AXIS_LINE = { stroke: "var(--border)" } as const;
export const GRID_STROKE = "var(--border)";

/** Plain-HTML tooltip so it picks up the theme tokens in both color schemes. */
export function ChartTooltip({
  active,
  payload,
  label,
  formatLabel,
  formatValue,
}: TooltipContentProps & {
  formatLabel?: (label: unknown) => string;
  formatValue?: (value: number, name: string) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const rows = payload.filter((p) => p.value !== null && p.value !== undefined);
  return (
    <div className="rounded-ctl border border-border bg-elevated px-3 py-2 text-xs shadow-[var(--shadow-pop)]">
      <p className="mb-1 font-medium text-text">{formatLabel ? formatLabel(label) : String(label)}</p>
      <ul className="space-y-0.5">
        {rows.map((p) => {
          const fill = p.color ?? (p.payload as { fill?: string })?.fill;
          const hollow = (!fill || fill === "none") && p.stroke; // outline-only series: backfilled (design.md § 13)
          return (
            <li key={String(p.dataKey ?? p.name)} className="flex items-center gap-2 text-text-2">
              <span aria-hidden className="size-2 rounded-full" style={hollow ? { boxShadow: `inset 0 0 0 1.5px ${p.stroke}` } : { background: fill }} />
              <span>{p.name}</span>
              <span className="ml-auto pl-4 font-medium text-text">{formatValue ? formatValue(Number(p.value), String(p.name)) : String(p.value)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Legend as HTML: color swatch beside text, text stays in the text ink. */
export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-2" aria-label="Chart legend">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span aria-hidden className="h-0.5 w-4 rounded-full" style={{ background: i.color }} />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

/** `hollow` draws an outline in the color with no fill: backfilled figures (design.md § 13). */
export function LegendSwatch({ items }: { items: { label: string; color: string; hollow?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-2" aria-label="Chart legend">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="size-2.5 rounded-[3px]"
            style={i.hollow ? { boxShadow: `inset 0 0 0 1.5px ${i.color}` } : { background: i.color }}
          />
          {i.label}
        </li>
      ))}
    </ul>
  );
}
