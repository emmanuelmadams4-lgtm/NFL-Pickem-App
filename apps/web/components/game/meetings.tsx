"use client";

import type { GameDetail } from "@nflpi/shared";
import { Section, cx } from "@/components/ui";

export function Meetings({ game }: { game: GameDetail }) {
  return (
    <Section id="meetings" title="Recent meetings" note="Shown for context. Not used by the model.">
      {game.meetings.length === 0 ? (
        <p className="text-sm text-text-2">No earlier meetings found in the data.</p>
      ) : (
        <ul className="divide-y divide-border">
          {game.meetings.map((m) => {
            const awayWon = (m.away_score ?? 0) > (m.home_score ?? 0);
            const homeWon = (m.home_score ?? 0) > (m.away_score ?? 0);
            return (
              <li key={m.game_id} className="flex items-center justify-between gap-4 py-2 first:pt-0 last:pb-0">
                <span className="text-xs text-subtle">
                  {m.season}, Week {m.week}
                </span>
                <span className="text-sm text-text-2">
                  <span className={cx(awayWon && "font-semibold text-text")}>
                    {m.away_team} {m.away_score ?? "-"}
                  </span>
                  <span className="mx-2 text-subtle">at</span>
                  <span className={cx(homeWon && "font-semibold text-text")}>
                    {m.home_team} {m.home_score ?? "-"}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}
