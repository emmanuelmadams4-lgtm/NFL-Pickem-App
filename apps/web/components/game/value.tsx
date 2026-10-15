"use client";

import { type GameDetail } from "@nflpi/shared";
import { Section } from "@/components/ui";

type ValueRatingOut = GameDetail["value_ratings"][number];

const REASONS: Record<string, string> = {
  STALE_PRICE: "price too old to rate",
  NONPOSITIVE_EV: "no value at this price",
  NO_VALIDATION_HISTORY: "not yet shown to beat the market",
  QB_MISSING: "starting quarterback unknown",
  BELOW_FIRST_THRESHOLD: "value below the first star",
};

function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value}`;
}

function side(rating: ValueRatingOut, game: GameDetail): string {
  if (rating.market_type === "total") {
    return `${rating.selection === "over" ? "Over" : "Under"} ${rating.line}`;
  }
  const team = rating.selection === "home" ? game.home.abbr : game.away.abbr;
  if (rating.market_type === "spread" && rating.line !== null) {
    return `${team} ${signed(rating.selection === "home" ? rating.line : -rating.line)}`;
  }
  return team;
}

export function ValueSection({ game }: { game: GameDetail }) {
  const ratings = game.value_ratings ?? [];
  return (
    <Section id="value" title="Value">
      <p className="text-sm text-subtle">Ratings are not yet shown to beat the market.</p>
      {ratings.length === 0 ? (
        <p className="mt-3 text-sm text-text-2">No book prices to rate for this game.</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {ratings.map((rating, index) => (
            <li key={`${rating.sportsbook}-${rating.market_type}-${rating.selection}-${index}`} className="min-w-0 break-words rounded-card border border-border p-3 text-sm">
              <p className="font-medium text-text">
                {{ moneyline: "Win", spread: "Spread", total: "Total" }[rating.market_type]}: {side(rating, game)} · {signed(rating.price)} · {rating.sportsbook}
              </p>
              <p className="mt-1 text-text-2">
                {rating.status === "RATED" ? `${rating.stars} of 5 stars` : rating.status === "UNRATED" ? "Unrated" : "No bet"}
                {" · Expected value "}{signed(Math.round(rating.expected_value * 100))}%
              </p>
              {rating.reasons.length > 0 && <p className="mt-1 text-text-2">{rating.reasons.map((reason) => REASONS[reason] ?? reason).join(" · ")}</p>}
              <p className="mt-1 text-xs text-subtle">{rating.note}</p>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
