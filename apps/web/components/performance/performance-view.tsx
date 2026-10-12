"use client";

import Link from "next/link";
import type { Performance, Tally } from "@nflpi/shared";
import { usePerformance, useMeta } from "@/lib/queries";
import { useSelection } from "@/lib/selection";
import { BigDash, EmptyState, ErrorState, PageHead, Section, Skeleton, cx } from "@/components/ui";
import { SeasonPicker } from "@/components/pickers";
import { ChevronRight } from "@/components/icons";
import { WeeklyBars } from "@/components/charts/weekly-bars";
import { CalibrationChart } from "@/components/charts/calibration";
import { Scorecard } from "@/components/performance/scorecard";
import { pctOr } from "@/lib/fmt";

/** One cell of the accuracy strip. Cells are divided by hairlines, not boxed (design.md § 7). */
function TallyCell({ testId, label, tally, color, empty, note }: { testId: string; label: string; tally: Tally; color: string; empty?: React.ReactNode; note?: string }) {
  const has = tally.total > 0;
  return (
    <div data-testid={testId} className="min-w-0 rounded-card border border-border bg-surface p-4 lg:p-5">
      <p className="flex items-center gap-2 text-sm font-medium text-text">
        <span aria-hidden className="h-2.5 w-2.5 rounded-[3px]" style={{ background: color }} />
        {label}
      </p>
      {has ? (
        <>
          <p className="font-display mt-2 text-[40px] leading-10 text-text">{pctOr(tally.accuracy, 1)}</p>
          <p className="mt-1 text-label text-text-2">
            95% CI {pctOr(tally.ci_low, 1)} to {pctOr(tally.ci_high, 1)}
          </p>
          <p className="text-label text-text-2">
            {tally.correct} of {tally.total} correct
          </p>
          {note && <p className="mt-1 text-label text-subtle">{note}</p>}
        </>
      ) : (
        <>
          <p className="font-display mt-2 text-[40px] leading-10 text-subtle">
            <BigDash />
          </p>
          <p className="mt-1 text-label text-text-2">{empty ?? "No graded games yet"}</p>
        </>
      )}
    </div>
  );
}

/** Backfilled predictions were computed after kickoff, so they sit apart from the live headline (PRODUCT.md). */
function BackfillRecord({ tally }: { tally: Tally }) {
  return (
    <div data-testid="tally-model-backfill" className="mt-3 rounded-card border border-dashed border-border-strong p-5">
      <p className="flex items-center gap-2 text-sm font-medium text-text">
        <span aria-hidden className="h-2.5 w-2.5 rounded-[3px] border-2" style={{ borderColor: "var(--series-model)" }} />
        Model, backfilled
      </p>
      {tally.total > 0 ? (
        <p className="mt-1 text-sm text-text-2">
          <span className="num-display font-semibold text-text">{pctOr(tally.accuracy, 1)}</span>, 95% CI {pctOr(tally.ci_low, 1)} to {pctOr(tally.ci_high, 1)}, {tally.correct} of {tally.total} correct
        </p>
      ) : (
        <p className="mt-1 text-sm text-text-2">No backfilled games this season</p>
      )}
      <p className="mt-1 text-label text-subtle">Computed after kickoff from pre-game inputs. Not part of the live record above.</p>
    </div>
  );
}

