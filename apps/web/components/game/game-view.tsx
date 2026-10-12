"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useGame, useMeta } from "@/lib/queries";
import { EmptyState, ErrorState, Skeleton, cx } from "@/components/ui";
import { GameHeader } from "@/components/game/game-header";
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
  { id: "ai", label: "AI research" },
  { id: "ask", label: "Ask" },
  { id: "history", label: "History" },
  { id: "meetings", label: "Meetings" },
];

/** Section chips: sticky under the top bar, highlight the section in view, jump on tap. */
function SectionNav() {
  const [active, setActive] = useState<string>(SECTIONS[0].id);

  useEffect(() => {
    const els = SECTIONS.map((s) => document.getElementById(s.id)).filter((e): e is HTMLElement => !!e);
    if (els.length === 0 || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-110px 0px -65% 0px", threshold: 0 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  function jump(id: string) {
    const el = document.getElementById(id);
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    setActive(id);
  }

  return (
    <nav
      aria-label="Matchup sections"
      className="sticky top-[var(--header-h)] z-20 -mx-4 border-b border-border bg-bg/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-bg/80 lg:-mx-5 lg:px-5"
    >
      <ul className="no-scrollbar flex gap-1 overflow-x-auto py-2">
        {SECTIONS.map((s) => (
          <li key={s.id} className="shrink-0">
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? "location" : undefined}
              onClick={(e) => {
                e.preventDefault();
                jump(s.id);
              }}
              className={cx(
                "inline-flex h-9 items-center rounded-ctl px-3 text-sm whitespace-nowrap transition-colors lg:h-8",
                active === s.id ? "bg-elevated font-medium text-text" : "text-text-2 hover:bg-elevated/70 hover:text-text",
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
          <Link href="/" className="text-sm text-accent underline underline-offset-2">
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
      <SectionNav />
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-6">
        <aside className="lg:sticky lg:top-[calc(var(--header-h)+64px)] lg:col-start-2 lg:row-start-1">
          <Recommendation game={game} />
        </aside>
        <div className="min-w-0 space-y-6 lg:col-start-1 lg:row-start-1">
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
