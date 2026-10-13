"use client";

import { useRef, useState, type ChangeEvent } from "react";
import Link from "next/link";
import type { GroupImportResult } from "@nflpi/shared";
import { Button, Section, SelectField } from "@/components/ui";
import { useApi } from "@/lib/api";
import { MAX_UPLOAD_BYTES, TOO_LARGE_MESSAGE, uploadErrorMessage, uploadResultText } from "@/lib/group";
import { useMeta } from "@/lib/queries";

export function UploadPanel({ season, week, onSaved }: { season: number; week: number; onSaved: () => void }) {
  const api = useApi();
  const seasons = useMeta().data?.seasons ?? [season];
  const input = useRef<HTMLInputElement>(null);
  const sending = useRef(false);
  const [inputKey, setInputKey] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [chosenSeason, setChosenSeason] = useState(season);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GroupImportResult | null>(null);
  const [error, setError] = useState("");

  function openChooser() {
    if (!input.current) return;
    input.current.value = "";
    input.current.click();
  }

  function choose(e: ChangeEvent<HTMLInputElement>) {
    const next = e.target.files?.[0];
    setResult(null);
    setError("");
    setFile(null);
    if (!next) return;
    if (next.size > MAX_UPLOAD_BYTES) {
      setError(TOO_LARGE_MESSAGE);
      return;
    }
    setChosenSeason(season);
    setFile(next);
  }

  async function send() {
    if (!file || sending.current) return;
    sending.current = true;
    setLoading(true);
    setError("");
    try {
      const saved = await api.groupImport(chosenSeason, file);
      setFile(null);
      setInputKey((key) => key + 1);
      setResult(saved);
      onSaved();
    } catch (e) {
      setError(uploadErrorMessage(e));
    } finally {
      sending.current = false;
      setLoading(false);
    }
  }

  return (
    <Section title="Upload a file" note="Export your picks file or your weekly performance file from Yahoo, then choose it here.">
      <input key={inputKey} ref={input} type="file" accept=".csv,text/csv" aria-label="Choose a CSV file" className="sr-only" tabIndex={-1} onChange={choose} />

      {result && (
        <div role="status" data-testid="upload-result" className="mb-4 rounded-ctl border border-good/40 bg-good/10 px-4 py-3 text-sm text-text">
          {uploadResultText(result)}
          {result.season !== season && <Link href={`/group/?season=${result.season}&week=${week}`} className="ml-2 inline-block py-3 text-accent-text underline underline-offset-2">Show the {result.season} season</Link>}
        </div>
      )}
      {error && <>
        <div role="alert" data-testid="upload-error" className="mb-4 rounded-ctl border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-bad">{error}</div>
        <p className="-mt-2 mb-4 text-label text-subtle">Check that it is the picks file or the weekly performance file you exported from Yahoo.</p>
      </>}

      {!file && <Button type="button" variant="secondary" className="h-11 lg:h-9" onClick={openChooser}>Choose file</Button>}

      {file && (
        <div data-testid="upload-confirm" className="max-w-xl space-y-4 rounded-card border border-border bg-surface p-4">
          <p className="break-all text-sm text-text">{file.name} <span className="text-text-2">({Math.ceil(file.size / 1024)} KB)</span></p>
          <SelectField label="Season for this file" value={chosenSeason} disabled={loading} onChange={(e) => setChosenSeason(Number(e.target.value))}>
            {seasons.map((s) => <option key={s} value={s}>{s}</option>)}
          </SelectField>
          <div className="text-sm text-text">
            <p className="font-semibold">Saving to the {chosenSeason} season</p>
            <p className="mt-1 text-text-2">Check the season: the server cannot tell if the year is wrong.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="primary" className="h-11 lg:h-9" loading={loading} onClick={() => void send()}>Upload file</Button>
            <Button type="button" variant="secondary" className="h-11 lg:h-9" disabled={loading} onClick={openChooser}>Choose another file</Button>
          </div>
        </div>
      )}

    </Section>
  );
}
