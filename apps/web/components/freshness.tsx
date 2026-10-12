"use client";

import { useState } from "react";
import { ago, type Freshness } from "@nflpi/shared";
import { useFreshness } from "@/lib/queries";
import { cx } from "@/components/ui";

export function staleList(data: Freshness[] | undefined): Freshness[] {
  return (data ?? []).filter((d) => d.stale);
}

/** Datasets the model reads. Lines arrive with schedules. Weather and teams are context only. */
const MODEL_INPUTS = new Set(["schedules", "injuries"]);

export function feedsModel(d: Freshness): boolean {
  return MODEL_INPUTS.has(d.dataset);
}

/** "weather (never updated)", "injuries (26h ago)" */
export function describeStale(d: Freshness): string {
  return d.last_success ? `${d.dataset} (${ago(d.last_success)})` : `${d.dataset} (never updated)`;
}

export function FreshnessTable({ data }: { data: Freshness[] }) {
  return (
    <ul className="divide-y divide-border">
      {data.map((d) => (
        <li key={d.dataset} className="flex items-start justify-between gap-4 py-2 first:pt-0 last:pb-0">
          <div className="min-w-0">
            <p className="text-sm font-medium capitalize text-text">{d.dataset}</p>
            {d.last_error && <p className="mt-0.5 text-xs break-words text-bad">Last error: {d.last_error}</p>}
          </div>
          <div className="shrink-0 text-right">
            <p className={cx("text-sm", d.stale ? "font-medium text-warn" : "text-text-2")}>{d.last_success ? ago(d.last_success) : "never"}</p>
            {d.stale && <p className="text-[11px] text-warn">stale</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Top-bar freshness indicator. Amber only when a model input is stale; hover or focus lists every dataset. */
export function FreshnessIndicator() {
  const q = useFreshness();
  const [hover, setHover] = useState(false);
  const [pinned, setPinned] = useState(false);
  const open = hover || pinned;

  const stale = staleList(q.data);
  const state = q.isPending ? "pending" : q.isError ? "error" : stale.some(feedsModel) ? "stale" : stale.length > 0 ? "context" : "fresh";
  const label =
    state === "pending"
      ? "Checking data"
      : state === "error"
        ? "Freshness unknown"
        : state === "stale" || state === "context"
          ? `Stale: ${stale.map((s) => s.dataset).join(", ")}`
          : "Data fresh";
  const dot = { pending: "bg-muted", error: "bg-muted", stale: "bg-warn", context: "bg-muted", fresh: "bg-good" }[state];
  const text = state === "stale" ? "text-warn" : "text-text-2";

  return (
    <div
      className="relative"
      onPointerEnter={(e) => e.pointerType === "mouse" && setHover(true)}
      onPointerLeave={(e) => e.pointerType === "mouse" && setHover(false)}
      onFocus={() => setHover(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) {
          setHover(false);
          setPinned(false);
        }
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setHover(false);
          setPinned(false);
        }
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls="freshness-popover"
        onClick={() => setPinned((p) => !p)}
        className={cx("flex h-10 max-w-[9rem] items-center gap-2 rounded-ctl border border-border bg-elevated px-2.5 text-xs hover:border-border-strong lg:h-8 lg:max-w-56", text)}
      >
        <span aria-hidden className={cx("size-2 shrink-0 rounded-full", dot)} />
        <span className="truncate">{label}</span>
      </button>
      <div
        id="freshness-popover"
        role="region"
        aria-label="Data freshness"
        hidden={!open}
        className="z-40 rounded-card border border-border bg-elevated p-4 shadow-[var(--shadow-pop)] max-lg:fixed max-lg:inset-x-4 max-lg:top-[calc(var(--header-h)+8px)] lg:absolute lg:top-full lg:right-0 lg:mt-2 lg:w-80"
      >
        <p className="mb-3 text-xs font-medium text-text-2">Data sources</p>
        {q.data ? <FreshnessTable data={q.data} /> : <p className="text-sm text-text-2">{q.isError ? "Could not load freshness." : "Loading."}</p>}
      </div>
    </div>
  );
}
