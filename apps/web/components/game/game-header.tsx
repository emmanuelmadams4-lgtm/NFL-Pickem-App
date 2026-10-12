"use client";

import Link from "next/link";
import type { GameDetail, Team } from "@nflpi/shared";
import { Chip } from "@/components/ui";
import { TeamLogo } from "@/components/team";
import { Check, ChevronLeft } from "@/components/icons";
import { cx } from "@/components/ui";
import { useLocked } from "@/lib/clock";
import { isIndoor, kickoffWhen } from "@/lib/fmt";

function cap(s: string | null | undefined): string {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** One side of the reference-style header: logo over the name in the display face, record and split under it. */
function TeamBlock({ team, record, split }: { team: Team; record: string; split: string }) {
  return (
    <div className="flex min-w-0 flex-col items-center gap-2 text-center">
      <TeamLogo team={team} size={72} />
      <p className="font-display text-xl leading-5 text-text lg:text-[32px] lg:leading-8">{team.name}</p>
      <p className="text-label text-text-2">
        <span className="font-medium text-text">{record}</span>
        <span className="ml-1.5 text-subtle">{split}</span>
      </p>
    </div>
  );
}

export function GameHeader({ game }: { game: GameDetail }) {
  const locked = useLocked(game);
  const started = game.status !== "scheduled";
  const final = game.status === "final";
  const scored = started && game.away_score !== null && game.home_score !== null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <Link href={`/?season=${game.season}&week=${game.week}`} className="-ml-1 inline-flex items-center gap-1 text-sm text-text-2 hover:text-text">
          <ChevronLeft />
          Week {game.week}, {game.season}
        </Link>
        <div className="flex flex-wrap items-center gap-1.5">
          {game.div_game && <Chip>Division game</Chip>}
          {game.neutral_site && <Chip>Neutral site</Chip>}
          {game.game_type !== "REG" && <Chip>{game.game_type}</Chip>}
          {game.status === "in_progress" && <Chip>In progress</Chip>}
          {final && <Chip>Final</Chip>}
          {game.status === "scheduled" && <Chip>{locked ? "Locked" : "Scheduled"}</Chip>}
        </div>
      </div>

      <h1 className="sr-only">
        {game.away.name} at {game.home.name}
      </h1>
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-3 lg:gap-8">
        <TeamBlock team={game.away} record={game.away_record} split={`Road ${game.away_form.away_record}`} />
        <div className="flex min-h-16 items-center justify-center lg:min-h-20">
          {scored ? (
            <p className="font-display text-[56px] leading-[56px] text-text lg:text-[80px] lg:leading-[80px]">
              <span className="sr-only">
                {final ? "Final score" : "Score"} {game.away.abbr} {game.away_score}, {game.home.abbr} {game.home_score}
              </span>
              <span aria-hidden>
                {game.away_score}
                <span className="text-text-2">:</span>
                {game.home_score}
              </span>
            </p>
          ) : (
            <span className="font-display grid size-14 place-items-center rounded-full border border-border bg-elevated text-2xl text-text">VS</span>
          )}
        </div>
        <TeamBlock team={game.home} record={game.home_record} split={`Home ${game.home_form.home_record}`} />
      </div>
      <p className="mt-4 text-center text-sm text-text">
        {kickoffWhen(game)}
        <span className="block text-xs text-text-2 sm:ml-2 sm:inline">
          {game.stadium ?? "Venue to be confirmed"}
          {", "}
          {[game.roof ? (isIndoor(game.roof) ? `${cap(game.roof)} roof` : cap(game.roof)) : null, game.surface ? `${cap(game.surface)} surface` : null].filter(Boolean).join(", ") ||
            "roof and surface unknown"}
        </span>
      </p>
    </div>
  );
}

/**
 * Split win-chance tiles (design.md § 0): away and home, whole percents that sum to 100, the model's side filled lime
 * and labeled "Model pick". Probability only; uncertainty stays a separate chip in the pick panel.
 */
export function WinSplit({ game }: { game: GameDetail }) {
  const p = game.prediction;
  if (!p) return null;
  const home = Math.round(p.home_win_prob * 100);
  const tiles = [
    { team: game.away, value: 100 - home },
    { team: game.home, value: home },
  ];
  return (
    <section aria-label="Model win chance" data-testid="win-split">
      <div className="grid grid-cols-2 gap-3">
        {tiles.map(({ team, value }) => {
          const model = team.abbr === p.pick;
          return (
            <div key={team.abbr} className={cx("min-w-0 rounded-card p-4 lg:p-5", model ? "bg-accent text-accent-ink" : "border border-border bg-surface text-text")}>
              <p className="font-display text-[44px] leading-[44px] lg:text-[56px] lg:leading-[56px]">{value}%</p>
              <p className="mt-1 truncate text-sm">
                <span className="font-semibold">{team.abbr}</span> <span className={model ? undefined : "text-text-2"}>{team.name}</span>
              </p>
              <p className={cx("mt-1 flex items-center gap-1 text-label font-medium", !model && "text-text-2")}>
                {model ? (
                  <>
                    <Check size={14} />
                    Model pick
                  </>
                ) : (
                  "Win chance"
                )}
              </p>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-label text-subtle">
        Model win chance{p.kind === "backfill" ? ", backfilled after the fact from pre-game inputs" : ""}. How reliable it is shows separately in the pick panel.
      </p>
    </section>
  );
}
