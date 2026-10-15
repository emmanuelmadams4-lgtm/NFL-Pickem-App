"use client";

import { type GameDetail } from "@nflpi/shared";
import { Chip, Section } from "@/components/ui";

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
    <Section id="value" title="Value" note={ratings.length ? "Ratings are not yet shown to beat the market." : undefined}>
      {ratings.length === 0 ? (
        <p className="text-sm text-text-2">
          No book prices to rate for this game. Spread and total prices are rated only at the simulator&apos;s line.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {ratings.map((rating) => (
            <li
              key={`${rating.sportsbook}-${rating.market_type}-${rating.selection}`}
              className="min-w-0 break-words py-4 first:pt-0 last:pb-0"
            >
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                <p className="min-w-0 break-words text-sm font-medium text-text">
                  {{ moneyline: "Win", spread: "Spread", total: "Total" }[rating.market_type]}: {side(rating, game)}
                  <span aria-hidden="true"> · </span>{signed(rating.price)}
                  <span aria-hidden="true"> · </span><span className="text-text-2">{rating.sportsbook}</span>
                </p>
                <Chip tone={rating.status === "RATED" ? "accent" : "neutral"}>
                  {rating.status === "RATED" ? `${rating.stars} of 5 stars` : rating.status === "UNRATED" ? "Unrated" : "No bet"}
                </Chip>
              </div>
              {rating.reasons.length > 0 && (
                <p className="mt-1 text-sm text-text-2">
                  {rating.reasons.map((reason, index) => (
                    <span key={`${reason}-${index}`}>
                      {index > 0 && <span aria-hidden="true"> · </span>}
                      {Object.hasOwn(REASONS, reason) ? REASONS[reason] : reason}
                    </span>
                  ))}
                </p>
              )}
              <p className="mt-1 text-xs text-subtle">
                Expected value <span className="tabular-nums text-text">{signed(Math.round(rating.expected_value * 100))}%</span>
              </p>
              <p className="mt-1 text-xs leading-snug text-subtle">{rating.note}</p>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
