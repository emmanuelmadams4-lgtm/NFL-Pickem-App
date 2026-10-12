"use client";

import Link from "next/link";
import { marketFavorite, pickProb, pct, type GameSummary, type Team } from "@nflpi/shared";
import { Chip, Mark, Tip, cx } from "@/components/ui";
import { TeamLogo } from "@/components/team";
import { BackfillChip, ProbBar, UncertaintyChip } from "@/components/prediction-bits";
import { PickButtons } from "@/components/pick-buttons";
import { PointsControl } from "@/components/week/points-control";
import { Refresh } from "@/components/icons";
import { useLocked } from "@/lib/clock";
import { effectivePick, usePendingPicks } from "@/lib/sync";
import { kickoffClock, scoreTone, shortDate, type ScoreTone } from "@/lib/fmt";

/** Final scores: the winning side in ink with a bold abbreviation, the loser in text-2. */
const scoreClass = (t: ScoreTone) => (t === "lost" ? "text-text-2 [&>span]:font-medium" : "text-text");

/** One side of the card's top band: logo, abbreviation in the display face, name and record. */
function TeamSide({ team, record, right, onLime }: { team: Team; record: string; right?: boolean; onLime?: boolean }) {
  return (
    <div className={cx("flex min-w-0 flex-col gap-1.5", right ? "items-end text-right" : "items-start")}>
      <TeamLogo team={team} size={40} onLight={onLime} />
      <div className="min-w-0 max-w-full">
        <p className="font-display text-2xl leading-6">{team.abbr}</p>
        <p className={cx("truncate text-label", onLime ? "text-accent-ink" : "text-text-2")}>{team.name}</p>
        <p className={cx("text-label", onLime ? "text-accent-ink" : "text-subtle")}>{record}</p>
      </div>
    </div>
  );
}

function alertParts(text: string): { who: string; status: string } {
  const i = text.lastIndexOf(": ");
  return i === -1 ? { who: text, status: "" } : { who: text.slice(0, i), status: text.slice(i + 2) };
}

function statusTone(status: string): "bad" | "warn" | "warn-soft" {
  const s = status.toLowerCase();
  if (s.startsWith("out") || s.includes("injured reserve")) return "bad";
  if (s.startsWith("doubtful")) return "warn";
  return "warn-soft";
}

/**
 * One card per game (design.md § 0, D40). Top: away, VS, home. Middle: kickoff (or the score), the model's pick with
 * its win chance and bar, uncertainty as a separate chip. Bottom: status chips, what changed, and the two pick pills.
 * The whole card opens the matchup; the pills and tooltips sit above that link. `highlight` fills the top band lime
 * (the next game to kick off; at most one per board).
 */
const labelWords = { easy_pick: ["Easy pick", "Easy picks"], tough_matchup: ["Tough matchup", "Tough matchups"], coin_flip: ["Coin flip", "Coin flips"] } as const;

