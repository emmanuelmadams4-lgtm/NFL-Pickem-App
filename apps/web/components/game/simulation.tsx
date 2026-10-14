"use client";

import { pct, type GameDetail } from "@nflpi/shared";
import { Section } from "@/components/ui";

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="num-display mt-0.5 text-lg font-semibold text-text">{children}</dd>
    </div>
  );
}

function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

function spreadText(value: number): string {
  if (value === 0) return "Pick'em";
  return `${value > 0 ? "+" : ""}${value.toFixed(Number.isInteger(value) ? 0 : 1)}`;
}

export function SimulationSection({ game }: { game: GameDetail }) {
  const sim = game.prediction?.simulation;

  return (
    <Section id="simulator" title="Score simulator" note={sim?.label}>
      {!sim ? (
        <p className="pt-4 text-sm text-text-2">No simulation for this game yet.</p>
      ) : (
        <div className="space-y-6 pt-4">
          <p className="text-sm text-text-2">Shown only: not a pick, and it does not change the pick above.</p>

          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
            <Fact label="Average score">
              <span className="block text-sm font-medium text-text-2">{game.away.abbr} {sim.away_points.toFixed(1)}</span>
              <span className="block text-sm font-medium text-text-2">{game.home.abbr} {sim.home_points.toFixed(1)}</span>
            </Fact>
            <Fact label="Home margin">
              {signed(sim.expected_margin)}
              <span className="block text-xs font-normal text-subtle">
                80% of runs between {signed(sim.margin_80[0])} and {signed(sim.margin_80[1])}
              </span>
            </Fact>
            <Fact label="Total points">
              {sim.expected_total.toFixed(1)}
              <span className="block text-xs font-normal text-subtle">
                80% of runs between {sim.total_80[0].toFixed(1)} and {sim.total_80[1].toFixed(1)}
              </span>
            </Fact>
          </dl>

          <div>
            {sim.home_spread === null ? (
              <p className="text-sm text-text-2">No spread yet.</p>
            ) : (
              <>
                <h3 className="mb-3 text-sm font-medium text-text">
                  {game.home.abbr} {spreadText(sim.home_spread)}
                </h3>
                <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
                  <Fact label={`${game.home.abbr} covers`}>{pct(sim.home_cover, 0)}</Fact>
                  <Fact label={`${game.away.abbr} covers`}>{pct(sim.away_cover, 0)}</Fact>
                  <Fact label="Push">{pct(sim.spread_push, 0)}</Fact>
                </dl>
              </>
            )}
          </div>

          <div>
            {sim.total === null ? (
              <p className="text-sm text-text-2">No total yet.</p>
            ) : (
              <>
                <h3 className="mb-3 text-sm font-medium text-text">Over/under {sim.total}</h3>
                <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
                  <Fact label="Over">{pct(sim.over, 0)}</Fact>
                  <Fact label="Under">{pct(sim.under, 0)}</Fact>
                  <Fact label="Push">{pct(sim.total_push, 0)}</Fact>
                </dl>
              </>
            )}
          </div>

          <p className="text-xs text-subtle">Based on {sim.n_simulations.toLocaleString("en-US")} simulated games.</p>
        </div>
      )}
    </Section>
  );
}
