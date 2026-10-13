import { ago, type GameSummary, type LiveGameOut, type LiveOut } from "@nflpi/shared";

export type LiveResult = {
  data: LiveOut | undefined;
  dataUpdatedAt: number;
  heldPosts: ReadonlyMap<string, LiveGameOut>;
};

export type CardLiveState = {
  kind: "S2" | "S3" | "S4" | "S5" | "S6";
  label: string;
  score: { away: number; home: number } | null;
  chanceLine: string | null;
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
  return { short: row.clock ? `${name} ${row.clock}` : name, spoken: row.clock ? `${spoken}, ${row.clock} left` : spoken };
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
  return value.replace(/^(\d+)m ago$/, "$1 minutes ago").replace(/^(\d+)h ago$/, "$1 hours ago").replace(/^(\d+)s ago$/, "$1 seconds ago");
}

/** The first matching live state for a started game. Final games stay on the week card's existing path. */
export function cardLiveState(game: GameSummary, live: LiveResult, now: number): CardLiveState | null {
  if (game.status === "final") return null;
  const current = live.data?.games.find((row) => row.game_id === game.game_id);
  const row = current ?? live.heldPosts.get(game.game_id);
  if (!row) return { kind: "S6", label: "Started", score: null, chanceLine: null, chanceReader: null, reader: "Game started, no live score right now." };

  const score = row.away_score !== null && row.home_score !== null ? { away: row.away_score, home: row.home_score } : null;
  const scoreWords = score ? `${game.away.abbr} ${score.away}, ${game.home.abbr} ${score.home}` : "no live score right now";
  const period = periodWords(row);
  const base = { score, chanceLine: null, chanceReader: null };

  if (row.state === "post") {
    return { ...base, kind: "S2", label: score ? "Ended · result pending" : "Ended · score not in yet", reader: score ? `Ended, result pending: ${scoreWords}.` : "Ended, score not in yet." };
  }
  if (row.state === "lost") {
    return { ...base, kind: "S3", label: `Not updating${period.short ? ` · last seen ${period.short}` : ""}`, reader: `Score may be out of date: ${scoreWords}.` };
  }
  const notUpdating = live.data?.stale || (live.dataUpdatedAt > 0 && now - live.dataUpdatedAt > 120_000);
  if (notUpdating) {
    const age = live.data?.last_confirmed_at ? ago(live.data.last_confirmed_at, new Date(now)) : null;
    return {
      ...base,
      kind: "S4",
      label: `Not updating${period.short ? ` · ${period.short}` : ""}`,
      chanceLine: age ? `Last update ${age}` : "No update yet",
      reader: `Score may be out of date, ${age ? `last update ${spokenAge(age)}` : "no update yet"}: ${scoreWords}.`,
    };
  }

  const club = game.prediction?.pick ?? game.my_pick ?? game.home.abbr;
  const isHome = club === game.home.abbr;
  const espn = chance(row.home_win_prob, isHome);
  const kalshi = chance(row.kalshi_home_prob, isHome);
  const chanceLine = row.home_win_prob === null && row.kalshi_home_prob === null
    ? "No live win chance right now"
    : `${club} to win now · ESPN ${espn} · Kalshi ${kalshi}`;
  const chanceParts = [
    row.home_win_prob === null ? null : `ESPN gives ${club} a ${spokenChance(espn)} chance to win`,
    row.kalshi_home_prob === null ? null : `Kalshi price ${spokenChance(kalshi)}`,
  ].filter(Boolean);
  return {
    kind: "S5",
    label: `Live${period.short ? ` · ${period.short}` : ""}`,
    score,
    chanceLine,
    chanceReader: chanceParts.length ? `Right now ${chanceParts.join("; ")}.` : null,
    reader: score ? `Live score ${scoreWords}${period.spoken ? `, ${period.spoken}` : ""}.` : "Live score not in yet.",
  };
}
