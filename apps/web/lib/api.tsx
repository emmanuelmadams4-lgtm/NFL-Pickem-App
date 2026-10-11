"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createClient, type Api } from "@nflpi/shared";
import { trackedFetch } from "@/lib/sync";

export const TOKEN_KEY = "nflpi_token";
export const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

/** undefined = still reading localStorage, null = signed out, string = token */
type TokenState = string | null | undefined;

interface Session {
  token: string | null;
  baseUrl: string;
  api: Api | null;
  signIn: (token: string) => void;
  signOut: (notice?: string) => void;
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

export function SessionProvider({ children, onSignOut }: { children: ReactNode; onSignOut?: () => void }) {
  const [token, setToken] = useState<TokenState>(undefined);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setToken(readToken());
  }, []);

  const signIn = useCallback((t: string) => {
    try {
      localStorage.setItem(TOKEN_KEY, t);
    } catch {
      /* private mode: the session simply won't persist */
    }
    setNotice(null);
    setToken(t);
  }, []);

  const signOut = useCallback(
    (message?: string) => {
      try {
        localStorage.removeItem(TOKEN_KEY);
      } catch {
        /* ignore */
      }
      setNotice(message ?? null);
      setToken(null);
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
