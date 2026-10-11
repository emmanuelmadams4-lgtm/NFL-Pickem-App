"use client";

import type { Week } from "@nflpi/shared";
import { Card, cx } from "@/components/ui";
import { pctOr } from "@/lib/fmt";

function Tile({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={cx("flex min-w-0 flex-col justify-between p-4", className)}>
      <p className="text-xs text-subtle">{label}</p>
      <div className="mt-2">{children}</div>
    </Card>
  );
}

function Big({ children }: { children: React.ReactNode }) {
  return <span className="num-display text-[26px] leading-8 font-semibold text-text">{children}</span>;
}

function AccuracyTile({ label, week, season, detail }: { label: string; week: number | null; season: number | null; detail: string }) {
  return (
    <Tile label={label}>
      <div className="flex items-baseline gap-4">
        <div>
          <Big>{pctOr(week)}</Big>
          <span className="ml-1.5 text-xs text-subtle">week</span>
        </div>
        <div>
          <span className="num-display text-lg font-semibold text-text-2">{pctOr(season)}</span>
          <span className="ml-1.5 text-xs text-subtle">season</span>
        </div>
      </div>
      <p className="mt-1 text-xs text-text-2">{detail}</p>
    </Tile>
  );
}

/** Phones: one compact row of the four numbers that matter at a glance. Season detail lives under Results. */
function PhoneSummary({ week }: { week: Week }) {
  const s = week.summary;
  const cells = [
    { label: "Final", value: `${s.games_final}/${s.games_total}` },
    { label: "Picked", value: `${s.picks_made}/${s.games_total}` },
    { label: "Me, week", value: pctOr(s.my_accuracy) },
    { label: "Model, week", value: pctOr(s.model_accuracy) },
  ];
  return (
    <Card className="grid grid-cols-4 divide-x divide-border py-3 lg:hidden">
      {cells.map((c) => (
        <div key={c.label} className="min-w-0 px-2 text-center">
          <p className="num-display text-lg leading-6 font-semibold text-text">{c.value}</p>
          <p className="mt-0.5 truncate text-[11px] text-subtle">{c.label}</p>
        </div>
      ))}
    </Card>
  );
}

export function KpiStrip({ week }: { week: Week }) {
  const s = week.summary;
  const open = week.games.filter((g) => !g.locked && !g.my_pick).length;
  const hasLeader = s.league_leader_accuracy !== null && s.league_leader_accuracy !== undefined;

  return (
    <>
      <PhoneSummary week={week} />
      <div className={cx("hidden gap-3 lg:grid lg:grid-cols-3", hasLeader ? "xl:grid-cols-6" : "xl:grid-cols-5")}>
      <Tile label="Games final">
        <Big>
          {s.games_final} <span className="text-text-2">/ {s.games_total}</span>
        </Big>
        <p className="mt-1 text-xs text-text-2">{s.games_remaining} remaining</p>
      </Tile>
      <Tile label="My picks">
        <Big>
          {s.picks_made} <span className="text-text-2">/ {s.games_total}</span>
        </Big>
        <p className="mt-1 text-xs text-text-2">{open > 0 ? `${open} still open to pick` : "No open games left to pick"}</p>
      </Tile>
      <AccuracyTile
        label="My accuracy"
        week={s.my_accuracy}
        season={s.season_my_accuracy}
        detail={s.picks_correct + s.picks_incorrect > 0 ? `${s.picks_correct} right, ${s.picks_incorrect} wrong this week` : "No graded picks this week"}
      />
      <AccuracyTile
        label="Model accuracy"
        week={s.model_accuracy}
        season={s.season_model_accuracy}
        detail={s.model_graded > 0 ? `${s.model_correct} of ${s.model_graded} graded this week` : "No graded games this week"}
      />
      {hasLeader && (
        <Tile label="League leader">
          <Big>{pctOr(s.league_leader_accuracy)}</Big>
          <p className="mt-1 text-xs text-text-2">Season accuracy you entered</p>
        </Tile>
      )}
      <Tile label="Needs attention">
        <Big>{s.attention}</Big>
        <p className="mt-1 text-xs text-text-2">High uncertainty or upset flags</p>
      </Tile>
      </div>
    </>
  );
}
