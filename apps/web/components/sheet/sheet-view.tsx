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
  const total = q.data?.games.length ?? 0;

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
      {total !== games.length && <p className="text-label text-text-2">{games.length} of {total} games have points</p>}
      {q.isPending && <div aria-busy="true" aria-label="Loading sheet"><Skeleton className="h-64 rounded-card" /></div>}
      {q.isError && !q.data && <ErrorState title="Could not load the sheet" error={q.error} onRetry={() => q.refetch()} />}
      {q.data && games.length === 0 && <EmptyState title="No games with points this week" />}
      {games.length > 0 && (
        <>
          <Button variant="primary" className="h-11" onClick={() => void copy()}>Copy as text</Button>
          {copyStatus && <p role="status" className="text-sm text-text-2">{copyStatus}</p>}
          <div className="max-w-xl">
          <table className="w-full border-collapse text-left">
            <thead className="text-label text-text-2"><tr><th scope="col" className="py-2 font-medium">Game</th><th scope="col" className="py-2 font-medium">Pick</th><th scope="col" className="py-2 text-right font-medium">Points</th></tr></thead>
            <tbody className="divide-y divide-border border-y border-border">
            {games.map((g) => {
              const winner = g.sheet.my_pick === g.away.abbr ? g.away : g.home;
              return (
                <tr key={g.game_id} data-testid="sheet-row">
                  <td className="py-3 pr-2"><span className="block text-label text-text-2">{kickoffWhen(g)}</span><span className="text-sm font-semibold text-text">{g.away.abbr} @ {g.home.abbr}</span>{g.locked && <span className="ml-2 inline-flex items-center gap-1 text-label text-text-2"><Lock size={13} /> Locked</span>}</td>
                  <td className="py-3"><span className="flex items-center gap-2"><TeamLogo team={winner} size={24} /><span data-testid="sheet-winner" className="font-semibold text-text">{winner.abbr}</span></span><span className="text-label text-text-2">{g.sheet.pick_by === "user" ? "Your pick" : g.sheet.pick_by === "auto" ? "Model picked for you" : "Model's pick"}</span></td>
                  <td data-testid="sheet-points" className="py-3 text-right font-display text-xl text-text">{g.sheet.my_points}</td>
                </tr>
              );
            })}
            </tbody>
          </table>
          </div>
        </>
      )}
    </div>
  );
}
