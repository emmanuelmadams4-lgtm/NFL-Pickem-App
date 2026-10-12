"use client";

import Link from "next/link";
import { kickoffTime, marketFavorite, pickProb, pct, strengthLabel, type GameSummary, type Team } from "@nflpi/shared";
import { Chip, Mark, Tip, cx } from "@/components/ui";
import { TeamBar, TeamLogo } from "@/components/team";
import { BackfillChip, ProbBar, UncertaintyChip } from "@/components/prediction-bits";
import { PickButtons } from "@/components/pick-buttons";
import { shortDay } from "@/lib/fmt";

export const ROW_GRID =
  "lg:grid-cols-[76px_minmax(176px,224px)_minmax(196px,1fr)_88px_96px_minmax(160px,1.2fr)_148px_104px]";

/** Desktop: a table cell. Phones: an optional inline label (`inline` puts it beside the value). */
function Cell({ label, inline, className, children }: { label?: string; inline?: boolean; className?: string; children: React.ReactNode }) {
  return (
    <div className={cx("min-w-0", inline && "flex items-center gap-2 lg:block", className)}>
      {label && <p className={cx("text-[11px] text-subtle lg:hidden", !inline && "mb-1")}>{label}</p>}
      {children}
    </div>
  );
}

function TeamLine({ team, record, score, home, winner, dim }: { team: Team; record: string; score: number | null; home?: boolean; winner?: boolean; dim?: boolean }) {
  return (
    <div className={cx("flex items-center gap-2", dim && "text-text-2")}>
      <span aria-hidden className="w-3 text-center text-[11px] text-subtle">
        {home ? "@" : ""}
      </span>
      <TeamBar team={team} className="h-5" />
      <TeamLogo team={team} size={22} />
      <span className={cx("text-sm", winner ? "font-semibold text-text" : "font-semibold")}>{team.abbr}</span>
      <span className="text-xs text-subtle">{record}</span>
      {score !== null && (
        <span className={cx("ml-auto pr-1 text-sm", winner ? "font-semibold text-text" : "text-text-2")}>{score}</span>
      )}
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

export function GameRow({ game }: { game: GameSummary }) {
  const p = game.prediction;
  const fav = marketFavorite(game);
  const started = game.status !== "scheduled";
  const final = game.status === "final";
  const pickTeam: Team | null = p ? (p.pick === game.home.abbr ? game.home : game.away) : null;
  const awayWon = final && (game.away_score ?? 0) > (game.home_score ?? 0);
  const homeWon = final && (game.home_score ?? 0) > (game.away_score ?? 0);
  const prob = p ? pickProb(p) : null;
  const hasAlerts = game.qb_alerts.length > 0 || !!(p && p.upset_flags.length > 0);

  return (
    <li className={cx("relative grid grid-cols-2 items-center gap-x-4 gap-y-3 rounded-card border border-border bg-surface p-4 transition-colors hover:bg-elevated/60 lg:rounded-none lg:border-0 lg:bg-transparent lg:px-4 lg:py-3", ROW_GRID)}>
      <Cell className="col-span-2 flex items-baseline gap-2 lg:col-span-1 lg:block">
        <p className="text-sm font-medium text-text">{kickoffTime(game.kickoff_utc)}</p>
        <p className="text-xs text-subtle">{shortDay(game.kickoff_utc)}</p>
        {game.status === "in_progress" && <Chip className="ml-auto lg:mt-1 lg:ml-0">Live</Chip>}
        {final && <p className="ml-auto text-xs text-text-2 lg:mt-0.5 lg:ml-0">Final</p>}
      </Cell>

      <Cell className="col-span-2 lg:col-span-1">
        <Link
          href={`/game/?id=${game.game_id}`}
          aria-label={`Open matchup: ${game.away.name} at ${game.home.name}`}
          className="absolute inset-0 z-0 rounded-none focus-visible:outline-offset-[-2px]"
        />
        <div className="space-y-1.5">
          <TeamLine team={game.away} record={game.away_record} score={started ? game.away_score : null} winner={awayWon} dim={final && !awayWon} />
          <TeamLine team={game.home} record={game.home_record} score={started ? game.home_score : null} home winner={homeWon} dim={final && !homeWon} />
        </div>
      </Cell>

      <Cell className="col-span-2 lg:col-span-1">
        {p && pickTeam && prob !== null ? (
          <div>
            <div className="flex items-center gap-2">
              <TeamLogo team={pickTeam} size={18} />
              <span className="text-sm font-semibold">{p.pick}</span>
              <span className="num-display text-base font-semibold text-text">{pct(prob)}</span>
              {p.kind === "backfill" && <BackfillChip />}
            </div>
            <ProbBar value={prob} className="mt-1.5" label={`${p.pick} win probability`} />
            <p className="mt-1 text-xs text-subtle lg:text-[11px]">{strengthLabel(prob)}</p>
          </div>
        ) : (
          <p className="text-sm text-subtle">No prediction yet</p>
        )}
      </Cell>

      <Cell label="Uncertainty" inline>
        {p ? <UncertaintyChip prediction={p} /> : <span className="text-sm text-subtle">-</span>}
      </Cell>

      <Cell label="Market" inline>
        {fav ? (
          <p className="text-sm">
            <span className="font-semibold">{fav.team}</span> <span className="text-text-2">{pct(fav.prob)}</span>
          </p>
        ) : (
          <p className="text-sm text-subtle">No line yet</p>
        )}
      </Cell>

      <Cell className={cx("col-span-2 lg:col-span-1", !hasAlerts && "hidden lg:block")}>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {game.qb_alerts.slice(0, 2).map((a) => {
            const { who, status } = alertParts(a);
            return (
              <span key={a} className="inline-flex max-w-full items-center gap-1.5 text-xs text-text-2">
                <span className="truncate">{who}</span>
                {status && <Chip tone={statusTone(status)}>{status}</Chip>}
              </span>
            );
          })}
          {game.qb_alerts.length > 2 && <span className="text-xs text-subtle">+{game.qb_alerts.length - 2} more</span>}
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
          {!hasAlerts && <span className="text-sm text-subtle">None</span>}
        </div>
      </Cell>

      <Cell className="col-span-2 lg:col-span-1">
        <PickButtons game={game} />
      </Cell>

      <Cell className="col-span-2 lg:col-span-1">
        {final ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-0.5 lg:block lg:space-y-0.5">
            {game.my_pick ? <Mark correct={game.my_pick_correct} who="Me" /> : <span className="block text-xs text-subtle">No pick made</span>}
            <div>
              <Mark correct={game.model_correct} who="Model" />
            </div>
          </div>
        ) : game.status === "in_progress" ? (
          <p className="text-xs text-text-2">In progress</p>
        ) : (
          <p className="text-xs text-subtle">{game.locked ? "Locked" : "Open until kickoff"}</p>
        )}
      </Cell>
    </li>
  );
}
