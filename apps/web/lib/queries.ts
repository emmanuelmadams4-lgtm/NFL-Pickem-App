"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, keys, type GameDetail, type Provider, type Week } from "@nflpi/shared";
import { useApi } from "@/lib/api";
import { errorMessage } from "@/components/ui";
import { useToast } from "@/components/toast";
import { isNetworkError, queuePick } from "@/lib/sync";

const LIVE_REFETCH_MS = 120_000;

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

/** One-tap pick with an optimistic update. 409 means the game has kicked off. */
export function useSetPick(gameId: string) {
  const api = useApi();
  const qc = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    // One game's taps reach the server in order, so a quick pick-then-clear can't land as pick.
    scope: { id: `pick:${gameId}` },
    // Offline: keep the optimistic choice, queue it, and report success. The queue flushes when we are back online.
    mutationFn: async (v: PickVars): Promise<{ queued: boolean }> => {
      try {
        if (v.team) await api.setPick(v.gameId, v.team);
        else await api.clearPick(v.gameId);
        return { queued: false };
      } catch (e) {
        if (isNetworkError(e)) {
          queuePick(v.gameId, v.team);
          return { queued: true };
        }
        throw e;
      }
    },
    onMutate: async (v) => {
      const weekKey = keys.week(v.season, v.week);
      const gameKey = keys.game(v.gameId);
      await Promise.all([qc.cancelQueries({ queryKey: weekKey }), qc.cancelQueries({ queryKey: gameKey })]);
      const prevWeek = qc.getQueryData<Week>(weekKey);
      const prevGame = qc.getQueryData<GameDetail>(gameKey);
      qc.setQueryData<Week>(weekKey, (w) => (w ? withPick(w, v.gameId, v.team) : w));
      qc.setQueryData<GameDetail>(gameKey, (g) => (g ? { ...g, my_pick: v.team } : g));
      return { prevWeek, prevGame };
    },
    onError: (err, v, ctx) => {
      if (ctx?.prevWeek) qc.setQueryData(keys.week(v.season, v.week), ctx.prevWeek);
      if (ctx?.prevGame) qc.setQueryData(keys.game(v.gameId), ctx.prevGame);
      if (err instanceof ApiError && err.status === 409) toast("Locked at kickoff.", "warn");
      else toast(`Pick not saved. ${errorMessage(err)}`, "bad");
    },
    onSettled: (data, _err, v) => {
      if (data?.queued) return; // do not refetch over a pick the server has not seen yet
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
