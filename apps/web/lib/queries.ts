"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, keys, type GameDetail, type GameSummary, type LiveGameOut, type LiveOut, type Provider, type Week } from "@nflpi/shared";
import { useApi } from "@/lib/api";
import { useNow } from "@/lib/clock";
import { errorMessage } from "@/components/ui";
import { useToast } from "@/components/toast";
import { isNetworkError, isServerReachable, lastQueueWriteDroppedStored, orderedPickSend, queuePick, queuedPick, unqueueIfCurrent } from "@/lib/sync";

const LIVE_REFETCH_MS = 120_000;
const LIVE_POLL_MS = 30_000;
const LIVE_ENDED_POLL_MS = 120_000;

// ponytail: at most one ended row per game seen this session; reload clears the map.
const heldPosts = new Map<string, LiveGameOut>();

export function startedGame(game: GameSummary, now: number): boolean {
  if (game.status === "final" || game.status === "postponed") return false;
  return game.status === "in_progress" || (!game.time_tbd && now >= Date.parse(game.kickoff_utc));
}

export function useLive(games: GameSummary[]) {
  const api = useApi();
  const meta = useMeta();
  const now = useNow();
  const started = games.filter((game) => startedGame(game, now));
  const query = useQuery({
    queryKey: keys.live,
    queryFn: async () => {
      const data = await api.live();
      for (const row of data.games) {
        if (row.state === "post") heldPosts.set(row.game_id, row);
        else heldPosts.delete(row.game_id);
      }
      return data;
    },
    enabled: started.length > 0,
    // useNow rebuilds this callback each tick; the query compares its computed interval before resetting the timer.
    refetchInterval: (q) => {
      const data = q.state.data as LiveOut | undefined;
      const allEnded = started.every((game) => {
        const row = data?.games.find((item) => item.game_id === game.game_id);
        return row?.state === "post" || (!row && heldPosts.has(game.game_id));
      });
      return allEnded ? LIVE_ENDED_POLL_MS : LIVE_POLL_MS;
    },
    refetchIntervalInBackground: false,
    retry: false,
  });
  const correction = meta.data ? Date.parse(meta.data.server_time) - meta.dataUpdatedAt : 0;
  return { ...query, heldPosts, checkedAt: query.dataUpdatedAt ? query.dataUpdatedAt + correction : 0 };
}

export function useMeta() {
  const api = useApi();
  return useQuery({ queryKey: keys.meta, queryFn: () => api.meta(), staleTime: 5 * 60_000 });
}

export function useWeek(season: number, week: number) {
  const api = useApi();
  return useQuery({
    queryKey: keys.week(season, week),
    queryFn: () => api.week(season, week),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useGame(gameId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: keys.game(gameId ?? ""),
    queryFn: () => api.game(gameId as string),
    enabled: !!gameId,
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useNews(gameId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: keys.news(gameId ?? ""),
    queryFn: () => api.news(gameId as string),
    enabled: !!gameId,
  });
}

export function usePerformance(season: number) {
  const api = useApi();
  return useQuery({ queryKey: keys.performance(season), queryFn: () => api.performance(season) });
}

export function useBacktest() {
  const api = useApi();
  return useQuery({ queryKey: keys.backtest, queryFn: () => api.backtest(), staleTime: 30 * 60_000 });
}

export function useFreshness() {
  const api = useApi();
  return useQuery({ queryKey: ["freshness"] as const, queryFn: () => api.freshness(), refetchInterval: LIVE_REFETCH_MS });
}

interface PickVars {
  gameId: string;
  season: number;
  week: number;
  /** null clears the pick */
  team: string | null;
}

function withPick(week: Week, gameId: string, team: string | null): Week {
  const games = week.games.map((g) => (g.game_id === gameId ? { ...g, my_pick: team } : g));
  return { ...week, games, summary: { ...week.summary, picks_made: games.filter((g) => g.my_pick).length } };
}

/** One-tap pick with an optimistic update. 409 means the pick is locked. */
export function useSetPick(gameId: string) {
  const api = useApi();
  const leadMinutes = useMeta().data?.pick_lock_minutes ?? 15;
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    // One game's taps reach the server in order, so a quick pick-then-clear can't land as pick.
    scope: { id: `pick:${gameId}` },
    // Offline: keep the optimistic choice, queue it, and report success. The queue flushes when we are back online.
    mutationFn: (v: PickVars): Promise<{ queued: boolean }> => orderedPickSend(v.gameId, async () => {
      if (queuedPick(v.gameId) !== v.team) return { queued: true };
      if (!navigator.onLine || !isServerReachable()) {
        return { queued: true };
      }
      try {
        if (v.team) await api.setPick(v.gameId, v.team);
        else await api.clearPick(v.gameId);
        unqueueIfCurrent(v.gameId, v.team);
        return { queued: false };
      } catch (e) {
        if (isNetworkError(e)) {
          return { queued: true };
        }
        unqueueIfCurrent(v.gameId, v.team);
        throw e;
      }
    }),
    onMutate: async (v) => {
      const persisted = queuePick(v.gameId, v.team);
      const weekKey = keys.week(v.season, v.week);
      const gameKey = keys.game(v.gameId);
      await Promise.all([qc.cancelQueries({ queryKey: weekKey }), qc.cancelQueries({ queryKey: gameKey })]);
      const prevWeek = qc.getQueryData<Week>(weekKey);
      const prevGame = qc.getQueryData<GameDetail>(gameKey);
      qc.setQueryData<Week>(weekKey, (w) => (w ? withPick(w, v.gameId, v.team) : w));
      qc.setQueryData<GameDetail>(gameKey, (g) => (g ? { ...g, my_pick: v.team } : g));
      return { prevWeek, prevGame, persisted };
    },
    onError: (err, v, ctx) => {
      if (ctx?.prevWeek) qc.setQueryData(keys.week(v.season, v.week), ctx.prevWeek);
      if (ctx?.prevGame) qc.setQueryData(keys.game(v.gameId), ctx.prevGame);
      if (err instanceof ApiError && err.status === 409) toast(`Locked ${leadMinutes} min before kickoff.`, "warn");
      else toast(`Pick not saved. ${errorMessage(err)}`, "bad");
    },
    onSettled: (data, _err, v, ctx) => {
      if (data?.queued) {
        if (ctx?.persisted === false && queuedPick(v.gameId) === v.team) {
          if (lastQueueWriteDroppedStored()) {
            toast("Waiting picks could not be stored on this phone. Keep the app open until they sync, or enter them again when you are online.", "bad");
          } else {
            toast("Could not save this pick on the phone. Keep the app open until it syncs.", "warn");
          }
        }
        return; // do not refetch over a pick the server has not seen yet
      }
      qc.invalidateQueries({ queryKey: keys.week(v.season, v.week) });
      qc.invalidateQueries({ queryKey: keys.game(v.gameId) });
      qc.invalidateQueries({ queryKey: ["performance"] });
    },
  });
}

export function useGenerateReport(gameId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (provider: Provider) => api.report(gameId, provider),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.game(gameId) }),
  });
}

export function useAsk(gameId: string) {
  const api = useApi();
  return useMutation({
    mutationFn: (v: { question: string; provider: Provider }) => api.ask(gameId, v.question, v.provider),
  });
}
