"use client";

import { ago, pct, type AIReport, type GameDetail, type MatchupReport, type Meta, type Provider } from "@nflpi/shared";
import { useGenerateReport } from "@/lib/queries";
import { Button, Chip, Notice, Section, errorMessage } from "@/components/ui";

export const PROVIDER_HINT: Record<Provider, string> = {
  claude: "Set ANTHROPIC_API_KEY on the server",
  jev: "Set OPENROUTER_API_KEY on the server",
};
export const PROVIDER_NAME: Record<Provider, string> = { claude: "Claude", jev: "Jev" };

function List({ title, items, tone }: { title: string; items: string[]; tone?: "good" | "bad" | "warn" }) {
  if (items.length === 0) return null;
  const c = tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : "text-text";
  return (
    <div>
      <h4 className={`text-xs font-semibold ${c}`}>{title}</h4>
      <ul className="mt-1.5 list-disc space-y-1 pl-4 text-sm text-text-2">
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  );
}

function Para({ title, text, note }: { title: string; text: string; note?: string }) {
  if (!text) return null;
  return (
    <div>
      <h4 className="text-xs font-semibold text-text">{title}</h4>
      <p className="mt-1 text-sm text-text-2">{text}</p>
      {note && <p className="mt-1 text-[11px] text-subtle">{note}</p>}
    </div>
  );
}

function ReportView({ report, meta }: { report: MatchupReport; meta: AIReport }) {
  const prob = report.statistical_win_probability > 1 ? report.statistical_win_probability / 100 : report.statistical_win_probability;
  return (
    <div className="space-y-5">
      <div>
        <p className="text-base font-semibold text-text">{report.headline}</p>
        <p className="mt-1 text-xs text-text-2">
          Report points to {report.recommended_winner}, citing the model&apos;s {pct(prob)} statistical win probability.
        </p>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <List title="Supporting factors" items={report.supporting_factors} tone="good" />
        <List title="Opposing factors" items={report.opposing_factors} tone="bad" />
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <Para title="Injury impact" text={report.injury_impact} />
        <Para title="Rest and schedule" text={report.rest_and_schedule} note="Rest days showed no proven effect in testing." />
        <Para title="Weather" text={report.weather_impact} />
        <Para title="Market view" text={report.market_view} />
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <List title="Key uncertainties" items={report.key_uncertainties} />
        <List title="What would change the pick" items={report.what_would_change_the_pick} />
      </div>
      {report.data_quality_warnings.length > 0 && (
        <Notice tone="warn" title="Data warnings">
          <ul className="list-disc space-y-0.5 pl-4">
            {report.data_quality_warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Notice>
      )}
      {report.sources.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text">Sources</h4>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {report.sources.map((s) => (
              <li key={s}>
                <Chip>{s}</Chip>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="border-t border-border pt-3 text-[11px] text-subtle">
        Written by {meta.provider} ({meta.model}), {ago(meta.created_at)}. AI research summarizes the evidence the model used. It does not change the model&apos;s probability.
      </p>
    </div>
  );
}

export function AiResearch({ game, ai }: { game: GameDetail; ai: Meta["ai_providers"] }) {
  const gen = useGenerateReport(game.game_id);
  const report = game.ai_report;
  const providers: Provider[] = ["claude", "jev"];
  const none = !ai.claude && !ai.jev;

  return (
    <Section
      id="ai"
      title="AI research"
      note="A written read of the same evidence, from a language model. Optional."
      action={
        <div className="flex flex-wrap gap-2">
          {providers.map((p) => (
            <Button
              key={p}
              size="sm"
              variant="secondary"
              disabled={!ai[p]}
              loading={gen.isPending && gen.variables === p}
              title={ai[p] ? undefined : PROVIDER_HINT[p]}
              onClick={() => gen.mutate(p)}
            >
              Generate with {PROVIDER_NAME[p]}
            </Button>
          ))}
        </div>
      }
    >
      {none ? (
        <Notice tone="info" title="AI providers are not configured">
          Set ANTHROPIC_API_KEY / OPENROUTER_API_KEY on the server to enable reports.
        </Notice>
      ) : (
        providers.some((p) => !ai[p]) && (
          <p className="mb-4 text-xs text-subtle">
            {providers
              .filter((p) => !ai[p])
              .map((p) => `${PROVIDER_NAME[p]} is off. ${PROVIDER_HINT[p]}.`)
              .join(" ")}
          </p>
        )
      )}
      {gen.isError && (
        <Notice tone="bad" title="Could not generate a report" className="mt-3">
          {errorMessage(gen.error)}
        </Notice>
      )}
      {gen.isPending && <p className="mt-3 text-sm text-text-2" role="status">Generating. This can take up to a minute.</p>}

      <div className={none || gen.isError || gen.isPending ? "mt-5" : ""}>
        {!report ? (
          !none && <p className="text-sm text-text-2">No report yet for this game. Generate one above.</p>
        ) : report.status === "failed" || !report.report ? (
          <Notice tone="bad" title={`Last report failed (${report.provider}, ${ago(report.created_at)})`}>
            {report.error ?? "The provider returned no valid report."}
          </Notice>
        ) : (
          <ReportView report={report.report} meta={report} />
        )}
      </div>
    </Section>
  );
}
