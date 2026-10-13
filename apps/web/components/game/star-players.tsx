import { ago, type GameDetail, type Team } from "@nflpi/shared";
import { Chip } from "@/components/ui";
import { TeamLogo } from "@/components/team";

const slotName = { qb: "QB", off: "Offense", def: "Defense" } as const;

function StarTeam({ team, club, week, reportsSeen }: {
  team: Team;
  club: GameDetail["stars"][number] | undefined;
  week: number;
  reportsSeen: number;
}) {
  return (
    <div className="min-w-0">
      <div className="mb-2 flex items-center gap-2">
        <TeamLogo team={team} size={20} />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text">{team.name}</p>
          {club?.stars_week !== null && club?.stars_week !== undefined && club.stars_week < week && (
            <p className="text-label text-subtle">Star list from week {club.stars_week}</p>
          )}
        </div>
      </div>
      {!club || club.stars_week === null ? (
        <p className="rounded-ctl border border-dashed border-border px-3 py-4 text-sm text-text-2">No star list yet</p>
      ) : (
        <ul aria-label={`${team.name} star players`} className="divide-y divide-border">
          {club.stars.map((star) => (
            <li key={`${star.slot}-${star.rank}`} className="flex min-w-0 items-start justify-between gap-3 py-2">
              <div className="min-w-0">
                <p className="text-sm text-text break-words">
                  <span className="mr-1 text-xs text-subtle">{slotName[star.slot]}</span>
                  {star.player} {star.position && <span className="text-xs text-subtle">{star.position}</span>}
                </p>
                {star.status && (
                  <p className="text-xs text-text-2 break-words">
                    {[star.injury, star.observed_at && `seen ${ago(star.observed_at)}`].filter(Boolean).join(" · ")}
                  </p>
                )}
              </div>
              {star.status === "Out" ? <Chip tone="bad">Out</Chip>
                : star.status === "Doubtful" ? <Chip tone="warn">Doubtful</Chip>
                : <span className="shrink-0 text-right text-xs text-text-2">
                    {star.status || (reportsSeen === 0 ? "–" : "Not on injury report")}
                  </span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function StarPlayers({ game }: { game: GameDetail }) {
  return (
    <div className="mt-5 mb-6">
      <h3 className="text-sm font-semibold text-text">Star players</h3>
      <p className="mt-0.5 text-label text-subtle">A star being out does not change the pick.</p>
      <p className="text-label text-subtle">Ages count from when this app first saw the status.</p>
      {game.stars_out.reports_seen === 0 && <p className="mt-2 text-label text-subtle">No injury report yet this week</p>}
      <div className="mt-3 grid gap-6 md:grid-cols-2">
        <StarTeam team={game.away} club={game.stars.find((club) => club.team === game.away.abbr)} week={game.week}
          reportsSeen={game.stars_out.reports_seen} />
        <StarTeam team={game.home} club={game.stars.find((club) => club.team === game.home.abbr)} week={game.week}
          reportsSeen={game.stars_out.reports_seen} />
      </div>
    </div>
  );
}