export function GameCard({ game, highlight, pointsCount }: { game: GameSummary; highlight?: boolean; pointsCount: number }) {
  const p = game.prediction;
  const fav = marketFavorite(game);
  const locked = useLocked(game);
  const pending = usePendingPicks();
  const mine = effectivePick(pending, game.game_id, game.my_pick).pick;
  const started = game.status !== "scheduled";
  const final = game.status === "final";
  const pickTeam: Team | null = p ? (p.pick === game.home.abbr ? game.home : game.away) : null;
  const prob = p ? pickProb(p) : null;
  const differs = !!(p && mine && mine !== p.pick);
  const away = game.away_score;
  const home = game.home_score;

  return (
    <li data-testid="game-card" className="relative flex flex-col overflow-hidden rounded-card border border-border bg-surface transition-colors hover:border-border-strong">
      <Link
        href={`/game/?id=${game.game_id}`}
        aria-label={`Open matchup: ${game.away.name} at ${game.home.name}`}
        className="absolute inset-0 z-0 rounded-card focus-visible:outline-offset-[-2px]"
      />

      <div className={cx("grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 p-4", highlight ? "bg-accent text-accent-ink" : "text-text")}>
        <TeamSide team={game.away} record={game.away_record} onLime={highlight} />
        <span className={cx("font-display grid size-11 shrink-0 place-items-center rounded-full text-lg", highlight ? "bg-accent-ink text-accent" : "border border-border bg-elevated text-text")}>
          VS
        </span>
        <TeamSide team={game.home} record={game.home_record} right onLime={highlight} />
      </div>

      <div className="flex flex-1 flex-col gap-3 border-t border-border p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <p className="text-label text-text-2">
              {shortDate(game.kickoff_utc)}
              {highlight && <span className="text-accent-text">, next kickoff</span>}
            </p>
            {started && away !== null && home !== null ? (
              <p className="font-display flex items-baseline gap-1.5 text-[32px] leading-9 whitespace-nowrap">
                <span className="sr-only">
                  {final ? "Final score" : "Score"} {game.away.abbr} {away}, {game.home.abbr} {home}
                </span>
                <span aria-hidden className={scoreClass(final ? scoreTone(away, home) : "even")}>
                  <span className="mr-1 font-sans text-sm">{game.away.abbr}</span>
                  {away}
                </span>
                <span aria-hidden className="font-sans font-normal text-text-2">
                  –
                </span>
                <span aria-hidden className={scoreClass(final ? scoreTone(home, away) : "even")}>
                  {home}
                  <span className="ml-1 font-sans text-sm">{game.home.abbr}</span>
                </span>
              </p>
            ) : game.status === "postponed" ? (
              <p className="py-1.5"><Chip tone="warn">Postponed</Chip></p>
            ) : (
              <p className="font-display text-[32px] leading-9 text-text">{kickoffClock(game)}</p>
            )}
          </div>
          {p && pickTeam && prob !== null && (
            <div className="text-right">
              <p className="text-label text-text-2">Model pick</p>
              <p className="flex items-center justify-end gap-1.5">
                <TeamLogo team={pickTeam} size={20} />
                <span className="text-sm font-semibold">{p.pick}</span>
                <span className="font-display text-[32px] leading-9 text-text">{pct(prob)}</span>
              </p>
            </div>
          )}
        </div>

        {p && prob !== null ? (
          <div>
            <ProbBar value={prob} fromRight={p.pick === game.home.abbr} label={`${p.pick} win probability`} />
            <div className="mt-2">
              {game.sheet.label && game.sheet.label in labelWords && (
                <p className="text-sm font-medium text-text">
                  <span data-testid="pick-label">{labelWords[game.sheet.label as keyof typeof labelWords][0]}</span>
                  {game.sheet.label_hit_rate !== null && (
                    <span className="font-normal text-text-2"> · {labelWords[game.sheet.label as keyof typeof labelWords][1]} have won {pct(game.sheet.label_hit_rate)} since 2012</span>
                  )}
                </p>
              )}
              <span className="mt-1 flex items-center gap-1.5 text-label text-subtle">
                Uncertainty <UncertaintyChip prediction={p} />
              </span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-subtle">No prediction yet</p>
        )}
        <p className="text-label text-text-2">
          Market{" "}
          {fav ? (
            <>
              <span className="font-semibold text-text">{fav.team}</span> {pct(fav.prob)}
            </>
          ) : (
            <span className="text-subtle">no line yet</span>
          )}
        </p>

        <div className="flex flex-wrap items-center gap-1.5">
          {game.status === "in_progress" && <Chip>In progress</Chip>}
          {final && <Chip>Final</Chip>}
          {p?.kind === "backfill" && <BackfillChip />}
          {differs && <Chip tone="accent">Differs from model</Chip>}
          {p && p.upset_flags.length > 0 && (
            <Tip
              content={
                <span className="block min-w-48">
                  <span className="block font-semibold">Upset watch</span>
                  <ul className="mt-1.5 list-disc space-y-1 pl-4">
                    {p.upset_flags.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </span>
              }
            >
              <Chip tone="warn">Upset watch</Chip>
            </Tip>
          )}
          {game.qb_alerts.slice(0, 2).map((a) => {
            const { who, status } = alertParts(a);
            return (
              <span key={a} className="inline-flex max-w-full items-center gap-1.5 text-label text-text-2">
                <span className="truncate">{who}</span>
                {status && <Chip tone={statusTone(status)}>{status}</Chip>}
              </span>
            );
          })}
          {game.qb_alerts.length > 2 && <span className="text-label text-subtle">+{game.qb_alerts.length - 2} more</span>}
        </div>

        {p?.change_note && (
          <p className="flex items-start gap-1.5 text-label text-text-2">
            <Refresh size={14} className="mt-px shrink-0" />
            <span>
              <span className="font-medium text-text">What changed:</span> {p.change_note}
            </span>
          </p>
        )}

        <PointsControl game={game} count={pointsCount} />

        <div className="mt-auto pt-1">
          {game.sheet.pick_by === "app" && !locked && game.sheet.app_pick && (
            <p className="mb-2 text-label text-text-2">Counts as {game.sheet.app_pick}, the model&apos;s pick, unless you tap a team.</p>
          )}
          {game.sheet.pick_by === "auto" && <p className="mb-2"><Chip>Model picked {game.sheet.my_pick} for you</Chip></p>}
          <PickButtons game={game} />
          {final && (
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-0.5">
              {game.my_pick ? <Mark correct={game.my_pick_correct} who={game.sheet.pick_by === "auto" ? "Picked for you" : "Me"} /> : <span className="text-label text-subtle">No pick made</span>}
              <Mark correct={game.model_correct} who="Model" />
            </div>
          )}
        </div>
      </div>
    </li>
  );
}
