"use client";

import { ago, type Freshness, type GameDetail } from "@nflpi/shared";
import { Section } from "@/components/ui";
import { useFreshness } from "@/lib/queries";
import { isIndoor, kickoffWhen } from "@/lib/fmt";

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="mt-0.5 text-sm text-text">{children}</dd>
    </div>
  );
}

function cap(s: string | null | undefined) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

/** "Weather source is down. Last error: ... Last update: never." The age and error come from the ingestion run log. */
function outageText(d: Freshness): string {
  return [`Weather source is down.`, d.last_error ? `Last error: ${d.last_error}.` : null, `Last update: ${d.last_success ? ago(d.last_success) : "never"}.`]
    .filter(Boolean)
    .join(" ");
}

function WeatherFact({ game, outage }: { game: GameDetail; outage: Freshness | null }) {
  const w = game.weather;
  if (isIndoor(game.roof)) return <span>Indoor</span>;
  if (!w) return <span className="text-text-2">{outage ? "No reading: the weather source is down" : "No forecast yet"}</span>;
  const parts = [
    w.temp_f != null ? `${Math.round(w.temp_f)}°F` : null,
    w.wind_mph != null ? `wind ${Math.round(w.wind_mph)} mph` : null,
    w.gust_mph != null ? `gusts ${Math.round(w.gust_mph)} mph` : null,
    w.precip_prob != null ? `${Math.round(w.precip_prob)}% precip` : null,
    w.precip_in != null && w.precip_in > 0 ? `${w.precip_in.toFixed(2)} in` : null,
  ].filter(Boolean);
  return (
    <span>
      <span className="text-xs text-subtle">{w.kind === "forecast" ? "Forecast" : "Observed"}{w.observed_at ? `, ${ago(w.observed_at)}` : ""}</span>
      <span className="block">{parts.length ? parts.join(", ") : "No readings"}</span>
    </span>
  );
}

export function Schedule({ game }: { game: GameDetail }) {
  const a = game.away_form;
  const h = game.home_form;
  const weather = useFreshness().data?.find((d) => d.dataset === "weather");
  const outage = weather && (weather.stale || weather.last_error) ? weather : null;
  return (
    <Section id="conditions" title="Schedule and conditions">
      {outage && (
        <p role="note" className="mb-4 text-sm text-warn">
          {outageText(outage)}
        </p>
      )}
      <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2 xl:grid-cols-3">
        <Fact label="Kickoff (your local time)">{kickoffWhen(game)}</Fact>
        <Fact label="Day">{game.weekday}</Fact>
        <Fact label="Venue">
          {game.stadium ?? "To be confirmed"}
          {game.neutral_site && <span className="block text-xs text-subtle">Neutral site</span>}
        </Fact>
        <Fact label="Roof and surface">
          {[game.roof ? cap(game.roof) : "Roof unknown", game.surface ? cap(game.surface) : "surface unknown"].join(", ")}
        </Fact>
        <Fact label="Rest days">
          {game.away.abbr} {a.rest_days ?? "–"}, {game.home.abbr} {h.rest_days ?? "–"}
          <span className="mt-0.5 block text-[11px] text-subtle">Rest days showed no proven effect in testing.</span>
        </Fact>
        <Fact label="Weather">
          <WeatherFact game={game} outage={outage} />
        </Fact>
      </dl>
    </Section>
  );
}
