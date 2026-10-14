import { ago, type GameSummary, type LiveGameOut, type LiveOut } from "@nflpi/shared";

const NOT_UPDATING_AFTER_MS = 120_000;

export type LiveResult = {
  data: LiveOut | undefined;
  checkedAt: number;
  heldPosts: ReadonlyMap<string, LiveGameOut>;
};

/** Live display state shared by the week card and game screen. */
export type CardLiveState = {
  kind: "S2" | "S3" | "S4" | "S5" | "S6";
  label: string;
  labelLead: "Live" | "Not updating" | null;
  labelJoiner: string;
  labelRest: string;
  dim: boolean;
  score: { away: number; home: number } | null;
  chanceLine: string | null;
  gameChanceLine: string | null;
  chanceClub: string | null;
  chanceReader: string | null;
  reader: string;
};

function periodWords(row: LiveGameOut): { short: string | null; spoken: string | null } {
  const period = row.period;
  if (period === null || period < 1 || period > 7) return { short: null, spoken: null };
  if (row.clock === "0:00") {
    if (period === 2) return { short: "Halftime", spoken: "halftime" };
    if (period === 1 || period === 3 || period === 4) return { short: `End of Q${period}`, spoken: `end of the ${["first", "second", "third", "fourth"][period - 1]} quarter` };
  }
  const name = period <= 4 ? `Q${period}` : period === 5 ? "OT" : `${period - 4}OT`;
  const spoken = period <= 4 ? `${["first", "second", "third", "fourth"][period - 1]} quarter` : period === 5 ? "overtime" : `${period - 4} overtime`;
  return { short: row.clock ? `${name}\u00a0${row.clock}` : name, spoken: row.clock ? `${spoken}, ${row.clock} left` : spoken };
}

function chance(prob: number | null, home: boolean): string {
  if (prob === null) return "–";
  const value = home ? prob : 1 - prob;
  if (value < 0.01) return "<1%";
  if (value > 0.99) return ">99%";
  return `${home ? Math.round(prob * 100) : 100 - Math.round(prob * 100)}%`;
}

function spokenChance(value: string): string {
  return value.replace("<1%", "less than 1 percent").replace(">99%", "more than 99 percent").replace("%", " percent");
}

function spokenAge(value: string): string {
  return value.replace(/^1m ago$/, "1 minute ago").replace(/^1h ago$/, "1 hour ago").replace(/^1s ago$/, "1 second ago")
    .replace(/^(\d+)m ago$/, "$1 minutes ago").replace(/^(\d+)h ago$/, "$1 hours ago").replace(/^(\d+)s ago$/, "$1 seconds ago");
}

function s5ChanceLines(game: GameSummary, row: LiveGameOut) {
  const club = game.prediction?.pick ?? game.my_pick ?? game.home.abbr;
  const isHome = club === game.home.abbr;
  const espn = chance(row.home_win_prob, isHome);
  const kalshi = chance(row.kalshi_home_prob, isHome);
  const chanceLine = row.home_win_prob === null && row.kalshi_home_prob === null
    ? "No live win chance right now"
    : `${club} to win now · ESPN ${espn} · Kalshi ${kalshi}`;
  const gameChanceLine = row.home_win_prob === null && row.kalshi_home_prob === null
    ? chanceLine
    : `${club} to win now · ESPN ${espn}${row.home_win_prob === null ? " · none right now" : ""} · Kalshi ${kalshi}${row.kalshi_home_prob === null ? " · no fresh price" : ""}`;
  const chanceParts = [
    row.home_win_prob === null ? null : `ESPN gives ${club} a ${spokenChance(espn)} chance to win`,
    row.kalshi_home_prob === null ? null : `Kalshi price ${spokenChance(kalshi)}`,
  ].filter(Boolean);
  return { chanceLine, gameChanceLine, chanceClub: club, chanceReader: chanceParts.length ? `Right now ${chanceParts.join("; ")}.` : null };
}

/** The first matching live state for a started game. Final games stay on the week card's existing path. */
export function cardLiveState(game: GameSummary, live: LiveResult, now: number): CardLiveState | null {
  if (game.status === "final") return null;
  const current = live.data?.games.find((row) => row.game_id === game.game_id);
  const row = current ?? live.heldPosts.get(game.game_id);
  if (!row) return { kind: "S6", label: "Started", labelLead: null, labelJoiner: "", labelRest: "Started", dim: false, score: null, chanceLine: null, gameChanceLine: null, chanceClub: null, chanceReader: null, reader: "Game started, no live score right now." };

  const score = row.away_score !== null && row.home_score !== null ? { away: row.away_score, home: row.home_score } : null;
  const scoreWords = score ? `${game.away.abbr} ${score.away}, ${game.home.abbr} ${score.home}` : "no live score right now";
  const period = periodWords(row);
  const base = { score, dim: false, labelLead: null, labelJoiner: "", labelRest: "", chanceLine: null, gameChanceLine: null, chanceClub: null, chanceReader: null };

  if (row.state === "post") {
    const label = score ? "Ended · result pending" : "Ended · score not in yet";
    return { ...base, kind: "S2", label, labelRest: label, reader: score ? `Ended, result pending: ${scoreWords}.` : "Ended, score not in yet." };
  }
  if (row.state === "lost") {
    const labelRest = period.short ? ` · last seen ${period.short}` : "";
    return { ...base, kind: "S3", label: `Not updating${labelRest}`, labelLead: "Not updating", labelRest, dim: true, reader: `Score may be out of date: ${scoreWords}.` };
  }
  const notUpdating = live.data?.stale || (live.checkedAt > 0 && now - live.checkedAt > NOT_UPDATING_AFTER_MS);
  if (notUpdating) {
    const age = live.data?.last_confirmed_at ? ago(live.data.last_confirmed_at, new Date(now)) : null;
    const labelRest = period.short ? ` · ${period.short}` : "";
    return {
      ...base,
      kind: "S4",
      label: `Not updating${labelRest}`,
      labelLead: "Not updating",
      labelRest,
      dim: true,
      chanceLine: age ? `Last update ${age}` : "No update yet",
      gameChanceLine: age ? `Last update ${age}` : "No update yet",
      reader: `Score may be out of date, ${age ? `last update ${spokenAge(age)}` : "no update yet"}: ${scoreWords}.`,
    };
  }

  const labelJoiner = period.short ? " ·" : "";
  const labelRest = period.short ? ` ${period.short}` : "";
  return {
    kind: "S5",
    label: `Live${labelJoiner}${labelRest}`,
    labelLead: "Live",
    labelJoiner,
    labelRest,
    dim: false,
    score,
    ...s5ChanceLines(game, row),
    reader: score ? `Live score ${scoreWords}${period.spoken ? `, ${period.spoken}` : ""}.` : "Live score not in yet.",
  };
}
