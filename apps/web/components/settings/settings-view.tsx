"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ApiError, ago, createClient, keys, type Meta } from "@nflpi/shared";
import { useQueryClient } from "@tanstack/react-query";
import { endStoredPasskeySession, PASSKEY_SIGNOUT_FAILED_NOTICE, useApi, useSession } from "@/lib/api";
import { useFreshness, useMeta } from "@/lib/queries";
import { useSelection } from "@/lib/selection";
import { useToast } from "@/components/toast";
import { Button, Chip, ErrorState, Notice, PageHead, SelectField, Section, Skeleton, errorMessage } from "@/components/ui";
import { FreshnessTable } from "@/components/freshness";
import { safeGet, safeSet } from "@/lib/fmt";
import { useOnline } from "@/lib/sync";
import { useStorageStatus } from "@/lib/persist";
import { AlertsSection } from "@/components/settings/alerts";
import { PasskeysSection } from "@/components/passkey/passkeys-section";

function Row({ label, hint, children }: { label: string; hint?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="grid gap-x-8 gap-y-2 py-4 first:pt-0 last:pb-0 md:grid-cols-[240px_minmax(0,1fr)]">
      <div>
        <p className="text-sm font-medium text-text">{label}</p>
        {hint && <p className="mt-0.5 text-xs text-subtle">{hint}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function AccessSection() {
  const { signOut, signIn, baseUrl } = useSession();
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const id = useId();

  async function change(e: React.FormEvent) {
    e.preventDefault();
    if (!next.trim()) return;
    setBusy(true);
    setError(null);
    try {
      try {
        await createClient({ baseUrl, token: next.trim() }).meta();
      } catch (err) {
        setError(err instanceof ApiError && err.status === 401 ? "Wrong token" : errorMessage(err));
        return;
      }
      const ended = await endStoredPasskeySession();
      signIn(next.trim());
      setNext("");
      toast(ended ? "Token updated." : PASSKEY_SIGNOUT_FAILED_NOTICE, ended ? "good" : "bad");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section id="access" title="Access">
      <Row label="Signed in" hint={`Server: ${baseUrl || "this origin"}`}>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-text-2" aria-label="Token is stored in this browser">
            Token stored in this browser
          </span>
          <Button variant="danger" size="sm" onClick={() => signOut()}>
            Sign out
          </Button>
        </div>
      </Row>
      <Row label="Change token">
        <form onSubmit={change} className="flex max-w-md flex-wrap items-start gap-2">
          <div className="min-w-0 flex-1">
            <label htmlFor={id} className="sr-only">
              New access token
            </label>
            <input
              id={id}
              type="password"
              autoComplete="off"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              placeholder="New access token"
              aria-invalid={!!error}
              className="h-11 w-full rounded-ctl border border-border-strong bg-elevated px-3 text-base text-text placeholder:text-text-2 hover:border-text-2 lg:h-9 lg:text-sm"
            />
            {error && (
              <p role="alert" className="mt-1.5 text-sm text-bad">
                {error}
              </p>
            )}
          </div>
          <Button type="submit" loading={busy} disabled={!next.trim()}>
            Update
          </Button>
        </form>
      </Row>
    </Section>
  );
}

function LeaderSection({ meta }: { meta: Meta }) {
  const api = useApi();
  const qc = useQueryClient();
  const { toast } = useToast();
  const id = useId();
  const [value, setValue] = useState(meta.league_leader_accuracy != null ? String(+(meta.league_leader_accuracy * 100).toFixed(1)) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    let payload: number | null = null;
    if (trimmed !== "") {
      const n = Number(trimmed);
      if (!Number.isFinite(n) || n < 0 || n > 100) {
        setError("Enter a percentage between 0 and 100.");
        return;
      }
      payload = n / 100;
    }
    setError(null);
    setBusy(true);
    try {
      const updated = await api.updateSettings({ league_leader_accuracy: payload });
      qc.setQueryData(keys.meta, updated);
      qc.invalidateQueries({ queryKey: ["week"] });
      qc.invalidateQueries({ queryKey: ["performance"] });
      toast(payload === null ? "League leader reference cleared." : "League leader accuracy saved.", "good");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section id="leader" title="League leader reference">
      <form onSubmit={save}>
        <Row label="League leader accuracy" hint="Optional. Shown as a reference on the week board and the Performance chart.">
          <div className="flex flex-wrap items-start gap-2">
            <div>
              <label htmlFor={id} className="sr-only">
                League leader accuracy in percent
              </label>
              <div className="flex items-center gap-2">
                <input
                  id={id}
                  inputMode="decimal"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="e.g. 68.5"
                  aria-invalid={!!error}
                  className="h-11 w-32 rounded-ctl border border-border-strong bg-elevated px-3 text-base text-text placeholder:text-text-2 hover:border-text-2 lg:h-9 lg:text-sm"
                />
                <span className="text-sm text-text-2">%</span>
              </div>
              {error && (
                <p role="alert" className="mt-1.5 text-sm text-bad">
                  {error}
                </p>
              )}
            </div>
            <Button type="submit" loading={busy}>
              Save
            </Button>
          </div>
          <p className="mt-2 text-xs text-subtle">Leave empty and save to clear.</p>
        </Row>
      </form>
    </Section>
  );
}

function CsvSection({ meta }: { meta: Meta }) {
  const api = useApi();
  const qc = useQueryClient();
  const { toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [season, setSeason] = useState(meta.current_season);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<{ imported: number; skipped: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function exportCsv() {
    setExporting(true);
    try {
      const text = await api.exportPicks(season);
      const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `picks-${season}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      toast(`Export failed. ${errorMessage(e)}`, "bad");
    } finally {
      setExporting(false);
    }
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.importPicks(await file.text());
      setResult(r);
      qc.invalidateQueries({ queryKey: ["week"] });
      qc.invalidateQueries({ queryKey: ["game"] });
      qc.invalidateQueries({ queryKey: ["performance"] });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <Section id="csv" title="Picks CSV">
      <Row label="Export" hint="Your picks and the model's pick for every game in a season.">
        <div className="flex flex-wrap items-center gap-2">
          <SelectField label="Season" value={season} onChange={(e) => setSeason(Number(e.target.value))}>
            {meta.seasons.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </SelectField>
          <Button onClick={exportCsv} loading={exporting}>
            Download CSV
          </Button>
        </div>
      </Row>
      <Row label="Import" hint="A CSV with game_id and my_pick columns. Past games are allowed.">
        <div className="space-y-3">
          {/* Opened by the button below; named so assistive tech can still identify it. */}
          <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={onFile} className="sr-only" id="csv-file" aria-label="Picks CSV file to import" tabIndex={-1} />
          <Button onClick={() => fileRef.current?.click()} loading={importing}>
            Choose CSV file
          </Button>
          {error && (
            <Notice tone="bad" title="Import failed">
              {error}
            </Notice>
          )}
          {result && (
            <Notice tone={result.skipped.length ? "warn" : "good"} title={`Imported ${result.imported} ${result.imported === 1 ? "pick" : "picks"}`}>
              {result.skipped.length > 0 ? (
                <>
                  Skipped {result.skipped.length}: {result.skipped.slice(0, 12).join(", ")}
                  {result.skipped.length > 12 ? ", and more" : ""}. Each named a game or team that is not in the schedule, or a game that has kicked off and already has a pick saved (that pick is kept).
                </>
              ) : (
                "No rows were skipped."
              )}
            </Notice>
          )}
        </div>
      </Row>
    </Section>
  );
}

const SAVED_KEY = "nflpi_offline_saved";

/** Prefetch the selected week and every game detail in it, so the app can be read with no connection. */
function OfflineSection() {
  const api = useApi();
  const qc = useQueryClient();
  const online = useOnline();
  const storageStatus = useStorageStatus();
  const { season, week } = useSelection();
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ season: number; week: number; at: string; games: number } | null>(null);

  useEffect(() => {
    try {
      const raw = safeGet(SAVED_KEY);
      if (raw) setSaved(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  async function save() {
    setError(null);
    setProgress({ done: 0, total: 1 });
    try {
      const w = await qc.fetchQuery({ queryKey: keys.week(season, week), queryFn: () => api.week(season, week), staleTime: 0 });
      const ids = w.games.map((g) => g.game_id);
      let done = 1;
      const total = ids.length + 1;
      setProgress({ done, total });
      const queue = [...ids];
      const worker = async () => {
        for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
          await qc.fetchQuery({ queryKey: keys.game(id), queryFn: () => api.game(id), staleTime: 0 });
          done++;
          setProgress({ done, total });
        }
      };
      await Promise.all([worker(), worker(), worker()]);
      const record = { season, week, at: new Date().toISOString(), games: ids.length };
      safeSet(SAVED_KEY, JSON.stringify(record));
      setSaved(record);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setProgress(null);
    }
  }

  return (
    <Section id="offline" title="Offline" note="Read the board and matchups with no connection. Picks made offline sync when you are back online.">
      <Row label="Storage">
        <p className="text-sm text-text-2">
          {storageStatus === "granted"
            ? "Protected from automatic clearing."
            : storageStatus === "denied"
              ? "Not protected. The browser may clear saved data when the phone is low on space."
              : "This browser does not say."}
        </p>
      </Row>
      <Row label={`Week ${week}, ${season}`} hint="Saves the week and every game in it on this device.">
        <div className="space-y-2">
          <Button onClick={save} loading={progress !== null} disabled={!online}>
            {progress ? `Saving ${progress.done}/${progress.total}` : "Save this week for offline"}
          </Button>
          {!online && <p className="text-xs text-warn">You are offline. Connect to save a week.</p>}
          {error && (
            <p role="alert" className="text-sm text-bad">
              Could not finish saving. {error}
            </p>
          )}
          {saved && !progress && (
            <p className="text-sm text-text-2" role="status">
              Saved Week {saved.week}, {saved.season} ({saved.games} games), {ago(saved.at)}.
            </p>
          )}
        </div>
      </Row>
    </Section>
  );
}

function ModelSection({ meta }: { meta: Meta }) {
  const fresh = useFreshness();
  const providers = useMemo(() => Object.entries(meta.ai_providers), [meta.ai_providers]);
  return (
    <>
      <Section
        id="freshness"
        title="Data freshness"
        note="When each source last updated successfully. Weather is shown for context and is not a model input, so a stale weather feed does not change a pick."
      >
        {fresh.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : fresh.isError ? (
          <ErrorState title="Could not load freshness" error={fresh.error} onRetry={() => fresh.refetch()} />
        ) : (
          <FreshnessTable data={fresh.data} />
        )}
      </Section>
      <Section id="model" title="Model and services">
        <Row label="Model">
          <p className="text-sm text-text">{meta.model_name ?? "No active model"}</p>
          <p className="mt-0.5 text-xs text-text-2">{meta.model_trained_through ? `Trained through the ${meta.model_trained_through} season.` : "Training range unknown."}</p>
        </Row>
        <Row label="AI providers" hint="Used for optional written research and questions.">
          <ul className="flex flex-wrap gap-2">
            {providers.map(([name, on]) => (
              <li key={name}>
                <Chip tone={on ? "good" : "neutral"}>
                  {name === "claude" ? "Claude" : name === "jev" ? "Jev" : name}: {on ? "configured" : "not configured"}
                </Chip>
              </li>
            ))}
          </ul>
          {providers.some(([, on]) => !on) && <p className="mt-2 text-xs text-subtle">Set ANTHROPIC_API_KEY / OPENROUTER_API_KEY on the server to enable them.</p>}
        </Row>
        <Row label="Server time">
          <p className="text-sm text-text-2">{new Date(meta.server_time).toLocaleString()}</p>
        </Row>
      </Section>
    </>
  );
}

export function SettingsView() {
  const q = useMeta();
  const meta = q.data;
  return (
    <div className="space-y-6">
      <PageHead kicker="Setup" title="Settings" sub="Access, alerts, picks data and system status." />
      {q.isPending && <Skeleton className="h-64 rounded-card" />}
      {q.isError && !meta && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {meta && (
        <>
          <AlertsSection meta={meta} />
          <OfflineSection />
          <LeaderSection meta={meta} />
          <CsvSection meta={meta} />
          <ModelSection meta={meta} />
          <PasskeysSection />
          <AccessSection />
        </>
      )}
    </div>
  );
}
