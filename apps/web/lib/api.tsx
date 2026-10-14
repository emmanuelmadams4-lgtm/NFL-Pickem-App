"use client";

import { createContext, useCallback, useContext, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { createClient, type Api } from "@nflpi/shared";
import { trackedFetch } from "@/lib/sync";

export const TOKEN_KEY = "nflpi_token";
export const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Session {
  token: string | null;
  baseUrl: string;
  api: Api | null;
  signIn: (token: string) => void;
  signOut: (notice?: string) => Promise<void>;
  notice: string | null;
  ready: boolean;
}

const SessionContext = createContext<Session | null>(null);

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/**
 * The token lives in an external store so the server render and the hydration render agree
 * (both see "not ready"), and the real value arrives right after hydration without a mismatch.
 */
let memoryToken: string | null = null;
let memoryTouched = false; // true once signIn/signOut ran, so a blocked localStorage still works for the session
const tokenListeners = new Set<() => void>();
const notifyToken = () => tokenListeners.forEach((l) => l());

function tokenSnapshot(): string | null {
  return memoryTouched ? memoryToken : readToken();
}
function subscribeToken(cb: () => void) {
  tokenListeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    tokenListeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

export function SessionProvider({ children, onSignOut }: { children: ReactNode; onSignOut?: () => void }) {
  const token = useSyncExternalStore<string | null | undefined>(subscribeToken, tokenSnapshot, () => undefined);
  const [notice, setNotice] = useState<string | null>(null);

  const signIn = useCallback((t: string) => {
    memoryToken = t;
    memoryTouched = true;
    try {
      localStorage.setItem(TOKEN_KEY, t);
    } catch {
      /* private mode: the session simply won't persist */
    }
    setNotice(null);
    notifyToken();
  }, []);

  const signOut = useCallback(
    async (message?: string) => {
      const current = tokenSnapshot();
      if (current?.startsWith("pks_")) {
        try {
          await createClient({ baseUrl: BASE_URL, token: current }).passkeySignout();
        } catch {
          /* clear the local session even when server sign-out fails */
        }
      }
      memoryToken = null;
      memoryTouched = true;
      try {
        localStorage.removeItem(TOKEN_KEY);
      } catch {
        /* ignore */
      }
      setNotice(message ?? null);
      notifyToken();
      onSignOut?.();
    },
    [onSignOut],
  );

  const api = useMemo(() => (token ? createClient({ baseUrl: BASE_URL, token, fetch: trackedFetch }) : null), [token]);

  const value = useMemo<Session>(
    () => ({ token: token ?? null, baseUrl: BASE_URL, api, signIn, signOut, notice, ready: token !== undefined }),
    [token, api, signIn, signOut, notice],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}

/** The typed API client. Only rendered below the token gate, so it is always present. */
export function useApi(): Api {
  const { api } = useSession();
  if (!api) throw new Error("useApi called without a token");
  return api;
}
