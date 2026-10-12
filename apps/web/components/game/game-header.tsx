"use client";

import Link from "next/link";
import type { GameDetail, Team } from "@nflpi/shared";
import { Chip } from "@/components/ui";
import { TeamLogo } from "@/components/team";
import { ChevronLeft } from "@/components/icons";
import { teamAccent } from "@/lib/team";
import { cx } from "@/components/ui";
import { useLocked } from "@/lib/clock";
import { isIndoor, kickoffWhen } from "@/lib/fmt";

function cap(s: string | null | undefined): string {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function TeamBlock({ team, record, split, side, score, winner }: { team: Team; record: string; split: string; side: "away" | "home"; score: number | null; winner: boolean }) {
  const right = side === "home";
  return (
    <div className={cx("flex min-w-0 items-center gap-4", right && "lg:flex-row-reverse lg:text-right")}>
      <div style={teamAccent(team)} className={cx("team-accent h-14 w-[3px] shrink-0 rounded-full", right && "lg:order-last")} aria-hidden />
      <TeamLogo team={team} size={56} className="lg:size-16" />
      <div className="min-w-0">
        <p className="text-xs text-subtle">{side === "away" ? "Away" : "Home"}</p>
        <p className="truncate text-xl font-semibold tracking-tight">{team.name}</p>
        <p className="mt-0.5 text-sm text-text-2">
          <span className="font-medium text-text">{record}</span>
          <span className="ml-2 text-subtle">{split}</span>
        </p>
      </div>
      {score !== null && (
        <p className={cx("num-display mx-2 text-5xl leading-none font-semibold", winner ? "text-text" : "text-text-2")}>{score}</p>
      )}
    </div>
  );
}

export function GameHeader({ game }: { game: GameDetail }) {
  const locked = useLocked(game);
  const started = game.status !== "scheduled";
  const final = game.status === "final";
  const awayWon = final && (game.away_score ?? 0) > (game.home_score ?? 0);
  const homeWon = final && (game.home_score ?? 0) > (game.away_score ?? 0);

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
          {game.status === "in_progress" && <Chip>Live</Chip>}
          {final && <Chip>Final</Chip>}
          {game.status === "scheduled" && <Chip tone={locked ? "warn-soft" : "neutral"}>{locked ? "Locked" : "Scheduled"}</Chip>}
        </div>
      </div>

      <h1 className="sr-only">
        {game.away.name} at {game.home.name}
      </h1>
      <div className="grid items-center gap-x-8 gap-y-5 lg:grid-cols-[1fr_auto_1fr]">
        <TeamBlock team={game.away} record={game.away_record} split={`Road ${game.away_form.away_record}`} side="away" score={started ? game.away_score : null} winner={awayWon} />
        <div className="text-center">
          <p className="text-sm font-medium text-text">{kickoffWhen(game)}</p>
          <p className="mt-0.5 text-xs text-text-2">{game.stadium ?? "Venue to be confirmed"}</p>
          <p className="mt-0.5 text-xs text-subtle">
            {[game.roof ? (isIndoor(game.roof) ? `${cap(game.roof)} roof` : cap(game.roof)) : null, game.surface ? `${cap(game.surface)} surface` : null].filter(Boolean).join(", ") || "Roof and surface unknown"}
          </p>
        </div>
        <TeamBlock team={game.home} record={game.home_record} split={`Home ${game.home_form.home_record}`} side="home" score={started ? game.home_score : null} winner={homeWon} />
      </div>
    </div>
  );
}
