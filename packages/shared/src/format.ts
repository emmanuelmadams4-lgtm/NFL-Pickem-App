import type { Freshness, GameSummary, Prediction } from "./client";

/** 0.634 -> "63%" */
export function pct(p: number | null | undefined, digits = 0): string {
  if (p === null || p === undefined || Number.isNaN(p)) return "—";
  return `${(p * 100).toFixed(digits)}%`;
}

/** Probability that the recommended pick wins. */
export function pickProb(p: Prediction): number {
  return Math.max(p.home_win_prob, p.away_win_prob);
}

export const UNCERTAINTY = {
  low: { label: "Low uncertainty", short: "Low", tone: "good" },
  moderate: { label: "Moderate uncertainty", short: "Moderate", tone: "warn" },
  high: { label: "High uncertainty", short: "High", tone: "bad" },
} as const;

/** Plain-words strength of a pick, separate from how reliable the estimate is. */
export function strengthLabel(prob: number): string {
  if (prob >= 0.8) return "Strong favorite";
  if (prob >= 0.65) return "Clear favorite";
  if (prob >= 0.55) return "Slight favorite";
  return "Toss-up";
}

/** "2h ago", "3d ago", "just now" */
export function ago(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "never";
  const mins = Math.round((now.getTime() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function kickoffLabel(iso: string, timeZone?: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  });
}

export function kickoffTime(iso: string, timeZone?: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", timeZone });
}

export function kickoffDay(iso: string, timeZone?: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric", timeZone });
}

export function moneyline(ml: number | null | undefined): string {
  if (ml === null || ml === undefined) return "—";
  return ml > 0 ? `+${ml}` : `${ml}`;
}

export function staleDatasets(freshness: Freshness[]): string[] {
  return freshness.filter((f) => f.stale).map((f) => f.dataset);
}

export type SortKey = "kickoff" | "confidence_desc" | "confidence_asc" | "uncertainty" | "upset" | "injuries" | "market_gap";

export const SORTS: { key: SortKey; label: string }[] = [
  { key: "kickoff", label: "Kickoff" },
  { key: "confidence_desc", label: "Most confident" },
  { key: "confidence_asc", label: "Closest games" },
  { key: "uncertainty", label: "Most uncertain" },
  { key: "upset", label: "Upset watch" },
  { key: "injuries", label: "Injury impact" },
  { key: "market_gap", label: "Model vs market gap" },
];

const UNC_RANK = { low: 0, moderate: 1, high: 2 } as const;

function marketGap(g: GameSummary): number {
  const p = g.prediction;
  if (!p || p.market_home_prob === null || p.stats_only_home_prob === null) return -1;
  return Math.abs(p.stats_only_home_prob - p.market_home_prob);
}

/** Shared sort for the week board (web table and mobile cards). */
export function sortGames(games: GameSummary[], key: SortKey): GameSummary[] {
  const prob = (g: GameSummary) => (g.prediction ? pickProb(g.prediction) : 0.5);
  const by: Record<SortKey, (a: GameSummary, b: GameSummary) => number> = {
    kickoff: (a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc),
    confidence_desc: (a, b) => prob(b) - prob(a),
    confidence_asc: (a, b) => prob(a) - prob(b),
    uncertainty: (a, b) =>
      (b.prediction ? UNC_RANK[b.prediction.uncertainty] : -1) - (a.prediction ? UNC_RANK[a.prediction.uncertainty] : -1),
    upset: (a, b) => (b.prediction?.upset_flags.length ?? 0) - (a.prediction?.upset_flags.length ?? 0) || marketGap(b) - marketGap(a),
    injuries: (a, b) => b.qb_alerts.length - a.qb_alerts.length || b.injury_count - a.injury_count,
    market_gap: (a, b) => marketGap(b) - marketGap(a),
  };
  return [...games].sort((a, b) => by[key](a, b) || a.kickoff_utc.localeCompare(b.kickoff_utc));
}

/** Who the market favors, with its probability, or null without a line. */
export function marketFavorite(g: GameSummary): { team: string; prob: number } | null {
  const m = g.prediction?.market_home_prob;
  if (m === null || m === undefined) return null;
  return m >= 0.5 ? { team: g.home.abbr, prob: m } : { team: g.away.abbr, prob: 1 - m };
}

export function needsAttention(g: GameSummary): boolean {
  return g.status === "scheduled" && !!g.prediction && (g.prediction.uncertainty === "high" || g.prediction.upset_flags.length > 0);
}

export function resultLabel(g: GameSummary): string {
  if (g.status !== "final") return g.status === "in_progress" ? "In progress" : "";
  return `${g.away.abbr} ${g.away_score} – ${g.home_score} ${g.home.abbr}`;
}
