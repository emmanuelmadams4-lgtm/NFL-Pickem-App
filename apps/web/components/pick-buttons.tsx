"use client";

import type { GameSummary } from "@nflpi/shared";
import { useSetPick } from "@/lib/queries";
import { effectivePick, usePendingPicks } from "@/lib/sync";
import { TeamLogo } from "@/components/team";
import { cx } from "@/components/ui";

type PickGame = Pick<GameSummary, "game_id" | "season" | "week" | "away" | "home" | "my_pick" | "locked">;

/**
 * One-tap pick. Away on the left, home on the right (matches "away @ home").
 * Tapping the selected team clears the pick. Disabled once the game has kicked off.
 */
export function PickButtons({ game, size = "sm", className }: { game: PickGame; size?: "sm" | "lg"; className?: string }) {
  const mutation = useSetPick();
  const pending = usePendingPicks();
  const { pick, waiting } = effectivePick(pending, game.game_id, game.my_pick);
  const teams = [game.away, game.home];

  return (
    <div className={className}>
    <div role="group" aria-label={`Your pick: ${game.away.abbr} at ${game.home.abbr}`} className="flex gap-2 lg:gap-1.5">
      {teams.map((t) => {
        const selected = pick === t.abbr;
        const label = selected ? `${t.name} picked. ${game.locked ? "Locked at kickoff." : "Tap to clear."}` : game.locked ? `Pick ${t.name} (locked at kickoff)` : `Pick ${t.name}`;
        return (
          <button
            key={t.abbr}
            type="button"
            aria-pressed={selected}
            aria-label={label}
            title={game.locked ? "Locked at kickoff" : selected ? "Tap again to clear" : `Pick ${t.name}`}
            disabled={game.locked}
            onClick={() => mutation.mutate({ gameId: game.game_id, season: game.season, week: game.week, team: selected ? null : t.abbr })}
            className={cx(
              "relative z-10 inline-flex items-center justify-center gap-1.5 rounded-ctl border font-semibold transition-[transform,background-color,border-color,opacity] duration-150 active:translate-y-px",
              size === "sm" ? "h-12 min-w-[68px] flex-1 px-2 text-base lg:h-8 lg:text-xs" : "h-12 flex-1 px-3 text-base lg:h-11 lg:text-sm",
              selected
                ? "border-transparent bg-accent-solid text-white"
                : "border-border bg-elevated text-text hover:border-accent",
              game.locked && "cursor-not-allowed active:translate-y-0",
              game.locked && !selected && "opacity-55 hover:border-border",
              game.locked && selected && "opacity-80",
            )}
          >
            {size === "lg" && <TeamLogo team={t} size={22} className={selected ? "rounded-full bg-white/90 p-0.5" : undefined} />}
            <span>{t.abbr}</span>
            {selected && (
              <span aria-hidden className="text-[11px] leading-none">
                &#10003;
              </span>
            )}
          </button>
        );
      })}
    </div>
    {waiting && (
      <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-warn" role="status">
        <span className="rounded-chip border border-warn/40 bg-warn/12 px-1.5 py-px font-medium">Waiting to sync</span>
      </p>
    )}
    </div>
  );
}
