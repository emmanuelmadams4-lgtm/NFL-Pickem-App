"use client";

import { Fragment, useMemo, useState } from "react";
import Link from "next/link";
import { SORTS, ago, kickoffDay, needsAttention, sortGames, type SortKey, type GameSummary } from "@nflpi/shared";
import { useWeek } from "@/lib/queries";
import { useSelection } from "@/lib/selection";
import { isLocked, useNow } from "@/lib/clock";
import { safeGet, safeSet } from "@/lib/fmt";
import { EmptyState, ErrorState, PageHead, SelectField, Skeleton, cx } from "@/components/ui";
import { describeStale, feedsModel, staleList } from "@/components/freshness";
import { KpiStrip } from "@/components/week/kpi-strip";
import { WeekPicker } from "@/components/pickers";
import { InstallHint } from "@/components/pwa";
import { GameCard } from "@/components/week/game-card";

const SORT_KEY = "nflpi_sort";
const SCOPE_KEY = "nflpi_scope";
type Scope = "all" | "open";
const SCOPES: { value: Scope; label: string }[] = [
  { value: "all", label: "All games" },
  { value: "open", label: "Open to pick" },
];

/** A filter chip (design.md § 0): a pill, lime when selected (amber for the attention filter). */
const chipClass = (on: boolean, onTone = "border-transparent bg-accent text-accent-ink") =>
  cx(
    "h-10 shrink-0 rounded-full border px-3.5 text-sm font-medium whitespace-nowrap transition-colors lg:h-9",
    on ? onTone : "border-border bg-elevated text-text-2 hover:border-border-strong hover:text-text",
  );

function initialSort(): SortKey {
  const saved = safeGet(SORT_KEY);
  return SORTS.some((s) => s.key === saved) ? (saved as SortKey) : "kickoff";
}

function BoardSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading week" className="space-y-4">
      <Skeleton className="h-24 rounded-card" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-[380px] rounded-card" />
        ))}
      </div>
    </div>
  );
}

export function WeekBoard() {
  const { season, week, qs } = useSelection();
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
  const pointsCount = data?.games.filter((g) => g.sheet.my_points !== null).length ?? 0;
  const now = useNow();
  const games = useMemo(() => {
    if (!data) return [];
    let base = scope === "open" ? data.games.filter((g) => g.status === "scheduled" && !isLocked(g, now)) : data.games;
    if (onlyAttention) base = base.filter(needsAttention);
    return sortGames(base, sort);
  }, [data, sort, onlyAttention, scope, now]);

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

  // The one lime card: the next game still open to pick (design.md § 0: at most one highlight per board).
  const nextId = useMemo(() => {
    const open = (data?.games ?? []).filter((g) => g.status === "scheduled" && !g.time_tbd && !isLocked(g, now));
    return open.sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc))[0]?.game_id ?? null;
  }, [data, now]);

  // Loud only for what can change a pick: stale model inputs. Weather is context; Settings notes it.
  const stale = staleList(data?.freshness).filter(feedsModel);

  return (
    <div className="space-y-5">
      <PageHead
        kicker="Picks"
        title={`Week ${week}`}
        sub={`${season} season${data ? `, ${data.summary.games_total} games` : ""}`}
        aside={
          data && (
            <p className="text-xs text-subtle">
              Updated {ago(data.generated_at)}
              {q.isFetching && !q.isPending ? ", refreshing" : ""}
            </p>
          )
        }
      />

      {/* Filter chips directly under the title, before any summary (design.md § 0); one scrolling row on the phone. */}
      <div className="flex flex-wrap items-center gap-3">
      <div data-testid="filter-chips" className="no-scrollbar -mx-4 flex min-w-0 items-center gap-2 overflow-x-auto px-4 lg:mx-0 lg:flex-wrap lg:px-0">
        <div role="group" aria-label="Games shown" className="flex shrink-0 gap-2">
          {SCOPES.map((o) => (
            <button key={o.value} type="button" aria-pressed={scope === o.value} onClick={() => setScope(o.value)} className={chipClass(scope === o.value)}>
              {o.label}
            </button>
          ))}
        </div>
        {data && (
          <button
            type="button"
            aria-pressed={onlyAttention}
            onClick={() => setOnlyAttention((v) => !v)}
            className={chipClass(onlyAttention, "border-warn/50 bg-warn/12 text-warn")}
          >
            Needs attention ({data.summary.attention})
          </button>
        )}
        {data && (
          <span className="hidden text-xs text-subtle lg:ml-auto lg:inline" aria-live="polite">
            {games.length} of {data.games.length} games
          </span>
        )}
        <SelectField label="Sort by" className="inline-flex shrink-0" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
          {SORTS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </SelectField>
      </div>
      <Link href={`/sheet/${qs}`} aria-label="Copy to Yahoo" className="relative z-10 inline-flex min-h-11 items-center rounded-full border border-border-strong bg-elevated px-4 text-sm font-medium text-text lg:min-h-9">
        Copy to Yahoo
      </Link>
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
              <Link href="/settings/" className="text-accent-text underline underline-offset-2">
                See data sources
              </Link>
            </div>
          )}

          <KpiStrip week={data} />

          {data.games.length === 0 ? (
            <EmptyState title={`No games scheduled for Week ${week}`} hint={`There are no ${season} games in this week. Pick another week or season above.`} />
          ) : (
            <section aria-label="Games">
              {games.length === 0 ? (
                <p className="rounded-card border border-border bg-surface px-4 py-10 text-center text-sm text-text-2">{scope === "open" ? "No games are open to pick in this week." : "No games need attention in this week."}</p>
              ) : (
                <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {groups.map((grp) => (
                    <Fragment key={grp.day || "all"}>
                      {grp.day && (
                        <li className="col-span-full pt-2 text-sm font-medium text-text first:pt-0">
                          {grp.day}
                          <span className="ml-2 text-xs font-normal text-subtle">
                            {grp.games.length} {grp.games.length === 1 ? "game" : "games"}
                          </span>
                        </li>
                      )}
                      {grp.games.map((g) => (
                        <GameCard key={g.game_id} game={g} highlight={g.game_id === nextId} pointsCount={pointsCount} />
                      ))}
                    </Fragment>
                  ))}
                </ul>
              )}
              <p className="mt-2 text-xs text-subtle">Select a game for the full matchup. Picks lock at kickoff.</p>
            </section>
          )}
        </>
      )}
    </div>
  );
}
