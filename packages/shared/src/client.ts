import type { components } from "./api-types";

type S = components["schemas"];
export type Meta = S["MetaOut"];
export type Week = S["WeekOut"];
export type WeekSummary = S["WeekSummary"];
export type GameSummary = S["GameSummary"];
export type GameDetail = S["GameDetail"];
export type Prediction = S["PredictionOut"];
export type Factor = S["Factor"];
export type Team = S["TeamOut"];
export type TeamForm = S["TeamForm"];
export type Injury = S["InjuryOut"];
export type Market = S["MarketOut"];
export type Weather = S["WeatherOut"];
export type Freshness = S["DatasetFreshness"];
export type Performance = S["PerformanceOut"];
export type WeekPerformance = S["WeekPerformance"];
export type Tally = S["Tally"];
export type Backtest = S["BacktestOut"];
export type AIReport = S["AIReportOut"];
export type MatchupReport = S["MatchupReport"];
export type AskAnswer = S["AskOut"];
export type Pick = S["PickOut"];
export type ImportResult = S["ImportResult"];
export type PushSubscriptionIn = S["PushSubscriptionIn"];
export type SettingsIn = S["SettingsIn"];
export type Provider = "claude" | "jev";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export interface ClientConfig {
  /** Server origin, e.g. "http://my-server.tailnet.ts.net:8000". Empty string = same origin. */
  baseUrl: string;
  token: string;
  fetch?: typeof fetch;
}

/** One typed client for web. Every call goes to our own backend only. */
export function createClient(config: ClientConfig) {
  const f = config.fetch ?? fetch;
  const base = config.baseUrl.replace(/\/+$/, "");

  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await f(`${base}/api${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${config.token}`,
        ...(init.body && typeof init.body === "string" && !path.endsWith("import")
          ? { "Content-Type": "application/json" }
          : {}),
        ...init.headers,
      },
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* keep statusText */
      }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    const type = res.headers.get("content-type") ?? "";
    return (type.includes("json") ? res.json() : res.text()) as Promise<T>;
  }

  return {
    health: () => call<S["HealthOut"]>("/health"),
    meta: () => call<Meta>("/meta"),
    week: (season: number, week: number) => call<Week>(`/weeks/${season}/${week}`),
    game: (gameId: string) => call<GameDetail>(`/games/${gameId}`),
    setPick: (gameId: string, team: string) =>
      call<Pick>(`/picks/${gameId}`, { method: "PUT", body: JSON.stringify({ team }) }),
    clearPick: (gameId: string) => call<void>(`/picks/${gameId}`, { method: "DELETE" }),
    exportPicks: (season: number) => call<string>(`/picks/export.csv?season=${season}`),
    importPicks: (csv: string) =>
      call<ImportResult>("/picks/import", { method: "POST", body: csv, headers: { "Content-Type": "text/csv" } }),
    performance: (season: number) => call<Performance>(`/performance/${season}`),
    backtest: () => call<Backtest>("/backtest"),
    report: (gameId: string, provider: Provider = "claude") =>
      call<AIReport>(`/games/${gameId}/report?provider=${provider}`, { method: "POST" }),
    ask: (gameId: string, question: string, provider: Provider = "claude") =>
      call<AskAnswer>(`/games/${gameId}/ask`, { method: "POST", body: JSON.stringify({ question, provider }) }),
    /** Pass `PushSubscription.toJSON()` from the browser. */
    pushSubscribe: (subscription: PushSubscriptionIn) =>
      call<void>("/push/subscribe", { method: "POST", body: JSON.stringify(subscription) }),
    pushUnsubscribe: (endpoint: string) =>
      call<void>(`/push/subscribe?endpoint=${encodeURIComponent(endpoint)}`, { method: "DELETE" }),
    /** Only the fields you pass are changed. reminder_minutes: 0 = off. */
    updateSettings: (settings: SettingsIn) => call<Meta>("/settings", { method: "PUT", body: JSON.stringify(settings) }),
    refresh: () => call<{ started: boolean; reason?: string }>("/refresh", { method: "POST" }),
    freshness: () => call<Freshness[]>("/freshness"),
  };
}

export type Api = ReturnType<typeof createClient>;

/** Query keys shared by web so caches line up. */
export const keys = {
  meta: ["meta"] as const,
  week: (season: number, week: number) => ["week", season, week] as const,
  game: (gameId: string) => ["game", gameId] as const,
  performance: (season: number) => ["performance", season] as const,
  backtest: ["backtest"] as const,
};
