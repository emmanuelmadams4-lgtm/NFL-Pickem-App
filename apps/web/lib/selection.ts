"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMeta } from "@/lib/queries";

export interface Selection {
  season: number;
  week: number;
  setSeason: (season: number) => void;
  setWeek: (week: number) => void;
  /** Query string that preserves the current season/week for links, e.g. "?season=2026&week=5" */
  qs: string;
}

/** Season and week live in the URL (?season=&week=) and default to the server's current week. */
export function useSelection(): Selection {
  const meta = useMeta().data;
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const currentSeason = meta?.current_season ?? new Date().getFullYear();
  const currentWeek = meta?.current_week ?? 1;

  const pSeason = Number(params.get("season"));
  const pWeek = Number(params.get("week"));
  const season = meta?.seasons.includes(pSeason) ? pSeason : currentSeason;
  const weekDefault = season === currentSeason ? currentWeek : 1;
  const week = meta?.weeks.includes(pWeek) ? pWeek : weekDefault;

  const replace = useCallback(
    (next: { season?: number; week?: number }) => {
      const sp = new URLSearchParams(params.toString());
      if (next.season !== undefined) sp.set("season", String(next.season));
      if (next.week !== undefined) sp.set("week", String(next.week));
      router.replace(`${pathname}?${sp.toString()}`, { scroll: false });
    },
    [params, router, pathname],
  );

  const setSeason = useCallback((s: number) => replace({ season: s, week: s === currentSeason ? currentWeek : 1 }), [replace, currentSeason, currentWeek]);
  const setWeek = useCallback((w: number) => replace({ week: w }), [replace]);

  return { season, week, setSeason, setWeek, qs: `?season=${season}&week=${week}` };
}
