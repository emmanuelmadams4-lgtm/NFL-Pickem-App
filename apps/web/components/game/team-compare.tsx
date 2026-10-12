"use client";

import type { GameDetail, TeamForm } from "@nflpi/shared";
import { Section, cx } from "@/components/ui";
import { TeamLogo } from "@/components/team";
import { num, signed } from "@/lib/fmt";

type Better = "high" | "low" | null;

interface Row {
  label: string;
  away: React.ReactNode;
  home: React.ReactNode;
  awayN?: number | null;
  homeN?: number | null;
  better?: Better;
  note?: string;
}

function winner(r: Row): "away" | "home" | null {
  if (!r.better || r.awayN == null || r.homeN == null || r.awayN === r.homeN) return null;
  const awayBetter = r.better === "high" ? r.awayN > r.homeN : r.awayN < r.homeN;
  return awayBetter ? "away" : "home";
}

function qbCell(f: TeamForm) {
  if (!f.qb) return <span className="text-subtle">Unknown</span>;
  return (
    <span>
      {f.qb}
      {f.prev_qb && f.prev_qb !== f.qb && <span className="mt-0.5 block text-[11px] font-normal text-warn">was {f.prev_qb} last game</span>}
    </span>
  );
}

const NO_GAMES = <span className="text-subtle">No games yet</span>;
const NOT_LISTED = <span className="text-subtle">Not listed</span>;

/** A value, or the reason it is missing. Never a bare dash. */
function show(v: number | null, fmt: (n: number | null) => string, none: React.ReactNode): React.ReactNode {
  return v === null ? none : fmt(v);
}

export function TeamCompare({ game }: { game: GameDetail }) {
  const a = game.away_form;
  const h = game.home_form;
  // points_for_pg is null only when the team has no earlier game this season (views._form); the form figures are then missing too.
  const gp = (f: TeamForm, v: number | null, fmt: (n: number | null) => string) => show(v, fmt, f.points_for_pg === null ? NO_GAMES : NOT_LISTED);
  const rows: Row[] = [
    { label: "Record", away: a.record, home: h.record },
    { label: "Home record", away: a.home_record, home: h.home_record },
    { label: "Away record", away: a.away_record, home: h.away_record },
    { label: "Points for / game", away: gp(a, a.points_for_pg, num), home: gp(h, h.points_for_pg, num), awayN: a.points_for_pg, homeN: h.points_for_pg, better: "high" },
    { label: "Points against / game", away: gp(a, a.points_against_pg, num), home: gp(h, h.points_against_pg, num), awayN: a.points_against_pg, homeN: h.points_against_pg, better: "low" },
    { label: "Last 3 avg margin", away: gp(a, a.last3_margin, signed), home: gp(h, h.last3_margin, signed), awayN: a.last3_margin, homeN: h.last3_margin, better: "high" },
    { label: "Last 5 avg margin", away: gp(a, a.last5_margin, signed), home: gp(h, h.last5_margin, signed), awayN: a.last5_margin, homeN: h.last5_margin, better: "high" },
    { label: "Elo", away: show(a.elo, (n) => num(n, 0), NOT_LISTED), home: show(h.elo, (n) => num(n, 0), NOT_LISTED), awayN: a.elo, homeN: h.elo, better: "high" },
    { label: "Quarterback", away: qbCell(a), home: qbCell(h) },
    { label: "Rest days", away: a.rest_days ?? NOT_LISTED, home: h.rest_days ?? NOT_LISTED, note: "Rest days showed no proven effect in testing." },
    { label: "Head coach", away: a.coach ?? NOT_LISTED, home: h.coach ?? NOT_LISTED },
  ];

  const noGames = [a, h].filter((f) => f.points_for_pg === null).map((f) => f.team);

  return (
    <Section
      id="teams"
      title="Team comparison"
      note={`Form going into this game. The leader on each measure is brighter.${noGames.length ? ` ${noGames.join(" and ")}: no games played yet this season.` : ""}`}
    >
      <div className="mb-3 grid grid-cols-[1fr_1fr] items-center gap-4 sm:grid-cols-[1fr_168px_1fr]">
        <div className="flex items-center gap-2">
          <TeamLogo team={game.away} size={24} />
          <span className="text-sm font-semibold">{game.away.abbr}</span>
        </div>
        <span className="hidden sm:block" />
        <div className="flex items-center justify-end gap-2">
          <span className="text-sm font-semibold">{game.home.abbr}</span>
          <TeamLogo team={game.home} size={24} />
        </div>
      </div>
      <dl className="divide-y divide-border">
        {rows.map((r) => {
          const w = winner(r);
          return (
            <div key={r.label} className="grid grid-cols-2 items-baseline gap-x-4 py-2 sm:grid-cols-[1fr_168px_1fr]">
              <dt className="order-first col-span-2 text-xs text-subtle sm:order-none sm:col-span-1 sm:col-start-2 sm:row-start-1 sm:text-center">{r.label}</dt>
              <dd className={cx("text-sm sm:col-start-1 sm:row-start-1", w === "away" ? "font-semibold text-text" : w === "home" ? "text-text-2" : "text-text")}>{r.away}</dd>
              <dd className={cx("text-right text-sm sm:col-start-3 sm:row-start-1", w === "home" ? "font-semibold text-text" : w === "away" ? "text-text-2" : "text-text")}>{r.home}</dd>
              {r.note && <dd className="col-span-2 mt-1 text-[11px] text-subtle sm:col-span-3 sm:text-center">{r.note}</dd>}
            </div>
          );
        })}
      </dl>
    </Section>
  );
}
