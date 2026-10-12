"use client";

import { Fragment, useMemo, useState } from "react";
import Link from "next/link";
import { SORTS, ago, kickoffDay, needsAttention, sortGames, type SortKey, type GameSummary } from "@nflpi/shared";
import { useWeek } from "@/lib/queries";
import { useSelection } from "@/lib/selection";
import { safeGet, safeSet } from "@/lib/fmt";
import { EmptyState, ErrorState, SelectField, Segmented, Skeleton, cx } from "@/components/ui";
import { describeStale, feedsModel, staleList } from "@/components/freshness";
import { KpiStrip } from "@/components/week/kpi-strip";
import { WeekPicker } from "@/components/pickers";
import { InstallHint } from "@/components/pwa";
import { GameRow, ROW_GRID } from "@/components/week/game-row";

const SORT_KEY = "nflpi_sort";
const SCOPE_KEY = "nflpi_scope";
type Scope = "all" | "open";

function initialSort(): SortKey {
  const saved = safeGet(SORT_KEY);
  return SORTS.some((s) => s.key === saved) ? (saved as SortKey) : "kickoff";
}

function BoardSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading week" className="space-y-4">
      <div className="grid grid-cols-4 divide-x divide-border lg:flex">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="px-2 lg:px-6 lg:first:pl-0">
            <Skeleton className="mx-auto h-12 w-14 lg:mx-0 lg:h-[72px] lg:w-32" />
          </div>
        ))}
      </div>
      <div className="space-y-3 lg:space-y-0 lg:divide-y lg:divide-border lg:rounded-card lg:border lg:border-border lg:bg-surface">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="rounded-card border border-border bg-surface p-4 lg:rounded-none lg:border-0">
            <div className="flex items-center gap-4">
              <Skeleton className="h-9 w-14" />
              <Skeleton className="h-10 w-44" />
              <Skeleton className="hidden h-10 w-40 lg:block" />
              <Skeleton className="ml-auto hidden h-8 w-36 lg:block" />
            </div>
            <Skeleton className="mt-3 h-12 w-full lg:hidden" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function WeekBoard() {
  const { season, week } = useSelection();
  const q = useWeek(season, week);
  const [sort, setSortState] = useState<SortKey>(initialSort);
  const [onlyAttention, setOnlyAttention] = useState(false);
  const [scope, setScopeState] = useState<Scope>(() => (safeGet(SCOPE_KEY) === "open" ? "open" : "all"));
  const setScope = (v: Scope) => {
    setScopeState(v);
    safeSet(SCOPE_KEY, v);
  };

  const setSort = (k: SortKey) => {
    setSortState(k);
    safeSet(SORT_KEY, k);
  };

  const data = q.data;
  const games = useMemo(() => {
    if (!data) return [];
    let base = scope === "open" ? data.games.filter((g) => g.status === "scheduled" && !g.locked) : data.games;
    if (onlyAttention) base = base.filter(needsAttention);
    return sortGames(base, sort);
  }, [data, sort, onlyAttention, scope]);

  const groups = useMemo(() => {
    if (sort !== "kickoff") return [{ day: "", games }];
    const out: { day: string; games: GameSummary[] }[] = [];
    for (const g of games) {
      const day = kickoffDay(g.kickoff_utc);
      const last = out[out.length - 1];
      if (last && last.day === day) last.games.push(g);
      else out.push({ day, games: [g] });
    }
    return out;
  }, [games, sort]);

  // Loud only for what can change a pick: stale model inputs. Weather is context; Settings notes it.
  const stale = staleList(data?.freshness).filter(feedsModel);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-title">Week {week}</h1>
          <p className="mt-0.5 text-sm text-text-2">
            {season} season{data ? `, ${data.summary.games_total} games` : ""}
          </p>
        </div>
        {data && (
          <p className="text-xs text-subtle">
            Updated {ago(data.generated_at)}
            {q.isFetching && !q.isPending ? ", refreshing" : ""}
          </p>
        )}
      </div>

      <WeekPicker className="lg:hidden" />
      <InstallHint />

      {q.isPending && <BoardSkeleton />}
      {q.isError && !data && <ErrorState title="Could not load this week" error={q.error} onRetry={() => q.refetch()} />}

      {data && (
        <>
          {stale.length > 0 && (
            <div role="note" className="rounded-ctl border border-warn/40 bg-warn/10 px-4 py-2.5 text-sm text-text-2">
              <span className="font-semibold text-warn">Stale data: {stale.map(describeStale).join(", ")}.</span>{" "}
              <span className="hidden sm:inline">Anything that depends on {stale.length === 1 ? "it" : "them"} may be missing or out of date.</span>
              {stale.some((s) => s.last_error) && (
                <span className="hidden sm:inline"> Last error: {stale.filter((s) => s.last_error).map((s) => `${s.dataset} ${s.last_error}`).join("; ")}.</span>
              )}{" "}
              <Link href="/settings/" className="text-accent underline underline-offset-2">
                See data sources
              </Link>
            </div>
          )}

          <KpiStrip week={data} />

          {data.games.length === 0 ? (
            <EmptyState title={`No games scheduled for Week ${week}`} hint={`There are no ${season} games in this week. Pick another week or season above.`} />
          ) : (
            <section aria-label="Games">
              <div className="mb-3 grid gap-2 lg:mb-2 lg:flex lg:flex-wrap lg:items-center lg:justify-between lg:gap-x-3">
                <SelectField label="Sort by" grow className="flex lg:inline-flex" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
                  {SORTS.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.label}
                    </option>
                  ))}
                </SelectField>
                <div className="flex flex-wrap items-center gap-2 lg:gap-3">
                  <Segmented
                    label="Games shown"
                    value={scope}
                    onChange={setScope}
                    options={[
                      { value: "all", label: "All games" },
                      { value: "open", label: "Open to pick" },
                    ]}
                  />
                  <button
                    type="button"
                    aria-pressed={onlyAttention}
                    onClick={() => setOnlyAttention((v) => !v)}
                    className={cx(
                      "h-10 rounded-ctl border px-3 text-sm font-medium transition-colors lg:h-8 lg:text-xs",
                      onlyAttention ? "border-warn/50 bg-warn/12 text-warn" : "border-border bg-elevated text-text-2 hover:border-border-strong hover:text-text",
                    )}
                  >
                    <span className="lg:hidden">Attention ({data.summary.attention})</span>
                    <span className="hidden lg:inline">Needs attention only ({data.summary.attention})</span>
                  </button>
                  <span className="hidden text-xs text-subtle lg:inline" aria-live="polite">
                    {games.length} of {data.games.length} games
                  </span>
                </div>
              </div>

              <div className="lg:rounded-card lg:border lg:border-border lg:bg-surface">
                <div className={cx("hidden items-center gap-x-4 border-b border-border px-4 py-2 text-[11px] font-medium text-subtle lg:grid", ROW_GRID)}>
                  <span>Kickoff</span>
                  <span>Matchup</span>
                  <span>Model pick</span>
                  <span>Uncertainty</span>
                  <span>Market</span>
                  <span>Alerts</span>
                  <span>My pick</span>
                  <span>Result</span>
                </div>
                {games.length === 0 ? (
                  <p className="rounded-card border border-border bg-surface px-4 py-10 text-center text-sm text-text-2 lg:border-0">{scope === "open" ? "No games are open to pick in this week." : "No games need attention in this week."}</p>
                ) : (
                  <ul className="space-y-3 lg:space-y-0 lg:divide-y lg:divide-border">
                    {groups.map((grp) => (
                      <Fragment key={grp.day || "all"}>
                        {grp.day && (
                          <li className="px-1 pt-3 pb-0 text-xs font-medium text-text-2 first:pt-0 lg:bg-elevated/50 lg:px-4 lg:py-1.5">
                            {grp.day}
                            <span className="ml-2 text-subtle">{grp.games.length} {grp.games.length === 1 ? "game" : "games"}</span>
                          </li>
                        )}
                        {grp.games.map((g) => (
                          <GameRow key={g.game_id} game={g} />
                        ))}
                      </Fragment>
                    ))}
                  </ul>
                )}
              </div>
              <p className="mt-2 text-xs text-subtle">Select a game for the full matchup. Picks lock at kickoff.</p>
            </section>
          )}
        </>
      )}
    </div>
  );
}
