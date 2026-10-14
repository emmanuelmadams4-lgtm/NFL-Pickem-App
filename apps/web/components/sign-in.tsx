"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, createClient, keys } from "@nflpi/shared";
import { BASE_URL, useSession } from "@/lib/api";
import { Bezel, Button, Notice } from "@/components/ui";
import { getPasskey, PasskeyBrowserError, passkeyCancelled, passkeyReady, passkeyUnsupported } from "@/components/passkey/browser";
import { usePasskeysEnabled } from "@/components/passkey/use-passkeys-enabled";

const unreachableApi = `Could not reach the API${BASE_URL ? ` at ${BASE_URL}` : ""}. Check that the server is running.`;

export function SignIn({ notice }: { notice?: string | null }) {
  const { signIn } = useSession();
  const qc = useQueryClient();
  const [value, setValue] = useState("");
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [passkeyError, setPasskeyError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [passkeyBusy, setPasskeyBusy] = useState(false);
  const publicApi = createClient({ baseUrl: BASE_URL, token: "" });
  const passkeysOn = usePasskeysEnabled(publicApi);

  async function signInWithPasskey() {
    setTokenError(null);
    setPasskeyError(null);
    if (!passkeyReady("get")) {
      setPasskeyError(passkeyUnsupported);
      return;
    }
    setPasskeyBusy(true);
    try {
      const options = await publicApi.passkeySigninBegin();
      const credential = await getPasskey(options);
      const session = await publicApi.passkeySigninFinish(credential);
      signIn(session.session);
    } catch (err) {
      if (passkeyCancelled(err)) setPasskeyError("No passkey was used.");
      else if (err instanceof PasskeyBrowserError) setPasskeyError(err.message);
      else if (err instanceof ApiError && err.status === 401) setPasskeyError("Passkey sign-in failed.");
      else if (err instanceof ApiError) setPasskeyError(err.message);
      else if (err instanceof Error && err.message === passkeyUnsupported) setPasskeyError(passkeyUnsupported);
      else setPasskeyError(unreachableApi);
    } finally {
      setPasskeyBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPasskeyError(null);
    const token = value.trim();
    if (!token) {
      setTokenError("Enter your access token.");
      return;
    }
    setBusy(true);
    setTokenError(null);
    try {
      const meta = await createClient({ baseUrl: BASE_URL, token }).meta();
      qc.setQueryData(keys.meta, meta);
      signIn(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setTokenError("Wrong token");
      else setTokenError(unreachableApi);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-[100dvh] items-center justify-center px-4">
      <Bezel className="w-full max-w-sm">
        <form onSubmit={submit} className="p-5 sm:p-6" aria-labelledby="signin-title">
          {/* eslint-disable-next-line @next/next/no-img-element -- static export; the owner's app icon (D41) */}
          <img src="/icons/icon-192.png" alt="" width={56} height={56} className="mb-4 size-14 rounded-[16px]" />
          <p className="text-sm text-text-2">Private workspace</p>
          <h1 id="signin-title" className="mt-0.5 text-[40px] leading-[40px] text-text">
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
              aria-invalid={!!tokenError}
              aria-describedby={tokenError ? "token-error" : "token-help"}
              className="mt-1.5 h-11 w-full rounded-ctl border border-border-strong bg-elevated px-3 text-base text-text placeholder:text-text-2 hover:border-text-2"
            />
            {tokenError ? (
              <p id="token-error" role="alert" className="mt-1.5 text-sm text-bad">
                {tokenError}
              </p>
            ) : (
              <p id="token-help" className="mt-1.5 text-xs text-subtle">
                Stored in this browser only.
              </p>
            )}
          </div>

          <Button type="submit" variant="primary" loading={busy} disabled={passkeyBusy} className="mt-5 w-full">
            {busy ? "Checking" : "Sign in"}
          </Button>
          {passkeysOn && (
            <>
              <Button type="button" onClick={signInWithPasskey} loading={passkeyBusy} disabled={busy} className="mt-3 w-full">
                Sign in with a passkey
              </Button>
              {passkeyError && <p role="alert" className="mt-1.5 text-sm text-bad">{passkeyError}</p>}
            </>
          )}
        </form>
      </Bezel>
    </main>
  );
}
