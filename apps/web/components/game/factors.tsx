"use client";

import type { GameDetail } from "@nflpi/shared";
import { Section, cx } from "@/components/ui";
import { teamAccent } from "@/lib/team";

export function Factors({ game }: { game: GameDetail }) {
  const p = game.prediction;
  const factors = p?.factors ?? [];
  const max = Math.max(0.0001, ...factors.map((f) => Math.abs(f.weight)));
  const sorted = [...factors].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));

  return (
    <Section id="factors" title="Key factors" note="What moved the model, largest first.">
      {!p || sorted.length === 0 ? (
        <p className="text-sm text-text-2">No factors recorded for this prediction.</p>
      ) : (
        <>
          <div className="hidden items-end gap-4 pb-2 text-[11px] font-medium text-subtle sm:grid sm:grid-cols-[minmax(0,1fr)_minmax(0,260px)_44px]">
            <span>Factor</span>
            <span className="grid min-w-0 grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <span className="pr-3 text-right">Favors {game.away.abbr}</span>
              <span className="pl-3">Favors {game.home.abbr}</span>
            </span>
            <span className="text-right">Weight</span>
          </div>
          <ul className="divide-y divide-border">
            {sorted.map((f) => {
              const side = f.favors === game.away.abbr ? "away" : f.favors === game.home.abbr ? "home" : null;
              const team = side === "away" ? game.away : side === "home" ? game.home : null;
              const width = `${(Math.abs(f.weight) / max) * 100}%`;
              return (
                <li key={f.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,260px)_44px]">
                  <div className="col-span-2 min-w-0 sm:col-span-1">
                    <p className="text-sm font-medium text-text">{f.label}</p>
                    <p className="mt-0.5 text-xs text-text-2">{f.detail}</p>
                    {team && <p className="mt-0.5 text-[11px] text-subtle sm:hidden">Favors {team.abbr}</p>}
                  </div>
                  <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" role="img" aria-label={team ? `${f.label} favors ${team.abbr}, weight ${Math.abs(f.weight).toFixed(2)}` : `${f.label}, no side`}>
                    <div className="flex min-w-0 justify-end border-r border-border pr-0">
                      {side === "away" && team && (
                        <span style={{ ...teamAccent(team), width }} className="team-accent block h-2 max-w-full rounded-l-full" />
                      )}
                    </div>
                    <div className="flex min-w-0 justify-start">
                      {side === "home" && team && <span style={{ ...teamAccent(team), width }} className="team-accent block h-2 max-w-full rounded-r-full" />}
                    </div>
                  </div>
                  <p className={cx("text-xs sm:text-right", team ? "text-text-2" : "text-subtle")}>
                    <span className="text-subtle sm:hidden">Weight </span>
                    {Math.abs(f.weight).toFixed(2)}
                  </p>
                </li>
              );
            })}
          </ul>
          <p className="mt-4 text-[11px] text-subtle">Bar length is each factor&apos;s weight relative to the largest one. A factor that favors the other side pulls the pick the other way.</p>
        </>
      )}
    </Section>
  );
}
