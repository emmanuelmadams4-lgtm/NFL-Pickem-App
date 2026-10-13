"use client";

import { useSyncExternalStore } from "react";
import { ApiError, type Api } from "@nflpi/shared";
import type { QueryClient } from "@tanstack/react-query";
import { safeGet, safeRemove, safeSet } from "@/lib/fmt";

/* ---------- connectivity ---------- */

function subscribeOnline(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

let serverReachable = true;
const reachabilityListeners = new Set<() => void>();

function setServerReachable(value: boolean) {
  if (serverReachable === value) return;
  serverReachable = value;
  reachabilityListeners.forEach((listener) => listener());
}

export function isServerReachable(): boolean {
  return serverReachable;
}

export function useServerReachable(): boolean {
  return useSyncExternalStore(
    (listener) => {
      reachabilityListeners.add(listener);
      return () => reachabilityListeners.delete(listener);
    },
    isServerReachable,
    () => true,
  );
}

/** Remember whether the server answered; HTTP errors still prove it is reachable. */
export const trackedFetch: typeof fetch = async (input, init) => {
  try {
    const res = await fetch(input, init);
    setServerReachable(true);
    return res;
  } catch (error) {
    setServerReachable(false);
    throw error;
  }
};

export function isNetworkError(e: unknown): boolean {
  return !(e instanceof ApiError) && (
    e instanceof TypeError ||
    (e instanceof DOMException && (e.name === "TimeoutError" || e.name === "AbortError")) ||
    (e instanceof Error && /network|fetch|load failed/i.test(e.message))
  );
}

/* ---------- offline pick queue ---------- */

const QUEUE_KEY = "nflpi_pick_queue";
type Queue = Record<string, string | null>;

let snapshot: Queue | null = null;
let volatileQueue: Queue | null = null;
const listeners = new Set<() => void>();
let listeningForStorage = false;

function readStoredQueue(): Queue {
  try {
    const parsed: unknown = JSON.parse(safeGet(QUEUE_KEY) ?? "{}");
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(Object.entries(parsed).filter(([, team]) => typeof team === "string" || team === null)) as Queue;
  } catch {
    return {};
  }
}

function currentQueue(): Queue {
  return volatileQueue ?? readStoredQueue();
}

function listenForStorage() {
  if (listeningForStorage || typeof window === "undefined") return;
  listeningForStorage = true;
  window.addEventListener("storage", (event) => {
    if (event.key !== QUEUE_KEY) return;
    snapshot = null;
    listeners.forEach((listener) => listener());
  });
}

function readQueue(): Queue {
  listenForStorage();
  if (!snapshot) snapshot = currentQueue();
  return snapshot;
}

function writeQueue(q: Queue): boolean {
  listenForStorage();
  const value = JSON.stringify(q);
  const stored = safeSet(QUEUE_KEY, value);
  if (!stored) {
    const previous = readStoredQueue();
    const stale = (gameId: string, team: string | null) =>
      !Object.prototype.hasOwnProperty.call(q, gameId) || q[gameId] !== team;
    const fallback = Object.fromEntries(Object.entries(previous).filter(([gameId, team]) => !stale(gameId, team))) as Queue;
    if (Object.keys(fallback).length !== Object.keys(previous).length && !safeSet(QUEUE_KEY, JSON.stringify(fallback))) {
      if (Object.entries(readStoredQueue()).some(([gameId, team]) => stale(gameId, team))) safeRemove(QUEUE_KEY);
    }
  }
  snapshot = q;
  volatileQueue = stored ? null : q;
  listeners.forEach((l) => l());
  return stored;
}

export function queuePick(gameId: string, team: string | null): boolean {
  return writeQueue({ ...currentQueue(), [gameId]: team });
}

export function queuedPick(gameId: string): string | null | undefined {
  return currentQueue()[gameId];
}

let warnedGameId: string | null = null;

export function unqueue(gameId: string) {
  const next = { ...currentQueue() };
  delete next[gameId];
  writeQueue(next);
  if (warnedGameId === gameId) warnedGameId = null;
}

export function unqueueIfCurrent(gameId: string, team: string | null): boolean {
  const queue = currentQueue();
  if (queue[gameId] !== team) return false;
  unqueue(gameId);
  return true;
}

const pickSends = new Map<string, Promise<void>>();

/** Keep direct saves and queued saves for one game in the order they start. */
export function orderedPickSend<T>(gameId: string, send: () => Promise<T>): Promise<T> {
  const current = (pickSends.get(gameId) ?? Promise.resolve()).then(send);
  const settled = current.then(() => undefined, () => undefined);
  pickSends.set(gameId, settled);
  void settled.then(() => {
    if (pickSends.get(gameId) === settled) pickSends.delete(gameId);
  });
  return current;
}

export function pendingCount(): number {
  return Object.keys(readQueue()).length;
}

const EMPTY: Queue = {};
export function usePendingPicks(): Queue {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    readQueue,
    () => EMPTY,
  );
}

/** Pick to show: a queued (not yet synced) choice wins over what the server last said. */
export function effectivePick(pending: Queue, gameId: string, serverPick: string | null): { pick: string | null; waiting: boolean } {
  return gameId in pending ? { pick: pending[gameId], waiting: true } : { pick: serverPick, waiting: false };
}

/**
 * Send queued picks. 409 (kicked off) and 422 are dropped and reported as locked/invalid;
 * a network error stops the flush and keeps the rest queued.
 */
let flushing = false;
export async function flushPicks(api: Api, qc: QueryClient, notify: (message: string, tone: "good" | "warn" | "bad") => void): Promise<void> {
  if (flushing) return;
  const entries = Object.entries(readQueue());
  if (entries.length === 0) return;
  flushing = true;
  let synced = 0;
  let locked = 0;
  try {
    for (const [gameId, team] of entries) {
      if (readQueue()[gameId] !== team) continue;
      try {
        const saved = await orderedPickSend(gameId, async () => {
          if (readQueue()[gameId] !== team) return false;
          if (team) await api.setPick(gameId, team);
          else await api.clearPick(gameId);
          return unqueueIfCurrent(gameId, team);
        });
        if (saved) synced++;
      } catch (e) {
        if (e instanceof ApiError && (e.status === 409 || e.status === 422 || e.status === 404)) {
          if (unqueueIfCurrent(gameId, team)) locked++;
        } else if (isNetworkError(e)) {
          break;
        } else {
          if (warnedGameId !== gameId) notify("Pick not saved yet. Will retry.", "warn");
          warnedGameId = gameId;
          if (e instanceof ApiError && e.status === 401) break;
        }
      }
    }
  } finally {
    flushing = false;
    if (synced + locked > 0) {
      qc.invalidateQueries({ queryKey: ["week"] });
      qc.invalidateQueries({ queryKey: ["game"] });
      qc.invalidateQueries({ queryKey: ["performance"] });
    }
    if (locked > 0) notify(`${locked} waiting ${locked === 1 ? "pick was" : "picks were"} not saved: locked at kickoff.`, "warn");
    else if (synced > 0) notify(`${synced} waiting ${synced === 1 ? "pick" : "picks"} saved.`, "good");
  }
}
