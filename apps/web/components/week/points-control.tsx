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
  if (points === null) return null;

  async function change(next: number | null) {
    if (busy) return;
    if (!navigator.onLine) {
      toast("Changing points needs a connection.", "bad");
      return;
    }
    setBusy(true);
    try {
      const week = next === null ? await api.clearPoints(game.game_id) : await api.setPoints(game.game_id, next);
      qc.setQueryData(keys.week(game.season, game.week), week);
    } catch (e) {
      toast(`Points not saved. ${errorMessage(e)}`, "bad");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
      <div>
        <p className="flex items-center gap-2 text-sm font-medium text-text">
          Points <span className="font-display text-[32px] leading-8">{points}</span>
          {locked && <Lock size={16} className="opacity-60" />}
        </p>
        {game.sheet.points_by === "user" && (
          <p className="text-label text-text-2">Your number · App says {game.sheet.app_points}</p>
        )}
      </div>
      <select
        aria-label={`Points for ${game.away.abbr} at ${game.home.abbr}`}
        value={points}
        disabled={locked || busy}
        onChange={(e) => void change(Number(e.target.value))}
        className="h-12 min-w-16 rounded-ctl border border-border-strong bg-elevated px-3 text-base text-text disabled:cursor-not-allowed disabled:opacity-60 lg:h-10"
      >
        {Array.from({ length: count }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}
      </select>
      {game.sheet.points_by === "user" && !locked && (
        <button type="button" onClick={() => void change(null)} disabled={busy} className="min-h-11 text-sm text-accent-text underline underline-offset-2">
          Use the app&apos;s number
        </button>
      )}
    </div>
  );
}
