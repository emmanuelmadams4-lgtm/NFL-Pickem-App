"use client";

import { ago, moneyline, pct, type GameDetail, type Market } from "@nflpi/shared";
import { Section } from "@/components/ui";
import { TimeLine } from "@/components/charts/time-line";
import { dateTime } from "@/lib/fmt";

/** spread_line > 0 means the home team is favored by that many points. */
function spreadText(m: Market, game: GameDetail): string {
  if (m.spread_line === null || m.spread_line === undefined) return "-";
  if (m.spread_line === 0) return "Pick'em";
  const fav = m.spread_line > 0 ? game.home.abbr : game.away.abbr;
  return `${fav} -${Math.abs(m.spread_line)}`;
}

const KIND: Record<string, string> = { latest: "Latest", closing: "Closing", opening: "Opening" };

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="num-display mt-0.5 text-lg font-semibold text-text">{children}</dd>
    </div>
  );
}

export function MarketSection({ game }: { game: GameDetail }) {
  const history = [...game.market_history].sort((a, b) => a.observed_at.localeCompare(b.observed_at));
  const latest = history[history.length - 1];
  const chart = history.filter((m) => m.home_prob !== null).map((m) => ({ t: new Date(m.observed_at).getTime(), v: m.home_prob as number }));

  return (
    <Section id="market" title="Market" note="Betting lines from nflverse. Shown to compare, and blended into the final model when a line exists.">
      {!latest ? (
        <p className="text-sm text-text-2">No line yet. The market view appears once a line is posted.</p>
      ) : (
        <div className="space-y-6">
          <div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
              <Fact label="Moneyline">
                <span className="block text-sm font-medium text-text-2">{game.away.abbr} {moneyline(latest.away_moneyline)}</span>
                <span className="block text-sm font-medium text-text-2">{game.home.abbr} {moneyline(latest.home_moneyline)}</span>
              </Fact>
              <Fact label="Spread">{spreadText(latest, game)}</Fact>
              <Fact label="Total">{latest.total_line ?? "-"}</Fact>
              <Fact label="Implied, no-vig">
                {latest.home_prob === null ? (
                  "-"
                ) : (
                  <>
                    <span className="block text-sm font-medium text-text-2">{game.home.abbr} {pct(latest.home_prob, 1)}</span>
                    <span className="block text-sm font-medium text-text-2">{game.away.abbr} {pct(1 - latest.home_prob, 1)}</span>
                  </>
                )}
              </Fact>
            </dl>
            <p className="mt-3 text-[11px] text-subtle">
              {KIND[latest.kind] ?? latest.kind} line from {latest.source}, observed {ago(latest.observed_at)}.
            </p>
          </div>

          {chart.length >= 2 && (
            <div>
              <h3 className="mb-2 text-xs font-medium text-text">{game.home.abbr} no-vig win probability over time</h3>
              <TimeLine data={chart} name={`${game.home.abbr} no-vig`} color="var(--series-market)" label={`Line chart of ${game.home.abbr} no-vig win probability across ${chart.length} line observations`} />
            </div>
          )}

          <div>
            <h3 className="mb-2 text-xs font-medium text-text">Line history</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] font-medium text-subtle">
                  <th scope="col" className="py-1.5 pr-3 font-medium">Time</th>
                  <th scope="col" className="py-1.5 pr-3 font-medium">Home ML</th>
                  <th scope="col" className="hidden py-1.5 pr-3 font-medium sm:table-cell">Away ML</th>
                  <th scope="col" className="py-1.5 pr-3 font-medium">Spread</th>
                  <th scope="col" className="hidden py-1.5 pr-3 font-medium sm:table-cell">Total</th>
                  <th scope="col" className="py-1.5 text-right font-medium">Home no-vig</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[...history].reverse().map((m) => (
                  <tr key={m.observed_at + m.kind}>
                    <td className="py-1.5 pr-3 text-text-2">
                      {dateTime(m.observed_at)}
                      <span className="ml-2 text-[11px] text-subtle">{KIND[m.kind] ?? m.kind}</span>
                    </td>
                    <td className="py-1.5 pr-3">{moneyline(m.home_moneyline)}</td>
                    <td className="hidden py-1.5 pr-3 sm:table-cell">{moneyline(m.away_moneyline)}</td>
                    <td className="py-1.5 pr-3">{spreadText(m, game)}</td>
                    <td className="hidden py-1.5 pr-3 sm:table-cell">{m.total_line ?? "-"}</td>
                    <td className="py-1.5 text-right">{m.home_prob === null ? "-" : pct(m.home_prob, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {history.length === 1 && <p className="mt-2 text-[11px] text-subtle">One observation so far. The chart appears once the line moves.</p>}
          </div>
        </div>
      )}
    </Section>
  );
}
