"use client";

import { UNCERTAINTY, ago, pct, pickProb, strengthLabel, type GameDetail, type Prediction, type Team } from "@nflpi/shared";
import { Bezel, Chip, Mark } from "@/components/ui";
import { TeamLogo } from "@/components/team";
import { PickButtons } from "@/components/pick-buttons";
import { BackfillChip, UncertaintyChip } from "@/components/prediction-bits";
import { useLocked } from "@/lib/clock";
import { pctOr } from "@/lib/fmt";

function Divider() {
  return <hr className="my-4 border-border" />;
}

function Figure({ label, value, emphasis, hint }: { label: string; value: string; emphasis?: boolean; hint?: string }) {
  return (
    <div className="min-w-0">
      <p className={emphasis ? "num-display text-2xl leading-8 font-semibold text-text" : "num-display text-2xl leading-8 font-semibold text-text-2"}>{value}</p>
      <p className="mt-0.5 text-[11px] leading-4 font-medium text-text">{label}</p>
      {hint && <p className="text-[11px] leading-4 text-subtle">{hint}</p>}
    </div>
  );
}

export function Recommendation({ game }: { game: GameDetail }) {
  const p: Prediction | null = game.prediction;
  const locked = useLocked(game);
  const pickTeam: Team | null = p ? (p.pick === game.home.abbr ? game.home : game.away) : null;
  const pickIsHome = p ? p.pick === game.home.abbr : false;
  const forPick = (home: number | null) => (home === null ? null : pickIsHome ? home : 1 - home);

  return (
    // The screen's one elevated surface. The core scrolls on short desktop windows while the panel stays sticky.
    <Bezel aria-label="Recommendation" coreClassName="p-5 lg:max-h-[calc(100dvh-var(--header-h)-96px)] lg:overflow-y-auto">
      {!p || !pickTeam ? (
        <div>
          <h2 className="text-heading">Model pick</h2>
          <p className="mt-2 text-sm text-text-2">No prediction has been computed for this game yet.</p>
          <Divider />
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-heading">Model pick</h2>
            {p.kind === "backfill" ? <BackfillChip /> : <Chip>Live</Chip>}
          </div>

          <div className="mt-3 flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <TeamLogo team={pickTeam} size={44} />
              <div className="min-w-0">
                <p className="text-2xl leading-7 font-semibold tracking-tight">{p.pick}</p>
                <p className="truncate text-xs text-text-2">{pickTeam.name}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="num-display text-display text-text">{pct(pickProb(p))}</p>
              <p className="mt-1 text-xs text-text-2">{strengthLabel(pickProb(p))}</p>
            </div>
          </div>

          <Divider />

          <div>
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-text">How reliable is this estimate?</p>
              <UncertaintyChip prediction={p} long />
            </div>
            {p.uncertainty_reasons.length > 0 ? (
              <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-text-2">
                {p.uncertainty_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-text-2">{UNCERTAINTY[p.uncertainty].label}. No specific reasons flagged.</p>
            )}
            <p className="mt-2 text-[11px] text-subtle">Uncertainty is separate from win probability: a pick can be likely and still unreliable.</p>
          </div>

          <Divider />

          <div>
            <p className="mb-2 text-xs text-text-2">Win probability for {p.pick}</p>
            <div className="grid grid-cols-3 gap-3">
              <Figure label="Final model" value={pct(pickProb(p))} emphasis />
              <Figure label="Stats-only" value={pctOr(forPick(p.stats_only_home_prob))} />
              <Figure label="Market" hint="no-vig" value={p.market_home_prob === null ? "No line" : pct(forPick(p.market_home_prob))} />
            </div>
            <p className="mt-3 text-[11px] text-subtle">Final model = stats + market blend when a line exists.</p>
          </div>

          {p.upset_flags.length > 0 && (
            <>
              <Divider />
              <div>
                <p className="text-xs font-medium text-warn">Upset watch</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-text-2">
                  {p.upset_flags.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            </>
          )}

          <p className="mt-4 text-[11px] text-subtle">
            Updated {ago(p.created_at)}, model {p.model_version}
          </p>
          {p.kind === "backfill" && (
            <p className="mt-1 text-[11px] text-subtle">Backfilled: computed after the fact using only pre-game data.</p>
          )}
          <Divider />
        </>
      )}

      <div>
        <p className="mb-2 text-xs font-medium text-text">Your pick</p>
        <PickButtons game={game} size="lg" />
        {locked && game.status === "scheduled" && <p className="mt-2 text-xs text-text-2">Locked at kickoff.</p>}
        {locked && game.status !== "final" && game.status !== "scheduled" && <p className="mt-2 text-xs text-text-2">Locked. The game has started.</p>}
        {!locked && !game.my_pick && <p className="mt-2 text-xs text-subtle">Tap a team to pick. Tap again to clear.</p>}
        {game.status === "final" && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
            {game.my_pick ? <Mark correct={game.my_pick_correct} who="Your pick" /> : <span className="text-xs text-subtle">You made no pick.</span>}
            <Mark correct={game.model_correct} who="Model pick" />
          </div>
        )}
      </div>
    </Bezel>
  );
}
