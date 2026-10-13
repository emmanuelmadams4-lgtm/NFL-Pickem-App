import type { GroupShares, Week } from "@nflpi/shared";
import { Card, Chip, EmptyState, ErrorState, Section, Skeleton } from "@/components/ui";
import { dateTime, kickoffWhen } from "@/lib/fmt";
import { shareLine, type Load } from "@/lib/group";

type Game = GroupShares["games"][number];
type Side = Game["away"];

function SideRow({ side, picked }: { side: Side; picked: number }) {
  const line = shareLine(side, picked);
  return (
    <div data-testid={`side-${side.team}`} className="min-w-0 border-t border-border pt-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="font-semibold text-text">{side.team}</span>{" "}
        <span className="flex flex-wrap gap-x-3 text-text-2 tabular-nums">
          <span>{line.count}</span>{" "}<span>{line.share}</span>{" "}<span>{line.avg}</span>
        </span>
      </div>
      <div aria-hidden="true" className="mt-2 h-1.5 overflow-hidden rounded-full bg-elevated">
        <div className="h-full rounded-full bg-text-2" style={{ width: `${Math.max(0, Math.min(1, side.share ?? 0)) * 100}%` }} />
      </div>
    </div>
  );
}

export function Shares({ season, week, state, weekGames, onRetry }: {
  season: number; week: number; state: Load<GroupShares>; weekGames?: Week["games"]; onRetry: () => void;
}) {
  const games = state.status === "ok" ? state.data.games : [];
  return (
    <Section title="How the group picked" note={`Week ${week}, ${season}`} className="min-w-0">
      {state.status === "loading" && <div aria-busy="true" aria-label="Loading group picks" className="grid gap-3 xl:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-40 rounded-card" />)}</div>}
      {state.status === "error" && <ErrorState error={state.error} onRetry={onRetry} title="Could not load the group picks" />}
      {state.status === "ok" && games.length === 0 && <EmptyState title="No games this week" />}
      {state.status === "ok" && games.length > 0 && games.every((game) => game.picked === 0) && <EmptyState title={`No group picks for week ${week} yet`} hint="Upload your picks file above." />}
      {state.status === "ok" && games.some((game) => game.picked > 0) && (
        <div className="grid min-w-0 gap-3 xl:grid-cols-2">
          {games.map((game) => {
            const weekGame = weekGames?.find((g) => g.game_id === game.game_id);
            return (
              <Card key={game.game_id} data-testid="group-game" className="min-w-0 p-4">
                <h3 className="text-sm font-semibold text-text">{game.away_team} at {game.home_team}</h3>
                <p className="mt-1 text-label text-subtle">{weekGame ? kickoffWhen(weekGame) : dateTime(game.kickoff_utc)}</p>
                <Chip tone="neutral" className="mt-3">App pick: {weekGame?.sheet.app_pick ?? "–"}</Chip>
                {game.picked === 0 ? (
                  <p className="mt-4 text-sm text-text-2">No group picks for this game yet</p>
                ) : (
                  <div className="mt-4 space-y-3">
                    <SideRow side={game.away} picked={game.picked} />
                    <SideRow side={game.home} picked={game.picked} />
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </Section>
  );
}