function WeeklyTable({ perf }: { perf: Performance }) {
  const rows = perf.weeks;
  const cell = (c: number, t: number, note?: string) => (
    <td className="py-2 pr-2 text-right align-top">
      {t > 0 ? (
        <>
          <span className="text-text">{Math.round((c / t) * 100)}%</span>
          <span className="block text-[11px] text-subtle">
            {c}/{t}
          </span>
        </>
      ) : (
        <span className="text-subtle">–</span>
      )}
      {note && <span className="block text-[11px] text-subtle">{note}</span>}
    </td>
  );
  return (
    <table className="w-full text-sm">
      <caption className="caption-bottom pt-3 text-left text-label text-subtle">– means no live graded games that week for that column (the Model column shows backfilled counts separately).</caption>
      <thead>
        <tr className="border-b border-border text-[11px] text-subtle">
          <th scope="col" className="py-1.5 pr-2 text-left font-medium">Week</th>
          <th scope="col" className="hidden py-1.5 pr-2 text-right font-medium sm:table-cell">Final games</th>
          <th scope="col" className="py-1.5 pr-2 text-right font-medium">Me</th>
          <th scope="col" className="py-1.5 pr-2 text-right font-medium">Model</th>
          <th scope="col" className="py-1.5 pr-2 text-right font-medium">Market</th>
          <th scope="col" className="py-1.5 text-right font-medium">Home team</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border">
        {rows.map((w) => (
          <tr key={w.week}>
            <th scope="row" className="py-2 pr-2 text-left align-top font-medium text-text">{w.week}</th>
            <td className="hidden py-2 pr-2 text-right align-top text-text-2 sm:table-cell">{w.games_final}</td>
            {cell(w.my_correct, w.my_total)}
            {cell(w.model_live_correct, w.model_live_total, w.model_backfill_total > 0 ? `${w.model_backfill_correct}/${w.model_backfill_total} backfilled` : undefined)}
            {cell(w.market_correct, w.market_total)}
            <td className="py-2 text-right align-top">
              {w.home_total > 0 ? (
                <>
                  <span className="text-text">{Math.round((w.home_correct / w.home_total) * 100)}%</span>
                  <span className="block text-[11px] text-subtle">
                    {w.home_correct}/{w.home_total}
                  </span>
                </>
              ) : (
                <span className="text-subtle">–</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Skeletons() {
  return (
    <div aria-busy="true" aria-label="Loading performance" className="space-y-5">
      <Skeleton className="h-28 rounded-card" />
      <Skeleton className="h-80 rounded-card" />
      <Skeleton className="h-96 rounded-card" />
    </div>
  );
}

export function PerformanceView() {
  const { season } = useSelection();
  const meta = useMeta().data;
  const q = usePerformance(season);
  const perf = q.data;
  const leader = perf?.league_leader_accuracy ?? meta?.league_leader_accuracy ?? null;

  return (
    <div className="space-y-6">
      <PageHead kicker="Your record" title="Results" sub={`${season} season. Finished games only.`} aside={<SeasonPicker className="inline-flex lg:hidden" />} />

      {q.isPending && <Skeletons />}
      {q.isError && !perf && <ErrorState title="Could not load performance" error={q.error} onRetry={() => q.refetch()} />}

      {perf && (
        <>
          <Scorecard season={season} />
          {perf.auto.total > 0 && <p className="text-label text-text-2">Picked for you by the model: {perf.auto.correct} of {perf.auto.total} right</p>}
          {perf.model.total === 0 && perf.model_backfill.total === 0 && perf.me.total === 0 ? (
            <EmptyState title={`No finished games for ${season} yet`} hint="Accuracy appears here once games are final." />
          ) : (
            <>
              <section aria-label="Accuracy summary">
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                  <TallyCell
                    testId="tally-me"
                    label="Me"
                    tally={perf.me}
                    color="var(--series-me)"
                    empty={
                      <>
                        Make picks on the <Link href="/" className="text-accent-text underline underline-offset-2">Week board</Link> to track your accuracy.
                      </>
                    }
                  />
                  <TallyCell testId="tally-model-live" label="Model, live picks" tally={perf.model} color="var(--series-model)" empty="No graded live picks yet" />
                  <TallyCell testId="tally-market" label="Market" tally={perf.market} color="var(--series-market)" note="Favorite by the betting line" />
                  <TallyCell testId="tally-home" label="Home team" tally={perf.home} color="var(--series-home)" note="Always pick the home team" />
                </div>
                <BackfillRecord tally={perf.model_backfill} />
                <p className="mt-3 text-label text-subtle">Intervals are 95% confidence; small samples are wide on purpose.</p>
              </section>

              <Section id="weekly" title="Weekly accuracy" note="Share of finished games called correctly each week.">
                {perf.weeks.length === 0 ? (
                  <p className="text-sm text-text-2">No finished weeks yet.</p>
                ) : (
                  <div className="grid gap-8 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
                    <WeeklyBars weeks={perf.weeks} leader={leader} />
                    <WeeklyTable perf={perf} />
                  </div>
                )}
                {perf.me.total === 0 && <p className="mt-4 text-xs text-subtle">Your bars appear once you have graded picks.</p>}
              </Section>

              <Section id="calibration" title="Calibration" note="When the model says 70%, do those teams win about 70% of the time?">
                <CalibrationChart buckets={perf.calibration} backfill={perf.calibration_backfill} color="var(--series-model)" name="Model, live" backfillName="Model, backfilled" leader={null} />
                {leader !== null && (
                  <p className="mt-3 text-xs text-text-2">
                    League leader reference: <span className={cx("font-medium text-text")}>{pctOr(leader, 1)}</span> season accuracy (shown as a line on the weekly chart).
                  </p>
                )}
              </Section>
            </>
          )}
          <Link href="/backtest/" className="flex items-center justify-between gap-4 rounded-card border border-border bg-surface p-5 hover:border-border-strong">
            <span>
              <span className="block text-sm font-semibold text-text">Backtest</span>
              <span className="block text-xs text-text-2">How the model, the market and simpler baselines did over past seasons.</span>
            </span>
            <ChevronRight size={20} className="shrink-0 text-text-2" />
          </Link>
        </>
      )}
    </div>
  );
}
