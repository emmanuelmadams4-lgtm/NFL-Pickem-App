import type { GroupStandings } from "@nflpi/shared";
import { EmptyState, ErrorState, Section, Skeleton } from "@/components/ui";
import type { Load } from "@/lib/group";

export function Standings({ season, week, state, onRetry }: { season: number; week: number; state: Load<GroupStandings>; onRetry: () => void }) {
  return (
    <Section title="Standings" note={`Week ${week}, ${season}`} className="min-w-0">
      {state.status === "loading" && <div aria-busy="true" aria-label="Loading standings" className="space-y-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10 rounded-ctl" />)}</div>}
      {state.status === "error" && <ErrorState error={state.error} onRetry={onRetry} title="Could not load the standings" />}
      {state.status === "ok" && state.data.rows.length === 0 && <EmptyState title={`No standings for week ${week} yet`} hint="Upload your weekly performance file above." />}
      {state.status === "ok" && state.data.rows.length > 0 && (
        <>
          <table aria-label={`Standings for week ${week}`} className="w-full table-fixed text-sm">
            <thead className="border-b border-border text-label text-subtle">
              <tr>
                <th scope="col" className="w-10 py-2 pr-1 text-right font-medium tabular-nums sm:w-12">Rank</th>
                <th scope="col" className="py-2 pl-2 text-left font-medium">Member</th>
                <th scope="col" className="w-12 py-2 pl-1 text-right font-medium tabular-nums sm:w-14">Week</th>
                <th scope="col" className="w-14 py-2 pl-1 text-right font-medium tabular-nums sm:w-16">Total</th>
              </tr>
            </thead>
            <tbody>
              {state.data.rows.map((row, i) => (
                <tr key={`${row.member}-${i}`} className="border-b border-border">
                  <td className="py-2.5 pr-1 text-right align-top text-text-2 tabular-nums">{row.rank === null ? "–" : String(row.rank)}</td>
                  <td className="py-2.5 pl-2 align-top text-text [overflow-wrap:anywhere]">{row.member}</td>
                  <td className="py-2.5 pl-1 text-right align-top text-text tabular-nums">{row.points}</td>
                  <td className="py-2.5 pl-1 text-right align-top text-text tabular-nums">{row.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {state.data.weeks_counted.length > 0 && <p className="mt-3 text-label text-subtle">Totals count weeks {state.data.weeks_counted.join(", ")}.</p>}
        </>
      )}
    </Section>
  );
}
