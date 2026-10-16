"use client";

import type { GameSummary } from "@nflpi/shared";
import { useLocked, useLockMinutes } from "@/lib/clock";
import { useSetPick } from "@/lib/queries";
import { effectivePick, usePendingPicks } from "@/lib/sync";
import { TeamLogo } from "@/components/team";
import { Check, Lock } from "@/components/icons";
import { cx } from "@/components/ui";

type PickGame = Pick<GameSummary, "game_id" | "season" | "week" | "away" | "home" | "my_pick" | "locked" | "kickoff_utc" | "time_tbd" | "status">;

/**
 * One-tap pick. Away on the left, home on the right (matches "away @ home").
 * Tapping the selected team clears the pick. Disabled at the configured pregame lock.
 */
export function PickButtons({ game, size = "sm", className }: { game: PickGame; size?: "sm" | "lg"; className?: string }) {
  const mutation = useSetPick(game.game_id);
  const locked = useLocked(game);
  const lockWording = `Locked ${useLockMinutes()} min before kickoff`;
  const pending = usePendingPicks();
  const { pick, waiting } = effectivePick(pending, game.game_id, game.my_pick);
  const teams = [game.away, game.home];

  return (
    <div className={className}>
    <div role="group" aria-label={`Your pick: ${game.away.abbr} at ${game.home.abbr}`} className="flex gap-2 lg:gap-1.5">
      {teams.map((t) => {
        const selected = pick === t.abbr;
        const label = selected ? `${t.name} picked. ${locked ? `${lockWording}.` : "Tap to clear."}` : locked ? `Pick ${t.name} (${lockWording.toLowerCase()})` : `Pick ${t.name}`;
        return (
          <button
            key={t.abbr}
            type="button"
            aria-pressed={selected}
            aria-label={label}
            title={locked ? lockWording : selected ? "Tap again to clear" : `Pick ${t.name}`}
            disabled={locked}
            onClick={() => mutation.mutate({ gameId: game.game_id, season: game.season, week: game.week, team: selected ? null : t.abbr })}
            className={cx(
              "relative z-10 inline-flex items-center justify-center gap-1.5 rounded-full border font-semibold transition-[transform,background-color,border-color,opacity] active:translate-y-px",
              size === "sm" ? "h-12 min-w-[68px] flex-1 px-2 text-base lg:h-10 lg:text-sm" : "h-12 flex-1 px-3 text-base lg:h-11 lg:text-sm",
              selected && waiting
                ? "border-dashed border-accent-text bg-transparent text-accent-text"
                : selected
                ? "border-transparent bg-accent text-accent-ink"
                : locked
                  ? "border-transparent bg-elevated text-text"
                  : "border-border-strong bg-elevated text-text hover:border-accent-text",
              locked && "cursor-not-allowed opacity-60 active:translate-y-0",
            )}
          >
            {size === "lg" && <TeamLogo team={t} size={22} className={selected ? "rounded-full bg-white/90 p-0.5" : undefined} />}
            <span>{t.abbr}</span>
            {selected && <Check size={size === "lg" ? 16 : 14} className="shrink-0" />}
            {locked && <Lock size={size === "lg" ? 16 : 14} className="shrink-0" />}
          </button>
        );
      })}
    </div>
    {locked && (
      <p className="mt-1.5 flex items-center gap-1.5 text-label text-text-2">
        <Lock size={12} className="shrink-0" />
        Locked
      </p>
    )}
    {waiting && (
      <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-warn" role="status">
        <span className="rounded-chip border border-warn/40 bg-warn/12 px-1.5 py-px font-medium">Waiting to sync</span>
      </p>
    )}
    </div>
  );
}
