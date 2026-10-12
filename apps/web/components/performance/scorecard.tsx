"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, keys, type ScorecardWeek } from "@nflpi/shared";
import { useApi } from "@/lib/api";
import { useMeta } from "@/lib/queries";
import { Button, ErrorState, Section, Skeleton, errorMessage } from "@/components/ui";

const inputClass = "mt-1 h-11 w-full rounded-ctl border border-border-strong bg-elevated px-3 text-base text-text lg:h-10";

function Missing({ reason }: { reason: string }) {
  return <span className="text-subtle">–<span className="sr-only">{reason}</span></span>;
}

export function Scorecard({ season }: { season: number }) {
  const api = useApi();
  const qc = useQueryClient();
  const meta = useMeta().data;
  const q = useQuery({ queryKey: keys.scorecard(season), queryFn: () => api.scorecard(season) });
  const [week, setWeek] = useState<number | null>(null);
  const [rank, setRank] = useState("");
  const [leader, setLeader] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const selectedWeek = week ?? meta?.current_week ?? 1;
  useEffect(() => {
    if (!q.data) return;
    const row = q.data.weeks.find((r) => r.week === selectedWeek);
    setRank(row?.rank == null ? "" : String(row.rank));
    setLeader(row?.leader_points == null ? "" : String(row.leader_points));
  }, [q.data, selectedWeek]);

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setSaved(false);
    setBusy(true);
    try {
      await api.setRank(season, selectedWeek, { rank: Number(rank), leader_points: leader === "" ? null : Number(leader) });
      await qc.invalidateQueries({ queryKey: keys.scorecard(season) });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 422 ? errorMessage(err) : `Could not save rank. ${errorMessage(err)}`);
    } finally {
      setBusy(false);
    }
  }

  const cells = (row: ScorecardWeek, total = false) => (
    <>
      <th scope="row" className="px-3 py-3 text-left font-medium whitespace-nowrap">{total ? "Total" : `Week ${row.week}`}</th>
      <td className="px-3 py-3 text-right">{row.games ? row.my_points : <Missing reason="No finished games" />}</td>
      <td className="px-3 py-3 text-right">{row.games ? row.app_points : <Missing reason="No finished games" />}</td>
      <td className="px-3 py-3 text-right">{row.games ? row.max_points : <Missing reason="No finished games" />}</td>
      <td className="px-3 py-3 text-right whitespace-nowrap">{row.changed} ({row.changed_right} right, {row.changed_wrong} wrong)</td>
      <td className="px-3 py-3 text-right">{row.auto}</td>
      <td className="px-3 py-3 text-right">
        {row.rank === null ? <Missing reason={total ? "No total rank" : "Rank not entered"} /> : (
          <>{row.rank}{row.leader_points !== null && <span className="block text-label text-text-2">Leader {row.leader_points} points</span>}</>
        )}
      </td>
    </>
  );

  return (
    <Section id="scorecard" title="Scorecard" note="Your points beside the model's own sheet.">
      {q.isPending && <Skeleton className="h-48 rounded-card" />}
      {q.isError && !q.data && <ErrorState title="Could not load scorecard" error={q.error} onRetry={() => q.refetch()} />}
      {q.data && <>
        <div className="hidden sm:block relative w-full min-w-0 rounded-card border border-border bg-surface">
          <table aria-label="Scorecard" className="w-full text-sm text-text">
            <thead><tr className="border-b border-border text-label text-text-2">
              {["Week", "You", "Model", "Best possible", "Picks you changed", "Picked for you", "Rank"].map((h) => <th key={h} scope="col" className="px-3 py-3 text-right font-medium first:text-left">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-border">{q.data.weeks.map((row) => <tr key={row.week}>{cells(row)}</tr>)}</tbody>
            <tfoot className="border-t border-border font-semibold"><tr>{cells(q.data.totals, true)}</tr></tfoot>
          </table>
        </div>
        <div className="space-y-3 sm:hidden">
          {[...q.data.weeks, q.data.totals].map((row, i) => <div key={i} className="border-b border-border py-3 text-sm">
            <p className="mb-2 font-medium text-text">{i === q.data.weeks.length ? "Total" : `Week ${row.week}`}</p>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
            {[["You", row.my_points], ["Model", row.app_points], ["Best possible", row.max_points], ["Picks you changed", `${row.changed} (${row.changed_right} right, ${row.changed_wrong} wrong)`], ["Picked for you", row.auto], ["Rank", row.rank ?? "–"]].map(([label, value]) => <div key={String(label)} className="contents"><dt className="text-label text-text-2">{label}</dt><dd className="text-right text-text">{value}</dd></div>)}
            </dl>
          </div>)}
        </div>
      </>}
      <form onSubmit={(e) => void save(e)} className="mt-5 min-w-0 rounded-card border border-border bg-surface p-4">
        <fieldset className="min-w-0 space-y-3">
          <legend className="text-sm font-semibold text-text">Your Yahoo rank</legend>
          <p className="text-label text-text-2">From your Yahoo league&apos;s standings.</p>
          <div className="flex flex-wrap gap-3">
            <label className="block w-full max-w-40 text-label text-text-2">Week
              <select className={inputClass} value={selectedWeek} onChange={(e) => { const w = Number(e.target.value); setWeek(w); const row = q.data?.weeks.find((r) => r.week === w); setRank(row?.rank == null ? "" : String(row.rank)); setLeader(row?.leader_points == null ? "" : String(row.leader_points)); }}>
                {Array.from({ length: 18 }, (_, i) => <option key={i + 1} value={i + 1}>Week {i + 1}</option>)}
              </select>
            </label>
            <label className="block w-full max-w-40 text-label text-text-2">Your rank
              <input className={inputClass} type="number" min="1" required value={rank} onChange={(e) => setRank(e.target.value)} />
            </label>
            <label className="block w-full max-w-40 text-label text-text-2">Leader&apos;s points
              <input className={inputClass} type="number" min="0" value={leader} onChange={(e) => setLeader(e.target.value)} />
            </label>
          </div>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          {saved && <p role="status" className="text-sm text-good">Rank saved</p>}
          <Button type="submit" className="h-11" loading={busy}>Save rank</Button>
        </fieldset>
      </form>
    </Section>
  );
}
