"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { keys, type GameSummary } from "@nflpi/shared";
import { useApi } from "@/lib/api";
import { useLocked } from "@/lib/clock";
import { useToast } from "@/components/toast";
import { errorMessage } from "@/components/ui";
import { Lock } from "@/components/icons";

export function PointsControl({ game, count }: { game: GameSummary; count: number }) {
  const api = useApi();
  const qc = useQueryClient();
  const { toast } = useToast();
  const locked = useLocked(game);
  const [busy, setBusy] = useState(false);
  const points = game.sheet.my_points;
  if (game.status === "postponed" || (points === null && locked)) return null; // past games from before the sheet existed have no points

  async function change(next: number | null) {
    if (busy) return;
    if (!navigator.onLine) {
      toast("Changing points needs a connection.", "bad");
      return;
    }
    setBusy(true);
    try {
      const previous = qc.getQueryData<{ games: GameSummary[] }>(keys.week(game.season, game.week));
      const week = next === null ? await api.clearPoints(game.game_id) : await api.setPoints(game.game_id, next);
      qc.setQueryData(keys.week(game.season, game.week), week);
      if (next === null) {
        toast(`${game.away.abbr} @ ${game.home.abbr} is back to the model's number, ${week.games.find((g) => g.game_id === game.game_id)?.sheet.my_points ?? "–"}.`);
      } else {
        const moved = previous?.games.find((g) => g.game_id !== game.game_id && g.sheet.my_points === next);
        toast(moved
          ? `${game.away.abbr} @ ${game.home.abbr} is now ${next}. ${moved.away.abbr} @ ${moved.home.abbr} is now ${week.games.find((g) => g.game_id === moved.game_id)?.sheet.my_points}.`
          : `${game.away.abbr} @ ${game.home.abbr} is now ${next}.`);
      }
    } catch (e) {
      toast(`Points not saved. ${errorMessage(e)}`, "bad");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative z-10 lg:border-t lg:border-border lg:pt-3">
      <div className="flex flex-wrap items-center gap-3">
        {points === null ? <span className="text-sm font-medium text-text">Points</span> : <label htmlFor={`points-${game.game_id}`} className="text-sm font-medium text-text">Points</label>}
        {points === null ? <span className="text-text-2">– <span className="text-label">No points yet</span></span> : <select id={`points-${game.game_id}`}
        aria-label={`Points for ${game.away.abbr} at ${game.home.abbr}`}
        value={points ?? ""}
        disabled={locked || busy}
        onChange={(e) => void change(Number(e.target.value))}
        className="h-12 min-w-16 rounded-ctl border border-border-strong bg-elevated px-3 text-base text-text disabled:cursor-not-allowed disabled:opacity-60 lg:h-10"
      >
          {Array.from({ length: count }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}
        </select>}
        {locked && <span className="flex items-center gap-1 text-label text-text-2"><Lock size={16} /> Locked</span>}
      </div>
      <div className="pt-1 text-label text-text-2">
        {game.sheet.points_by === "user" && <span>Your number. Model says {game.sheet.app_points}. </span>}
        {game.sheet.points_by === "user" && !locked && <button type="button" onClick={() => void change(null)} disabled={busy} className="min-h-10 text-accent-text underline underline-offset-2">Use the model&apos;s number</button>}
      </div>
    </div>
  );
}
