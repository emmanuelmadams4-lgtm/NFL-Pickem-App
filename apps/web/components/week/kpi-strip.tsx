"use client";

import type { Week } from "@nflpi/shared";
import { isLocked, useNow } from "@/lib/clock";
import { cx } from "@/components/ui";
import { pctOr } from "@/lib/fmt";

/**
 * One unboxed strip at every width, cells divided by vertical hairlines (design.md § 7, § 8, § 11).
 * Phones: four numbers with one-word labels. Desktop: a sub-line per cell and a text summary on the right.
 * "Needs attention" is the board's filter, not a figure here.
 */
export function KpiStrip({ week }: { week: Week }) {
  const s = week.summary;
  const now = useNow();
  const open = week.games.filter((g) => !isLocked(g, now) && !g.my_pick).length;
  const hasLeader = s.league_leader_accuracy !== null && s.league_leader_accuracy !== undefined;

  const cells = [
    {
      label: "Games final",
      short: "Final",
      value: `${s.games_final}/${s.games_total}`,
      sub: `${s.games_remaining} remaining`,
    },
    {
      label: "My picks",
      short: "Picked",
      value: `${s.picks_made}/${s.games_total}`,
      sub: open > 0 ? `${open} still open to pick` : "No open games left to pick",
    },
    {
      label: "My accuracy, week",
      short: "Me",
      value: pctOr(s.my_accuracy),
      sub: `Season ${pctOr(s.season_my_accuracy)}`,
    },
    {
      label: "Model accuracy, week",
      short: "Model",
      value: pctOr(s.model_accuracy),
      sub: s.model_graded > 0 ? `Season ${pctOr(s.season_model_accuracy)}` : "No live picks graded",
      missing: s.model_graded === 0, // the reason is shown at every width, not only on desktop
    },
  ];

  const mine = s.picks_correct + s.picks_incorrect > 0 ? `Me: ${s.picks_correct} right, ${s.picks_incorrect} wrong this week.` : "No graded picks this week.";
  const model = s.model_graded > 0 ? `Model: ${s.model_correct} of ${s.model_graded} graded this week.` : "No live picks graded this week.";

  return (
    <section aria-label="Week summary" className="flex items-center gap-8">
      <dl className="grid min-w-0 flex-1 grid-cols-4 divide-x divide-border lg:flex lg:flex-none">
        {cells.map((c) => (
          <div key={c.label} className="flex min-w-0 flex-col px-2 text-center lg:px-6 lg:text-left lg:first:pl-0">
            <dt className="order-2 mt-0.5 truncate text-label text-subtle lg:order-none lg:mt-0">
              <span className="lg:hidden">{c.short}</span>
              <span className="hidden lg:inline">{c.label}</span>
            </dt>
            <dd className="num-display text-xl/7 font-semibold text-text lg:mt-1 lg:text-stat">{c.value}</dd>
            <dd className={cx("mt-0.5 text-label text-text-2", c.missing ? "order-3 lg:order-none" : "hidden lg:block")}>{c.sub}</dd>
          </div>
        ))}
      </dl>
      <p className="ml-auto hidden max-w-[44ch] text-right text-label text-text-2 lg:block">
        {mine} {model}
        {hasLeader && ` League leader: ${pctOr(s.league_leader_accuracy)} season accuracy you entered.`}
      </p>
    </section>
  );
}
