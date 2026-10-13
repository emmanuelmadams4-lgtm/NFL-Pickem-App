import { ago, type GameDetail, type Team } from "@nflpi/shared";
import { Chip, type ChipTone } from "@/components/ui";
import { TeamLogo } from "@/components/team";

const slotName = { qb: "QB", off: "Offense", def: "Defense" } as const;

export function statusTone(status: string | null): ChipTone | null {
  switch ((status ?? "").toLowerCase()) {
    case "out":
      return "bad";
    case "doubtful":
      return "warn";
    case "questionable":
      return "warn-soft";
    default:
      return null;
  }
}

function StarTeam({ team, club, week, reportsSeen }: {
  team: Team;
  club: GameDetail["stars"][number] | undefined;
  week: number;
  reportsSeen: number;
}) {
  return (
    <div className="min-w-0">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <TeamLogo team={team} size={20} />
        <h4 className="text-sm font-semibold text-text">{team.name}</h4>
        {club?.stars_week != null && club.stars.length > 0 && club.stars_week < week && (
          <span className="text-label text-subtle">Star list from week {club.stars_week}</span>
        )}
      </div>
      {!club || club.stars_week === null || club.stars.length === 0 ? (
        <p className="text-label text-text-2">No star list yet</p>
      ) : (
        <ul aria-label={`${team.name} star players`} className="divide-y divide-border">
          {club.stars.map((star) => {
            const details = [star.injury, star.observed_at && `seen ${ago(star.observed_at)}`].filter(Boolean);
            const tone = statusTone(star.status);
            return (
              <li key={`${star.slot}-${star.rank}`} className="flex min-w-0 items-start justify-between gap-3 py-2">
                <div className="min-w-0">
                  <p className="text-sm text-text break-words">
                    {star.player} <span className="text-label text-subtle">{star.position || slotName[star.slot]}</span>
                  </p>
                  {star.status && details.length > 0 && <p className="text-label text-text-2 break-words">{details.join(" · ")}</p>}
                </div>
                {star.status && tone ? <Chip tone={tone}>{star.status}</Chip> : (
                  <span className={`min-w-0 text-right text-label leading-5 break-words ${star.status ? "text-text-2" : "text-subtle"}`}>
                    {star.status || (reportsSeen === 0
                      ? <><span aria-hidden>–</span><span className="sr-only">Not known yet</span></>
                      : star.listed ? "No game status" : "Not on injury report")}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export function StarPlayers({ game }: { game: GameDetail }) {
  return (
    <div className="mb-6">
      <h3 className="text-sm font-semibold text-text">Star players</h3>
      <p className="mt-0.5 text-label text-subtle">A star being out does not change the pick.</p>
      <p className="text-label text-subtle">Ages count from when this app first saw the status.</p>
      {game.stars_out.reports_seen === 0 && <p className="mt-2 text-label text-text-2">No injury report yet this week</p>}
      <div className="mt-3 grid gap-6 md:grid-cols-2">
        <StarTeam team={game.away} club={game.stars.find((club) => club.team === game.away.abbr)} week={game.week}
          reportsSeen={game.stars_out.reports_seen} />
        <StarTeam team={game.home} club={game.stars.find((club) => club.team === game.home.abbr)} week={game.week}
          reportsSeen={game.stars_out.reports_seen} />
      </div>
    </div>
  );
}
