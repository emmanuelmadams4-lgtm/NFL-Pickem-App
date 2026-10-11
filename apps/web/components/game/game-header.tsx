"use client";

import Link from "next/link";
import { kickoffLabel, type GameDetail, type Team } from "@nflpi/shared";
import { Card, Chip } from "@/components/ui";
import { TeamLogo } from "@/components/team";
import { teamAccent } from "@/lib/team";
import { cx } from "@/components/ui";
import { isIndoor } from "@/lib/fmt";

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
        <h2 className="truncate text-xl font-semibold tracking-tight">{team.name}</h2>
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
  const started = game.status !== "scheduled";
  const final = game.status === "final";
  const awayWon = final && (game.away_score ?? 0) > (game.home_score ?? 0);
  const homeWon = final && (game.home_score ?? 0) > (game.away_score ?? 0);

  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <Link href={`/?season=${game.season}&week=${game.week}`} className="text-sm text-text-2 hover:text-text">
          <span aria-hidden>&lsaquo; </span>Week {game.week}, {game.season}
        </Link>
        <div className="flex flex-wrap items-center gap-1.5">
          {game.div_game && <Chip>Division game</Chip>}
          {game.neutral_site && <Chip>Neutral site</Chip>}
          {game.game_type !== "REG" && <Chip>{game.game_type}</Chip>}
          {game.status === "in_progress" && <Chip tone="accent">Live</Chip>}
          {final && <Chip>Final</Chip>}
          {game.status === "scheduled" && <Chip tone={game.locked ? "warn-soft" : "neutral"}>{game.locked ? "Locked" : "Scheduled"}</Chip>}
        </div>
      </div>

      <div className="grid items-center gap-x-8 gap-y-5 lg:grid-cols-[1fr_auto_1fr]">
        <TeamBlock team={game.away} record={game.away_record} split={`Road ${game.away_form.away_record}`} side="away" score={started ? game.away_score : null} winner={awayWon} />
        <div className="text-center">
          <p className="text-sm font-medium text-text">{kickoffLabel(game.kickoff_utc)}</p>
          <p className="mt-0.5 text-xs text-text-2">{game.stadium ?? "Venue to be confirmed"}</p>
          <p className="mt-0.5 text-xs text-subtle">
            {[game.roof ? (isIndoor(game.roof) ? `${cap(game.roof)} roof` : cap(game.roof)) : null, game.surface ? `${cap(game.surface)} surface` : null].filter(Boolean).join(", ") || "Roof and surface unknown"}
          </p>
        </div>
        <TeamBlock team={game.home} record={game.home_record} split={`Home ${game.home_form.home_record}`} side="home" score={started ? game.home_score : null} winner={homeWon} />
      </div>
    </Card>
  );
}
