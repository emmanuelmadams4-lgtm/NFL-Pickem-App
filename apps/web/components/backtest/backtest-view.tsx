"use client";

import { useState } from "react";
import { ago, pct, type Backtest } from "@nflpi/shared";
import { useBacktest } from "@/lib/queries";
import { Card, Chip, ErrorState, Section, Segmented, Skeleton, cx } from "@/components/ui";
import { SeasonLines, MODEL_STYLE, type SeasonRow } from "@/components/charts/season-lines";
import { CalibrationChart } from "@/components/charts/calibration";
import { pctOr } from "@/lib/fmt";

const NAMES: Record<string, string> = { home: "Always-home", elo: "Elo only", logistic: "Stats model", market: "Betting market", blend: "Blend" };
const name = (k: string) => NAMES[k] ?? k;

interface Comparison {
  a: string;
  b: string;
  accuracy_diff: number;
  ci: [number, number];
  significant: boolean;
}
interface Ablation {
  feature: string;
  log_loss_without: number;
  log_loss_gain: number;
}
interface Split {
  model: string;
  picked_favorite: number;
  favorite_accuracy: number | null;
  picked_underdog: number;
  underdog_accuracy: number | null;
}

const signedPts = (x: number) => `${x < 0 ? "-" : "+"}${Math.abs(x * 100).toFixed(1)}`;
const feature = (f: string) =>
  f
    .split("_")
    .map((w, i) => (w === "qb" ? "QB" : i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");

/** "Stats model vs Betting market: -2.1 pts (95% CI -3.4 to -0.8). A real gap." */
function ComparisonText({ c }: { c: Comparison }) {
  return (
    <>
      <span className="font-medium text-text">
        {name(c.a)} vs {name(c.b)}:
      </span>{" "}
      <span className="num-display font-semibold text-text">{signedPts(c.accuracy_diff)} pts</span>{" "}
      <span className="text-text-2">
        (95% CI {signedPts(c.ci[0])} to {signedPts(c.ci[1])}).
      </span>{" "}
      <span className={c.significant ? "text-text" : "text-text-2"}>{c.significant ? "A real gap." : "Not a proven difference."}</span>
    </>
  );
}

function Headline({ data, comparisons }: { data: Backtest; comparisons: Comparison[] }) {
  const m = (k: string) => data.models.find((x) => x.model === k);
  const seasons = [...data.seasons].sort((a, b) => a - b);
  const parts = ["market", "logistic", "blend"]
    .map((k) => {
      const row = m(k);
      return row ? `${k === "logistic" ? "stats model" : k} ${pct(row.accuracy, 1)}` : null;
    })
    .filter(Boolean);
  const home = m("home");
  const key = comparisons.filter((c) => (c.a === "logistic" || c.a === "blend") && c.b === "market");

  return (
    <Card className="p-5 sm:p-6">
      <p className="text-xs font-medium text-subtle">What the backtest shows</p>
      <p className="mt-2 text-lg leading-snug font-semibold text-text sm:text-xl">
        Over {seasons[0]}-{seasons[seasons.length - 1]} ({data.games.toLocaleString()} games): {parts.join(", ")}.
      </p>
      {key.length > 0 && (
        <ul className="mt-3 space-y-1.5 text-sm">
          {key.map((c) => (
            <li key={`${c.a}-${c.b}`}>
              <ComparisonText c={c} />
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-xs text-subtle">
        Every model is scored on the same games, those with a betting line, always predicting before kickoff.
        {home ? ` Always picking the home team scores ${pct(home.accuracy, 1)}, the floor to beat.` : ""} Run {ago(data.created_at)}.
      </p>
    </Card>
  );
}

function ModelsTable({ data }: { data: Backtest }) {
  const best = {
    accuracy: Math.max(...data.models.map((x) => x.accuracy)),
    brier: Math.min(...data.models.map((x) => x.brier)),
    log_loss: Math.min(...data.models.map((x) => x.log_loss)),
  };
  const lead = (on: boolean) => (on ? "font-semibold text-text" : "text-text-2");
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-[11px] text-subtle">
          <th scope="col" className="py-1.5 pr-3 font-medium">Model</th>
          <th scope="col" className="py-1.5 pr-3 text-right font-medium">Accuracy</th>
          <th scope="col" className="hidden py-1.5 pr-3 text-right font-medium md:table-cell">95% CI</th>
          <th scope="col" className="py-1.5 pr-3 text-right font-medium">Brier</th>
          <th scope="col" className="py-1.5 pr-3 text-right font-medium">Log loss</th>
          <th scope="col" className="hidden py-1.5 text-right font-medium sm:table-cell">Games</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {data.models.map((r) => (
          <tr key={r.model}>
            <th scope="row" className="py-2 pr-3 text-left align-top font-normal">
              <span className="flex items-start gap-2">
                <span aria-hidden className="mt-1.5 h-0.5 w-3 shrink-0 rounded-full" style={{ background: MODEL_STYLE[r.model]?.color ?? "var(--muted)" }} />
                <span>
                  <span className="text-text">{r.label}</span>
                </span>
              </span>
            </th>
            <td className={cx("py-2 pr-3 text-right align-top", lead(r.accuracy === best.accuracy))}>
              {pct(r.accuracy, 1)}
              <span className="block text-[11px] font-normal text-subtle md:hidden">
                {pctOr(r.accuracy_ci[0], 1)} to {pctOr(r.accuracy_ci[1], 1)}
              </span>
            </td>
            <td className="hidden py-2 pr-3 text-right align-top text-text-2 md:table-cell">
              {pctOr(r.accuracy_ci[0], 1)} to {pctOr(r.accuracy_ci[1], 1)}
            </td>
            <td className={cx("py-2 pr-3 text-right align-top", lead(r.brier === best.brier))}>{r.brier.toFixed(4)}</td>
            <td className={cx("py-2 pr-3 text-right align-top", lead(r.log_loss === best.log_loss))}>{r.log_loss.toFixed(3)}</td>
            <td className="hidden py-2 text-right align-top text-text-2 sm:table-cell">{r.n.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Skeletons() {
  return (
    <div aria-busy="true" aria-label="Loading backtest" className="space-y-5">
      <Skeleton className="h-40 rounded-card" />
      <Skeleton className="h-64 rounded-card" />
      <Skeleton className="h-80 rounded-card" />
    </div>
  );
}

export function BacktestView() {
  const q = useBacktest();
  const data = q.data;
  const [calKey, setCalKey] = useState<"blend" | "logistic" | "market">("blend");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-title">Backtest</h1>
        <p className="mt-0.5 text-sm text-text-2">How each approach would have done on past seasons, with uncertainty.</p>
      </div>

      {q.isPending && <Skeletons />}
      {q.isError && !data && <ErrorState title="Could not load the backtest" error={q.error} onRetry={() => q.refetch()} />}

      {data && (() => {
        const comparisons = data.comparisons as unknown as Comparison[];
        const ablations = data.ablations as unknown as Ablation[];
        const bySeason = data.by_season as unknown as SeasonRow[];
        const splits = data.favorite_split as unknown as Split[];
        return (
          <>
            <Headline data={data} comparisons={comparisons} />

            <Section id="models" title="Models" note="Bold marks the best value in each column. Lower is better for Brier and log loss.">
              <ModelsTable data={data} />
            </Section>

            <Section id="comparisons" title="Head-to-head accuracy" note="Difference in accuracy on the same games, in percentage points, with a bootstrap 95% interval.">
              <ul className="divide-y divide-border">
                {comparisons.map((c) => (
                  <li key={`${c.a}-${c.b}`} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-2.5 text-sm first:pt-0 last:pb-0">
                    <span className="min-w-0 flex-1">
                      <ComparisonText c={c} />
                    </span>
                    <Chip>{c.significant ? "Real gap" : "Not proven"}</Chip>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-[11px] text-subtle">If the interval spans zero, the data cannot tell the two apart. That is a statement about the evidence, not proof they are equal.</p>
            </Section>

            {ablations.length > 0 && (
              <Section id="ablations" title="Does a feature earn its place?" note="Log loss with and without each feature, same games.">
                <ul className="space-y-2 text-sm">
                  {ablations.map((a) => (
                    <li key={a.feature}>
                      <span className="font-medium text-text">{feature(a.feature)}</span>{" "}
                      <span className="text-text-2">
                        {a.log_loss_gain >= 0 ? "improves" : "worsens"} log loss by{" "}
                        <span className="num-display font-semibold text-text">{Math.abs(a.log_loss_gain).toFixed(3)}</span> ({a.log_loss_without.toFixed(3)} without it).
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-[11px] text-subtle">These are small numbers. Treat them as a hint about value, not proof.</p>
              </Section>
            )}

            <Section id="by-season" title="Accuracy by season">
              {bySeason.length < 2 ? <p className="text-sm text-text-2">Not enough seasons to chart.</p> : <SeasonLines rows={bySeason} />}
            </Section>

            <Section id="favorites" title="Favorites and underdogs" note="Favorite means the side the betting line favors.">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] text-subtle">
                    <th scope="col" className="py-1.5 pr-3 font-medium">Model</th>
                    <th scope="col" className="py-1.5 pr-3 text-right font-medium">Picked favorite</th>
                    <th scope="col" className="py-1.5 text-right font-medium">Picked underdog</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {splits.map((s) => (
                    <tr key={s.model}>
                      <th scope="row" className="py-2 pr-3 text-left font-normal text-text">{name(s.model)}</th>
                      <td className="py-2 pr-3 text-right">
                        <span className="text-text">{pctOr(s.favorite_accuracy, 1)}</span>
                        <span className="block text-[11px] text-subtle">{s.picked_favorite.toLocaleString()} picks</span>
                      </td>
                      <td className="py-2 text-right">
                        <span className={s.picked_underdog > 0 ? "text-text" : "text-subtle"}>{pctOr(s.underdog_accuracy, 1)}</span>
                        <span className="block text-[11px] text-subtle">{s.picked_underdog.toLocaleString()} picks</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>

            <Section
              id="calibration"
              title="Calibration"
              note="Predicted versus observed win rate."
              action={
                <Segmented
                  label="Model"
                  value={calKey}
                  onChange={setCalKey}
                  options={[
                    { value: "blend", label: "Blend" },
                    { value: "logistic", label: "Stats" },
                    { value: "market", label: "Market" },
                  ]}
                />
              }
            >
              <CalibrationChart
                buckets={data.calibration[calKey] ?? []}
                color={calKey === "blend" ? "var(--series-model)" : calKey === "logistic" ? "var(--series-stats)" : "var(--series-market)"}
                name={calKey === "blend" ? "Blend" : calKey === "logistic" ? "Stats model" : "Betting market"}
              />
            </Section>
          </>
        );
      })()}
    </div>
  );
}
