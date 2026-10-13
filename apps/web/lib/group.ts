import { useCallback, useEffect, useState } from "react";
import { ApiError, type GroupImportResult, type GroupShares, type GroupStandings } from "@nflpi/shared";
import { errorMessage } from "@/components/ui";
import { num, pctOr } from "@/lib/fmt";
import { useApi } from "@/lib/api";

export const MAX_UPLOAD_BYTES = 1_000_000;
export const TOO_LARGE_MESSAGE = "That file is too large. The limit is 1 MB.";
export const SERVER_ERROR_MESSAGE = "The server could not save this file. Try again.";

export function uploadErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 413) return TOO_LARGE_MESSAGE;
    if (e.status === 500) return SERVER_ERROR_MESSAGE;
    return e.message;
  }
  return errorMessage(e);
}

export function uploadResultText(r: GroupImportResult): string {
  return r.kind === "picks"
    ? `Picks file saved: ${r.rows} picks for the ${r.season} season.`
    : `Weekly performance file saved: ${r.rows} member-weeks for the ${r.season} season.`;
}

export type Load<T> = { status: "loading" } | { status: "error"; error: unknown } | { status: "ok"; data: T };

export function useGroupData(season: number, week: number): {
  standings: Load<GroupStandings>;
  shares: Load<GroupShares>;
  reload: () => void;
} {
  const api = useApi();
  const [reloadKey, setReloadKey] = useState(0);
  const [standings, setStandings] = useState<Load<GroupStandings>>({ status: "loading" });
  const [shares, setShares] = useState<Load<GroupShares>>({ status: "loading" });
  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  useEffect(() => {
    let cancelled = false;
    setStandings({ status: "loading" });
    setShares({ status: "loading" });
    void api.groupStandings(season, week).then(
      (data) => { if (!cancelled) setStandings({ status: "ok", data }); },
      (error: unknown) => { if (!cancelled) setStandings({ status: "error", error }); },
    );
    void api.groupShares(season, week).then(
      (data) => { if (!cancelled) setShares({ status: "ok", data }); },
      (error: unknown) => { if (!cancelled) setShares({ status: "error", error }); },
    );
    return () => { cancelled = true; };
  }, [api, season, week, reloadKey]);

  return { standings, shares, reload };
}

export function shareLine(
  side: { picks: number; share: number | null; avg_confidence: number | null },
  picked: number,
): { count: string; share: string; avg: string } {
  return {
    count: `${side.picks} of ${picked}`,
    share: pctOr(side.share, 0),
    avg: side.avg_confidence === null ? "avg –" : `avg ${num(side.avg_confidence, 1)} pts`,
  };
}
