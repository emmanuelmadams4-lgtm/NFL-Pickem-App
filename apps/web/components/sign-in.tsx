"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, createClient, keys } from "@nflpi/shared";
import { BASE_URL, useSession } from "@/lib/api";
import { Button, Notice } from "@/components/ui";

export function SignIn({ notice }: { notice?: string | null }) {
  const { signIn } = useSession();
  const qc = useQueryClient();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const token = value.trim();
    if (!token) {
      setError("Enter your access token.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const meta = await createClient({ baseUrl: BASE_URL, token }).meta();
      qc.setQueryData(keys.meta, meta);
      signIn(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError("Wrong token");
      else setError(`Could not reach the API${BASE_URL ? ` at ${BASE_URL}` : ""}. Check that the server is running.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-[100dvh] items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-card border border-border bg-surface p-5 sm:p-6" aria-labelledby="signin-title">
        <p className="text-xs font-medium text-subtle">Private workspace</p>
        <h1 id="signin-title" className="mt-1 text-xl font-semibold tracking-tight">
          Pick&apos;em Intel
        </h1>
        <p className="mt-1 text-sm text-text-2">Enter the access token for your server to continue.</p>

        {notice && <Notice tone="warn" className="mt-4">{notice}</Notice>}

        <div className="mt-5">
          <label htmlFor="token" className="block text-sm font-medium text-text">
            Access token
          </label>
          <input
            id="token"
            name="token"
            type="password"
            autoComplete="current-password"
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-invalid={!!error}
            aria-describedby={error ? "token-error" : "token-help"}
            className="mt-1.5 h-11 w-full rounded-ctl border border-border bg-elevated px-3 text-base text-text placeholder:text-subtle hover:border-muted"
          />
          {error ? (
            <p id="token-error" role="alert" className="mt-1.5 text-sm text-bad">
              {error}
            </p>
          ) : (
            <p id="token-help" className="mt-1.5 text-xs text-subtle">
              Stored in this browser only.
            </p>
          )}
        </div>

        <Button type="submit" variant="primary" loading={busy} className="mt-5 w-full">
          {busy ? "Checking" : "Sign in"}
        </Button>
      </form>
    </main>
  );
}
