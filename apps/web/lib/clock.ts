"use client";

import { useSyncExternalStore } from "react";
import type { GameSummary } from "@nflpi/shared";
import { useMeta } from "@/lib/queries";

const TICK_MS = 2_000;

/* One shared ticker for every component that reads the clock. */
let clientNow = Date.now();
let timer: ReturnType<typeof setInterval> | undefined;
const listeners = new Set<() => void>();

function subscribe(cb: () => void) {
  listeners.add(cb);
  if (listeners.size === 1) {
    clientNow = Date.now();
    timer = setInterval(() => {
      clientNow = Date.now();
      listeners.forEach((l) => l());
    }, TICK_MS);
  }
  return () => {
    listeners.delete(cb);
    if (listeners.size === 0) clearInterval(timer);
  };
}

/**
 * Server time now, in ms. Ticks every 2 s so a game locks on screen at the configured lead, without a reload.
 * The device clock is corrected by how far it was from the server when /api/meta arrived.
 */
export function useNow(): number {
  const meta = useMeta();
  const now = useSyncExternalStore(subscribe, () => clientNow, () => clientNow);
  return now + (meta.data ? Date.parse(meta.data.server_time) - meta.dataUpdatedAt : 0);
}

type LockGame = Pick<GameSummary, "locked" | "kickoff_utc" | "time_tbd" | "status">;

/** The API's `locked`, or a known kickoff within the lock lead. Same rule as the server's is_locked(). */
export function isLocked(game: LockGame, now: number, leadMinutes: number): boolean {
  return game.locked || (now >= Date.parse(game.kickoff_utc) - leadMinutes * 60_000 && !game.time_tbd && game.status !== "postponed");
}

export function useLocked(game: LockGame): boolean {
  const leadMinutes = useMeta().data?.pick_lock_minutes ?? 15;
  return isLocked(game, useNow(), leadMinutes);
}
