"use client";

import { ago, pct, pickProb, type GameDetail } from "@nflpi/shared";
import { Chip, Section } from "@/components/ui";
import { TimeLine } from "@/components/charts/time-line";
import { dateTime } from "@/lib/fmt";

export function History({ game }: { game: GameDetail }) {
  const snaps = [...game.prediction_history].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const chart = [...snaps].reverse().map((p) => ({ t: new Date(p.created_at).getTime(), v: p.home_win_prob, hollow: p.kind === "backfill" }));

  return (
    <Section id="history" title="Prediction history" note="Every snapshot of the model for this game, newest first.">
      {snaps.length === 0 ? (
        <p className="text-sm text-text-2">No prediction snapshots yet.</p>
      ) : (
        <div className="space-y-6">
          {chart.length >= 2 && (
            <div>
              <h3 className="mb-2 text-xs font-medium text-text">{game.home.abbr} win probability across snapshots</h3>
              <TimeLine data={chart} name={`${game.home.abbr} win probability`} color="var(--series-model)" label={`Line chart of ${game.home.abbr} win probability across ${chart.length} prediction snapshots`} />
            </div>
          )}
          <ol className="space-y-0">
            {snaps.map((p, i) => (
              <li key={p.id} className="relative flex gap-4 pb-5 last:pb-0">
                <span aria-hidden className="absolute top-2 bottom-0 left-[3px] w-px bg-border last:hidden" />
                <span
                  aria-hidden
                  className={`relative mt-1.5 size-[7px] shrink-0 rounded-full ${p.kind === "backfill" ? "border-2 border-text-2 bg-bg" : i === 0 ? "bg-text-2" : "bg-muted"}`}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <p className="text-sm font-semibold text-text">
                      {p.pick} <span className="font-medium text-text-2">{pct(pickProb(p))}</span>
                    </p>
                    {p.kind === "backfill" ? <Chip className="border-dashed">Backfilled</Chip> : <Chip>Live</Chip>}
                    {i === 0 && <span className="text-[11px] text-subtle">Current</span>}
                  </div>
                  <p className="mt-0.5 text-xs text-text-2">
                    {dateTime(p.created_at)}, {ago(p.created_at)}
                  </p>
                  {p.change_note && <p className="mt-1 text-sm text-text-2">{p.change_note}</p>}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </Section>
  );
}
