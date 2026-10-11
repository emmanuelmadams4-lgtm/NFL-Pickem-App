"use client";

import { useId, useState } from "react";
import { ago, type GameDetail, type Meta, type Provider } from "@nflpi/shared";
import { useAsk } from "@/lib/queries";
import { Button, Notice, Section, Segmented, errorMessage } from "@/components/ui";
import { PROVIDER_HINT, PROVIDER_NAME } from "@/components/game/ai-research";

export function Ask({ game, ai }: { game: GameDetail; ai: Meta["ai_providers"] }) {
  const ask = useAsk(game.game_id);
  const id = useId();
  const [q, setQ] = useState("");
  const [provider, setProvider] = useState<Provider>(ai.claude || !ai.jev ? "claude" : "jev");
  const enabled = ai[provider];
  const none = !ai.claude && !ai.jev;

  const suggestions = [
    `What would have to change for ${game.prediction?.pick === game.home.abbr ? game.away.abbr : game.home.abbr} to be the better pick?`,
    "Which injury matters most here and why?",
    "Why do the stats model and the market differ?",
  ];

  return (
    <Section id="ask" title="Ask a question" note="Answers use only this game's evidence from the app.">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim() && enabled) ask.mutate({ question: q.trim(), provider });
        }}
        className="space-y-3"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label htmlFor={id} className="text-sm font-medium text-text">
            Your question
          </label>
          <Segmented
            label="Provider"
            value={provider}
            onChange={setProvider}
            options={[
              { value: "claude", label: "Claude", disabled: !ai.claude },
              { value: "jev", label: "Jev", disabled: !ai.jev },
            ]}
          />
        </div>
        <textarea
          id={id}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          rows={3}
          disabled={none}
          placeholder="For example: why is the model lower on this team than the market?"
          className="w-full resize-y rounded-ctl border border-border bg-elevated px-3 py-2 text-base text-text lg:text-sm placeholder:text-subtle hover:border-muted disabled:cursor-not-allowed disabled:opacity-60"
        />
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              disabled={none}
              onClick={() => setQ(s)}
              className="rounded-chip border border-border px-2 py-1 text-left text-[11px] text-text-2 hover:border-muted hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" variant="primary" disabled={!q.trim() || !enabled} loading={ask.isPending}>
            Ask {PROVIDER_NAME[provider]}
          </Button>
          {!enabled && (
            <span className="text-xs text-subtle">
              {none ? "AI providers are not configured. Set ANTHROPIC_API_KEY / OPENROUTER_API_KEY on the server." : `${PROVIDER_NAME[provider]} is off. ${PROVIDER_HINT[provider]}.`}
            </span>
          )}
        </div>
      </form>

      <div aria-live="polite" className="mt-4">
        {ask.isError && (
          <Notice tone="bad" title="Could not get an answer">
            {errorMessage(ask.error)}
          </Notice>
        )}
        {ask.data && (
          <div className="rounded-ctl border border-border bg-elevated p-4">
            <p className="whitespace-pre-wrap text-sm text-text">{ask.data.answer}</p>
            <p className="mt-3 text-[11px] text-subtle">
              {ask.data.provider} ({ask.data.model}), {ago(ask.data.created_at)}
            </p>
          </div>
        )}
      </div>
    </Section>
  );
}
