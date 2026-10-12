"use client";

import { Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { QueryCache, QueryClient, QueryClientProvider, MutationCache } from "@tanstack/react-query";
import { ApiError } from "@nflpi/shared";
import { SessionProvider, useSession } from "@/lib/api";
import { useMeta } from "@/lib/queries";
import { ToastProvider } from "@/components/toast";
import { SignIn } from "@/components/sign-in";
import { ServiceWorkerRegister } from "@/components/pwa";
import { useOnline } from "@/lib/sync";
import { WEEK_MS, clearPersistedCache, requestPersistentStorage, restoreCache, startPersisting } from "@/lib/persist";
import { AppShell } from "@/components/app-shell";
import { Button, Skeleton, errorMessage } from "@/components/ui";

export function Providers({ children }: { children: ReactNode }) {
  const onUnauthorized = useRef<() => void>(() => {});
  const [client] = useState(() => {
    const c = new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            gcTime: WEEK_MS,
            refetchOnWindowFocus: true,
            networkMode: "offlineFirst",
            retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
          },
          mutations: { networkMode: "offlineFirst" },
        },
        queryCache: new QueryCache({
          onError: (err) => {
            if (err instanceof ApiError && err.status === 401) onUnauthorized.current();
          },
        }),
        mutationCache: new MutationCache({
          onError: (err) => {
            if (err instanceof ApiError && err.status === 401) onUnauthorized.current();
          },
        }),
      });
    restoreCache(c);
    return c;
  });

  useEffect(() => startPersisting(client), [client]);

  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <SessionProvider
          onSignOut={() => {
            client.clear();
            clearPersistedCache();
          }}
        >
          <ServiceWorkerRegister />
          <AuthFailureBridge handler={onUnauthorized} />
          <Gate>{children}</Gate>
        </SessionProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

/** Any 401 from any request drops the stored token and returns to the sign-in card. */
function AuthFailureBridge({ handler }: { handler: React.MutableRefObject<() => void> }) {
  const { signOut } = useSession();
  useEffect(() => {
    handler.current = () => signOut("Your token was rejected by the server. Sign in again.");
  }, [handler, signOut]);
  return null;
}

function Gate({ children }: { children: ReactNode }) {
  const { token, ready, notice } = useSession();
  useEffect(() => {
    if (ready && token) requestPersistentStorage();
  }, [ready, token]);
  if (!ready) return <FullScreenLoading />;
  if (!token) return <SignIn notice={notice} />;
  return <MetaGate>{children}</MetaGate>;
}

function MetaGate({ children }: { children: ReactNode }) {
  const meta = useMeta();
  const { signOut, baseUrl } = useSession();
  const online = useOnline();
  if (meta.isPending && !online) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center px-4">
        <div role="status" className="w-full max-w-md rounded-card border border-warn/40 bg-surface p-6">
          <h1 className="text-lg font-semibold text-warn">You are offline</h1>
          <p className="mt-1 text-sm text-text-2">Nothing is saved on this device yet. Connect once and open a week; it will be available offline afterwards.</p>
        </div>
      </main>
    );
  }
  if (meta.isPending) return <FullScreenLoading />;
  if (meta.isError) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center px-4">
        <div role="alert" className="w-full max-w-md rounded-card border border-bad/40 bg-surface p-6">
          <h1 className="text-lg font-semibold text-bad">Cannot reach the API</h1>
          <p className="mt-1 text-sm text-text-2">{errorMessage(meta.error)}</p>
          <p className="mt-1 text-sm text-text-2">Is Tailscale on?</p>
          <p className="mt-1 text-xs text-subtle">Server: {baseUrl || "this origin"}</p>
          <div className="mt-4 flex gap-2">
            <Button variant="primary" onClick={() => meta.refetch()}>
              Try again
            </Button>
            <Button variant="ghost" onClick={() => signOut()}>
              Change token
            </Button>
          </div>
        </div>
      </main>
    );
  }
  // Everything below the gate renders only on the client, after sign-in, so useSearchParams never runs during prerender.
  // The Suspense boundary is still required for static export and is deliberately below the gate: a boundary above it
  // would hydrate lazily, after the session state changed, and trigger a hydration mismatch.
  return (
    <Suspense fallback={<FullScreenLoading />}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}

function FullScreenLoading() {
  return (
    <div className="flex min-h-[100dvh] items-center justify-center" role="status" aria-label="Loading">
      <div className="w-64 space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
      </div>
    </div>
  );
}
