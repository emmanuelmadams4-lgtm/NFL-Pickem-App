"use client";

import { useState } from "react";
import { ago, type GameDetail, type Injury, type Team } from "@nflpi/shared";
import { Button, Chip, Section, type ChipTone } from "@/components/ui";
import { TeamLogo } from "@/components/team";

function statusTone(status: string | null): ChipTone | null {
  switch ((status ?? "").toLowerCase()) {
    case "out":
      return "bad";
    case "doubtful":
      return "warn";
    case "questionable":
      return "warn-soft";
    default:
      return null;
  }
}

const COLLAPSED = 8;

function TeamInjuries({ team, rows }: { team: Team; rows: Injury[] }) {
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, COLLAPSED);
  const out = rows.filter((r) => (r.report_status ?? "").toLowerCase() === "out").length;
  const dq = rows.filter((r) => ["doubtful", "questionable"].includes((r.report_status ?? "").toLowerCase())).length;

  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center gap-2">
        <TeamLogo team={team} size={20} />
        <h3 className="text-sm font-semibold">{team.name}</h3>
        <span className="text-xs text-subtle">
          {rows.length} listed{out > 0 ? `, ${out} out` : ""}
          {dq > 0 ? `, ${dq} doubtful or questionable` : ""}
        </span>
      </div>
      {rows.length === 0 ? (
        <p className="rounded-ctl border border-dashed border-border px-3 py-4 text-sm text-text-2">No injury report entries</p>
      ) : (
        <>
          <ul className="divide-y divide-border">
            {shown.map((r) => {
              const tone = statusTone(r.report_status);
              return (
                <li key={`${r.player}-${r.position}`} className="flex items-start justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-text">
                      {r.player} {r.position && <span className="text-xs text-subtle">{r.position}</span>}
                    </p>
                    <p className="truncate text-xs text-text-2">{[r.injury, r.practice_status].filter(Boolean).join(", ") || "No details"}</p>
                  </div>
                  {r.report_status && (tone ? <Chip tone={tone}>{r.report_status}</Chip> : <span className="shrink-0 text-xs text-text-2">{r.report_status}</span>)}
                </li>
              );
            })}
          </ul>
          {rows.length > COLLAPSED && (
            <Button variant="ghost" size="sm" className="mt-1 -ml-3" onClick={() => setAll((v) => !v)} aria-expanded={all}>
              {all ? "Show fewer" : `Show all ${rows.length}`}
            </Button>
          )}
        </>
      )}
    </div>
  );
}

export function Injuries({ game }: { game: GameDetail }) {
  const latest = game.injuries.reduce<string | null>((m, r) => (!m || r.observed_at > m ? r.observed_at : m), null);
  return (
    <Section id="injuries" title="Injuries" note={latest ? `Report as of ${ago(latest)}.` : "Official injury report entries for both teams."}>
      {game.injuries.length === 0 ? (
        <p className="rounded-ctl border border-dashed border-border px-3 py-6 text-center text-sm text-text-2">No injury report entries</p>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <TeamInjuries team={game.away} rows={game.injuries.filter((r) => r.team === game.away.abbr)} />
          <TeamInjuries team={game.home} rows={game.injuries.filter((r) => r.team === game.home.abbr)} />
        </div>
      )}
    </Section>
  );
}
