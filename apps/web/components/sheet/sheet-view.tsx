"use client";

import { useState } from "react";
import { useSelection } from "@/lib/selection";
import { useWeek } from "@/lib/queries";
import { kickoffWhen } from "@/lib/fmt";
import { TeamLogo } from "@/components/team";
import { Lock } from "@/components/icons";
import { Button, EmptyState, ErrorState, PageHead, Skeleton } from "@/components/ui";

export function SheetView() {
  const { season, week } = useSelection();
  const q = useWeek(season, week);
  const [copyStatus, setCopyStatus] = useState("");
  const games = [...(q.data?.games ?? [])]
    .filter((g) => g.sheet.my_points !== null)
    .sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc) || a.game_id.localeCompare(b.game_id));

  async function copy() {
    const text = games.map((g) => `${g.away.abbr} @ ${g.home.abbr}: ${g.sheet.my_pick} ${g.sheet.my_points}`).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus("Copied");
    } catch {
      setCopyStatus("Could not copy. Please copy the picks by hand.");
    }
  }

  return (
    <div className="space-y-5">
      <PageHead kicker={`Week ${week}`} title="Copy sheet" sub="Enter these in Yahoo. Tiebreaker scores are not in the app yet." />
      {q.isPending && <div aria-busy="true" aria-label="Loading sheet"><Skeleton className="h-64 rounded-card" /></div>}
      {q.isError && !q.data && <ErrorState title="Could not load the sheet" error={q.error} onRetry={() => q.refetch()} />}
      {q.data && games.length === 0 && <EmptyState title="No games with points this week" />}
      {games.length > 0 && (
        <>
          <Button variant="primary" className="h-11" onClick={() => void copy()}>Copy as text</Button>
          {copyStatus && <p role="status" className="text-sm text-text-2">{copyStatus}</p>}
          <ol className="divide-y divide-border rounded-card border border-border bg-surface px-4">
            {games.map((g) => {
              const winner = g.sheet.my_pick === g.away.abbr ? g.away : g.home;
              return (
                <li key={g.game_id} data-testid="sheet-row" className="flex flex-wrap items-center justify-between gap-3 py-4">
                  <div className="min-w-0">
                    <p className="text-label text-text-2">{kickoffWhen(g)}</p>
                    <p className="text-sm font-semibold text-text">{g.away.abbr} @ {g.home.abbr}</p>
                    {g.sheet.pick_by === "auto" && <p className="text-label text-text-2">Auto pick</p>}
                    {g.sheet.pick_by === "app" && <p className="text-label text-text-2">App pick</p>}
                    {g.locked && <p className="flex items-center gap-1 text-label text-text-2"><Lock size={13} /> Locked</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <TeamLogo team={winner} size={28} />
                    <span data-testid="sheet-winner" className="font-semibold text-text">{winner.abbr}</span>
                    <span data-testid="sheet-points" className="font-display ml-3 text-[32px] leading-8 text-text">{g.sheet.my_points}</span>
                  </div>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </div>
  );
}
