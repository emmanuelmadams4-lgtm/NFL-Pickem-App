"use client";

import { UNCERTAINTY, type Prediction } from "@nflpi/shared";
import { Chip, Tip, cx } from "@/components/ui";

/** `fromRight`: the picked team is the home team, which sits on the right of the VS layout, so the fill grows from the right. */
export function ProbBar({ value, className, label, fromRight }: { value: number; className?: string; label?: string; fromRight?: boolean }) {
  const w = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(w)}
      aria-label={label ?? "Win probability"}
      className={cx("relative h-1 w-full rounded-full bg-border", className)}
    >
      {/* The model's probability is not "me", so the fill is ink, never accent blue (design.md § 5). */}
      <div className={cx("absolute inset-y-0 rounded-full bg-text-2", fromRight ? "right-0" : "left-0")} style={{ width: `${w}%` }} />
      {/* 50% reference tick */}
      <div aria-hidden className="absolute -top-0.5 -bottom-0.5 left-1/2 w-px bg-text" />
    </div>
  );
}

export function BackfillChip({ className }: { className?: string }) {
  return (
    <Tip
      className={className}
      content={
        <span className="block max-w-60">
          <span className="block font-semibold">Backfilled</span>
          <span className="mt-0.5 block text-text-2">Computed after the fact, using only data that existed before kickoff. Not a prediction recorded live.</span>
        </span>
      }
    >
      <Chip tone="neutral" className="border-dashed">
        Backfilled
      </Chip>
    </Tip>
  );
}

export function UncertaintyChip({ prediction, long }: { prediction: Prediction; long?: boolean }) {
  const u = UNCERTAINTY[prediction.uncertainty];
  const reasons = prediction.uncertainty_reasons;
  return (
    <Tip
      content={
        <span className="block min-w-48">
          <span className="block font-semibold">{u.label}</span>
          <span className="mt-0.5 block text-text-2">How reliable this estimate is. Separate from win probability.</span>
          {reasons.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-4">
              {reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          ) : (
            <span className="mt-2 block text-text-2">No specific reasons flagged.</span>
          )}
        </span>
      }
    >
      <Chip tone={u.tone}>{long ? u.label : u.short}</Chip>
    </Tip>
  );
}
