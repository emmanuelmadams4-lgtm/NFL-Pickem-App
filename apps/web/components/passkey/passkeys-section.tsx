"use client";

import { useId, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, ago, keys } from "@nflpi/shared";
import { useApi } from "@/lib/api";
import { Button, Notice, Section, errorMessage } from "@/components/ui";
import { createPasskey, passkeyCancelled, passkeyReady, passkeyUnsupported } from "@/components/passkey/browser";
import { usePasskeysEnabled } from "@/components/passkey/use-passkeys-enabled";

export function PasskeysSection() {
  const api = useApi();
  const qc = useQueryClient();
  const nameId = useId();
  const list = useQuery({ queryKey: keys.passkeys, queryFn: () => api.passkeys(), retry: false });
  const enabled = usePasskeysEnabled(api);
  const [name, setName] = useState("");
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<number | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function add() {
    setError(null);
    if (!passkeyReady("create")) {
      setError(passkeyUnsupported);
      return;
    }
    setAdding(true);
    try {
      const options = await api.passkeyRegisterBegin();
      const credential = await createPasskey(options);
      await api.passkeyRegisterFinish(credential, name.trim() || null);
      setName("");
      await qc.invalidateQueries({ queryKey: keys.passkeys });
    } catch (err) {
      if (passkeyCancelled(err)) setError("No passkey was added.");
      else if (err instanceof ApiError && err.status === 403) setError("Adding a passkey needs the access token. Sign in with the token, then add it here.");
      else setError(errorMessage(err));
    } finally {
      setAdding(false);
    }
  }

  async function remove(id: number) {
    if (confirmId !== id) {
      setConfirmId(id);
      return;
    }
    setError(null);
    setRemoving(id);
    try {
      await api.removePasskey(id);
      setConfirmId(null);
      await qc.invalidateQueries({ queryKey: keys.passkeys });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRemoving(null);
    }
  }

  return (
    <Section id="passkeys" title="Passkeys" note="Sign in with a passkey on a device you trust.">
      <div className="space-y-4 pt-4">
        {list.isPending && <p className="text-sm text-text-2">Loading passkeys…</p>}
        {list.isError && <Notice tone="bad">{errorMessage(list.error)}</Notice>}
        {list.data && (list.data.passkeys.length ? (
          <ul className="space-y-2">
            {list.data.passkeys.map((row) => (
              <li key={row.id} className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-ctl border border-border bg-elevated p-3">
                <div className="min-w-0 break-words">
                  <p className="text-sm font-medium text-text">{row.label || "Unnamed passkey"}</p>
                  <p className="text-xs text-subtle">
                    Added {new Date(row.created_at).toLocaleDateString()} · {row.last_used_at ? `Last used ${ago(row.last_used_at)}` : "Never used"}
                  </p>
                </div>
                <Button type="button" variant="danger" size="sm" loading={removing === row.id} disabled={removing !== null && removing !== row.id} onClick={() => remove(row.id)}>
                  {confirmId === row.id ? "Confirm remove" : "Remove"}
                </Button>
              </li>
            ))}
          </ul>
        ) : <p className="text-sm text-text-2">No passkeys added yet.</p>)}
        {enabled && (
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-0 flex-1">
              <label htmlFor={nameId} className="block text-sm font-medium text-text">Passkey name (optional)</label>
              <input
                id={nameId}
                value={name}
                maxLength={64}
                onChange={(event) => setName(event.target.value)}
                className="mt-1.5 h-11 w-full rounded-ctl border border-border-strong bg-elevated px-3 text-base text-text placeholder:text-text-2 hover:border-text-2 lg:h-9 lg:text-sm"
              />
            </div>
            <Button type="button" onClick={add} loading={adding}>Add a passkey</Button>
          </div>
        )}
        {error && <Notice tone="bad">{error}</Notice>}
      </div>
    </Section>
  );
}
