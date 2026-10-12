import { kickoffLabel, kickoffTime, pct } from "@nflpi/shared";

/** pct() from shared, with an en dash for missing values (design.md § 2.5). */
export function pctOr(p: number | null | undefined, digits = 0, empty = "–"): string {
  return p === null || p === undefined || Number.isNaN(p) ? empty : pct(p, digits);
}

export function num(n: number | null | undefined, digits = 1, empty = "–"): string {
  return n === null || n === undefined || Number.isNaN(n) ? empty : n.toFixed(digits);
}

export function signed(n: number | null | undefined, digits = 1, empty = "–"): string {
  if (n === null || n === undefined || Number.isNaN(n)) return empty;
  const s = Math.abs(n).toFixed(digits);
  return n < 0 ? `-${s}` : `+${s}`;
}

/** Percentage points from a 0-1 difference: 0.0205 -> "2.1" */
export function pts(diff: number, digits = 1): string {
  return Math.abs(diff * 100).toFixed(digits);
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

type Kickoff = { kickoff_utc: string; time_tbd: boolean };

/** Clock time of kickoff. The API stores midnight when the schedule has no time yet; that is shown as missing. */
export function kickoffClock(g: Kickoff): string {
  return g.time_tbd ? "Time TBD" : kickoffTime(g.kickoff_utc);
}

/** Day, date and clock time of kickoff, or the day and date with "Time TBD". */
export function kickoffWhen(g: Kickoff): string {
  if (!g.time_tbd) return kickoffLabel(g.kickoff_utc);
  return `${new Date(g.kickoff_utc).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}, Time TBD`;
}

export function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}

export function isIndoor(roof: string | null | undefined): boolean {
  return roof === "dome" || roof === "closed";
}

/** "Sun, Oct 5" */
export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}
