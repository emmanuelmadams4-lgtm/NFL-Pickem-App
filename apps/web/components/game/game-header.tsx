"use client";

import Link from "next/link";
import type { GameDetail, Team } from "@nflpi/shared";
import { Chip } from "@/components/ui";
import { TeamLogo } from "@/components/team";
import { ChevronLeft } from "@/components/icons";
import { cx } from "@/components/ui";
import { useLocked } from "@/lib/clock";
import { isIndoor, kickoffWhen, scoreTone, type ScoreTone } from "@/lib/fmt";
import type { CardLiveState } from "@/components/live/state";

function cap(s: string | null | undefined): string {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** One side of the reference-style header: Away or Home, logo over the name in the display face, record and split under it. */
function TeamBlock({ team, side, record, split }: { team: Team; side: "Away" | "Home"; record: string; split: string }) {
  return (
    <div className="flex min-w-0 flex-col items-center gap-2 text-center">
      <p className="text-label text-subtle">{side}</p>
      <TeamLogo team={team} size={72} />
      <p className="font-display text-xl leading-5 text-text lg:text-[32px] lg:leading-8">{team.name}</p>
      <p className="text-label text-text-2">
        <span className="font-medium text-text">{record}</span>
        <span className="ml-1.5 text-subtle">{split}</span>
      </p>
    </div>
  );
}

/** One side of the score: the figure in the display face with its team abbreviation under it; the loser in text-2. */
function ScoreSide({ abbr, score, tone }: { abbr: string; score: number; tone: ScoreTone }) {
  return (
    <span aria-hidden className={cx("flex flex-col items-center", tone === "lost" ? "text-text-2" : "text-text")}>
      <span>{score}</span>
      <span className={cx("font-sans text-sm leading-5", tone === "won" ? "font-bold" : "font-medium")}>{abbr}</span>
    </span>
  );
}

export function GameHeader({ game, live }: { game: GameDetail; live: CardLiveState | null }) {
  const locked = useLocked(game);
  const started = game.status !== "scheduled";
  const final = game.status === "final";
  const away = game.away_score;
  const home = game.home_score;
  const scored = started && away !== null && home !== null;

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
          {final && <Chip>Final</Chip>}
          {game.status === "scheduled" && !live && <Chip>{locked ? "Locked" : "Scheduled"}</Chip>}
          {game.status === "postponed" && <Chip tone="warn">Postponed</Chip>}
        </div>
      </div>

      <h1 className="sr-only">
        {game.away.name} at {game.home.name}
      </h1>
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-3 lg:gap-8">
        <TeamBlock team={game.away} side="Away" record={game.away_record} split={`Road ${game.away_form.away_record}`} />
        <div className={cx("flex min-h-16 flex-col items-center justify-center lg:min-h-20", live && "w-28 sm:w-auto")}>
          {live ? (
            <>
              <p className="flex min-h-10 max-w-full items-end justify-center text-center text-sm text-text-2 sm:min-h-0">
                <span aria-hidden="true" className="break-words">
                  {live.kind === "S3" || live.kind === "S4" ? <><span className="text-warn">Not updating</span>{live.label.slice("Not updating".length)}</>
                    : live.kind === "S5" ? <><span className="text-text">Live<span className="text-text-2">{live.label.slice(4, 6)}</span></span>{live.label.slice(6)}</> : live.label}
                </span>
                <span className="sr-only">{live.reader}</span>
              </p>
              {live.score ? (
                <p aria-hidden="true" className={cx("flex max-w-full items-start gap-1 font-display text-[40px] leading-[42px] tabular-nums lg:gap-4 lg:text-[80px] lg:leading-[80px]", live.kind === "S3" || live.kind === "S4" ? "text-text-2" : "text-text")}>
                  <ScoreSide abbr={game.away.abbr} score={live.score.away} tone={live.kind === "S3" || live.kind === "S4" ? "lost" : "even"} />
                  <span className="font-sans font-normal">–</span>
                  <ScoreSide abbr={game.home.abbr} score={live.score.home} tone={live.kind === "S3" || live.kind === "S4" ? "lost" : "even"} />
                </p>
              ) : <p aria-hidden="true" className="max-w-full text-center text-label text-text-2">No live score right now</p>}
            </>
          ) : scored ? (
            <p className="font-display flex items-start gap-2 text-[48px] leading-[48px] lg:gap-4 lg:text-[80px] lg:leading-[80px]">
              <span className="sr-only">
                {final ? "Final score" : "Score"} {game.away.abbr} {away}, {game.home.abbr} {home}
              </span>
              <ScoreSide abbr={game.away.abbr} score={away} tone={final ? scoreTone(away, home) : "even"} />
              <span aria-hidden className="font-sans font-normal text-text-2">
                –
              </span>
              <ScoreSide abbr={game.home.abbr} score={home} tone={final ? scoreTone(home, away) : "even"} />
            </p>
          ) : (
            <span className="font-display grid size-14 place-items-center rounded-full border border-border bg-elevated text-2xl text-text">VS</span>
          )}
        </div>
        <TeamBlock team={game.home} side="Home" record={game.home_record} split={`Home ${game.home_form.home_record}`} />
      </div>
      <p className="mt-4 text-center text-sm text-text">
        {game.status === "postponed" ? "New time to be announced" : kickoffWhen(game)}
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
 * Split win-chance tiles (design.md § 0): away and home, whole percents that sum to 100. The model's side has a strong
 * outline and the words "Model pick", never a lime fill or a check (lime is mine). Probability only; uncertainty stays a
 * separate chip in the pick panel.
 */
export function WinSplit({ game, started = false }: { game: GameDetail; started?: boolean }) {
  const p = game.prediction;
  if (!p) return null;
  const home = Math.round(p.home_win_prob * 100);
  const backfill = p.kind === "backfill";
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
            <div
              key={team.abbr}
              data-testid={model ? "win-tile-model" : undefined}
              className={cx("min-w-0 rounded-card bg-surface p-4 text-text lg:p-5", model ? "border-2 border-text" : "border border-border")}
            >
              <p className={cx("font-display text-[44px] leading-[44px] lg:text-[56px] lg:leading-[56px]", !model && "text-text-2")}>{value}%</p>
              <p className="mt-1 truncate text-sm">
                <span className="font-semibold">{team.abbr}</span> <span className="text-text-2">{team.name}</span>
              </p>
              <p className={cx("mt-1 flex flex-wrap items-center gap-1.5 text-label font-medium", !model && "text-text-2")}>
                {model ? "Model pick" : "Win chance"}
                {model && backfill && (
                  <Chip tone="neutral" className="border-dashed">
                    Backfilled
                  </Chip>
                )}
              </p>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-label text-subtle">
        {started ? `Model win chance before kickoff${backfill ? ", backfilled after the fact from pre-game inputs" : ""}. It does not change during the game.` : `Model win chance${backfill ? ", backfilled after the fact from pre-game inputs" : ""}. How reliable it is shows separately in the pick panel.`}
      </p>
    </section>
  );
}
