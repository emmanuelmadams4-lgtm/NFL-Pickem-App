"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useGame, useMeta } from "@/lib/queries";
import { EmptyState, ErrorState, Skeleton, cx } from "@/components/ui";
import { GameHeader, WinSplit } from "@/components/game/game-header";
import { Recommendation } from "@/components/game/recommendation";
import { Factors } from "@/components/game/factors";
import { TeamCompare } from "@/components/game/team-compare";
import { Injuries } from "@/components/game/injuries";
import { Schedule } from "@/components/game/schedule";
import { MarketSection } from "@/components/game/market";
import { AiResearch } from "@/components/game/ai-research";
import { Ask } from "@/components/game/ask";
import { History } from "@/components/game/history";
import { Meetings } from "@/components/game/meetings";

const SECTIONS = [
  { id: "factors", label: "Factors" },
  { id: "teams", label: "Teams" },
  { id: "injuries", label: "Injuries" },
  { id: "conditions", label: "Conditions" },
  { id: "market", label: "Market" },
  { id: "ai", label: "AI" },
  { id: "ask", label: "Ask" },
  { id: "history", label: "History" },
  { id: "meetings", label: "Meetings" },
];

/** Below the top bar and this tab row: the last section whose top has passed this line is the one in view. */
const SPY_LINE = 160;

/**
 * Pill section tabs (design.md § 0): sticky under the top bar, the section in view is the lime pill, jump on tap.
 * A tapped tab stays current while its jump scrolls (and when the page cannot scroll that far), until the next user scroll.
 */
function SectionNav() {
  const [active, setActive] = useState<string>(SECTIONS[0].id);
  const jumping = useRef(false);

  useEffect(() => {
    let frame = 0;
    const spy = () => {
      if (jumping.current) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (jumping.current) return;
        let current = SECTIONS[0].id;
        for (const s of SECTIONS) {
          const el = document.getElementById(s.id);
          if (el && el.getBoundingClientRect().top <= SPY_LINE) current = s.id;
        }
        setActive(current);
      });
    };
    const release = () => {
      jumping.current = false;
    };
    const gestures = ["wheel", "touchstart", "keydown", "scrollend"] as const;
    window.addEventListener("scroll", spy, { passive: true });
    gestures.forEach((g) => window.addEventListener(g, release, { passive: true }));
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", spy);
      gestures.forEach((g) => window.removeEventListener(g, release));
    };
  }, []);

  function jump(id: string) {
    const el = document.getElementById(id);
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    jumping.current = true;
    setActive(id);
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  return (
    <nav aria-label="Sections" className="sticky top-[var(--header-h)] z-20 -mx-4 bg-bg px-4 lg:mx-0 lg:px-0">
      <ul className="no-scrollbar flex gap-1.5 overflow-x-auto py-2">
        {SECTIONS.map((s) => (
          <li key={s.id} className="shrink-0">
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? "true" : undefined}
              onClick={(e) => {
                e.preventDefault();
                jump(s.id);
              }}
              className={cx(
                "inline-flex h-10 items-center rounded-full px-4 text-sm whitespace-nowrap transition-colors lg:h-9",
                active === s.id ? "bg-accent font-medium text-accent-ink" : "border border-border bg-surface text-text-2 hover:border-border-strong hover:text-text",
              )}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function GameSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading matchup" className="space-y-5">
      <Skeleton className="h-40 rounded-card" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          <Skeleton className="h-64 rounded-card" />
          <Skeleton className="h-80 rounded-card" />
        </div>
        <Skeleton className="h-[520px] rounded-card" />
      </div>
    </div>
  );
}

export function GameView() {
  const params = useSearchParams();
  const id = params.get("id");
  const q = useGame(id);
  const meta = useMeta().data;

  if (!id) {
    return (
      <EmptyState
        title="No game selected"
        hint="Open a game from the Week board to see its matchup."
        action={
          <Link href="/" className="text-sm text-accent-text underline underline-offset-2">
            Go to the Week board
          </Link>
        }
      />
    );
  }
  if (q.isPending) return <GameSkeleton />;
  if (q.isError && !q.data) return <ErrorState title="Could not load this matchup" error={q.error} onRetry={() => q.refetch()} />;
  const game = q.data;
  if (!game || !meta) return null;

  return (
    <div className="space-y-4 lg:space-y-5">
      <GameHeader game={game} />
      <WinSplit game={game} />
      {/* Phone: the pick panel comes right after the win tiles, then the section tabs. Desktop: tabs over the sections,
          the panel sticky beside them. */}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-6">
        <aside className="lg:sticky lg:top-[calc(var(--header-h)+16px)] lg:col-start-2 lg:row-start-1">
          <Recommendation game={game} />
        </aside>
        <div className="min-w-0 space-y-6 lg:col-start-1 lg:row-start-1">
          <SectionNav />
          <Factors game={game} />
          <TeamCompare game={game} />
          <Injuries game={game} />
          <Schedule game={game} />
          <MarketSection game={game} />
          <AiResearch game={game} ai={meta.ai_providers} />
          <Ask game={game} ai={meta.ai_providers} />
          <History game={game} />
          <Meetings game={game} />
        </div>
      </div>
    </div>
  );
}
