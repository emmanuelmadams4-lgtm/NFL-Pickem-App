"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import { useToast } from "@/components/toast";
import { FreshnessIndicator } from "@/components/freshness";
import { OfflineBanner, PickSync, PushKeepAlive } from "@/components/pwa";
import { SeasonPicker, WeekPicker } from "@/components/pickers";
import { Button, cx, errorMessage } from "@/components/ui";
import { BarChart, Calendar, Gear, Refresh } from "@/components/icons";
import { useOnline } from "@/lib/sync";

const REFRESH_WAIT_MS = 20_000;

function RefreshButton() {
  const api = useApi();
  const qc = useQueryClient();
  const online = useOnline();
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => () => void (timer.current && window.clearTimeout(timer.current)), []);

  async function run() {
    setBusy(true);
    try {
      const r = await api.refresh();
      if (!r.started) {
        toast(r.reason ?? "A refresh is already running.", "info");
        setBusy(false);
        return;
      }
      timer.current = window.setTimeout(() => {
        qc.invalidateQueries();
        setBusy(false);
        toast("Data refreshed.", "good");
      }, REFRESH_WAIT_MS);
    } catch (e) {
      toast(`Refresh failed. ${errorMessage(e)}`, "bad");
      setBusy(false);
    }
  }

  return (
    // Phones: icon only (the words stay as its accessible name) so the bar fits at 320px.
    <Button size="sm" onClick={run} loading={busy} disabled={!online} aria-live="polite" className="max-lg:h-10 max-sm:w-10 max-sm:px-0">
      {!busy && <Refresh size={16} className="sm:hidden" />}
      <span className="max-sm:sr-only">{busy ? "Refreshing…" : "Refresh data"}</span>
    </Button>
  );
}

const DESKTOP_NAV = [
  { label: "Week", match: (p: string) => p === "/" || p.startsWith("/game") || p.startsWith("/sheet") },
  { label: "Results", match: (p: string) => p.startsWith("/performance") },
  { label: "Backtest", match: (p: string) => p.startsWith("/backtest") },
  { label: "Settings", match: (p: string) => p.startsWith("/settings") },
];

const TABS = [
  { label: "Week", Icon: Calendar, match: (p: string) => p === "/" || p.startsWith("/game") || p.startsWith("/sheet") },
  { label: "Results", Icon: BarChart, match: (p: string) => p.startsWith("/performance") || p.startsWith("/backtest") },
  { label: "Settings", Icon: Gear, match: (p: string) => p.startsWith("/settings") },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const { qs, season } = useSelection();
  const onBoard = pathname === "/";
  const onPerformance = pathname.startsWith("/performance");

  const hrefs: Record<string, string> = {
    Week: `/${qs}`,
    Results: `/performance/?season=${season}`,
    Backtest: "/backtest/",
    Settings: "/settings/",
  };

  return (
    <div className="min-h-[100dvh]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-full focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink">
        Skip to content
      </a>
      <PickSync />
      <PushKeepAlive />

      <header className="sticky top-0 z-30 border-b border-border bg-bg/90 pt-[env(safe-area-inset-top)] backdrop-blur supports-[backdrop-filter]:bg-bg/80">
        <div className="mx-auto flex min-h-[52px] max-w-[1360px] items-center gap-x-3 px-4 sm:gap-x-6 lg:min-h-14 lg:px-5">
          <Link href={`/${qs}`} className="flex items-center gap-2 text-[15px] font-semibold tracking-tight whitespace-nowrap text-text">
            {/* eslint-disable-next-line @next/next/no-img-element -- static export; the owner's app icon (D41) */}
            <img src="/icons/icon-192.png" alt="" width={28} height={28} className="size-7 rounded-[8px]" />
            <span className="max-[379px]:sr-only">
              Pick&apos;em <span className="text-text-2">Intel</span>
            </span>
          </Link>
          <nav aria-label="Primary" className="hidden gap-1 rounded-full border border-border bg-surface p-1 lg:flex">
            {DESKTOP_NAV.map((n) => {
              const active = n.match(pathname);
              return (
                <Link
                  key={n.label}
                  href={hrefs[n.label]}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "rounded-full px-4 py-1.5 text-sm transition-colors",
                    active ? "bg-accent font-medium text-accent-ink" : "text-text-2 hover:bg-elevated hover:text-text",
                  )}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2 lg:gap-3">
            {onBoard && <WeekPicker className="hidden lg:flex" />}
            {onPerformance && <SeasonPicker className="hidden lg:inline-flex" />}
            <FreshnessIndicator />
            <RefreshButton />
          </div>
        </div>
        <OfflineBanner />
      </header>

      <main id="main" className="mx-auto w-full max-w-[1360px] px-4 pt-4 pb-[calc(96px+env(safe-area-inset-bottom))] lg:px-5 lg:pt-6 lg:pb-6">
        {children}
      </main>
      <footer className="mx-auto hidden max-w-[1360px] px-5 pt-2 pb-10 text-xs text-subtle lg:block">
        Probabilities are estimates, not guarantees. Uncertainty says how reliable an estimate is; it is not the same as win probability.
      </footer>

      {/* Phone and tablet: a floating pill tab bar 12px above the safe area (design.md § 0). The active tab is a lime pill
          with icon and label; the others are icon-only circles that keep their name in aria-label. */}
      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-[calc(12px+env(safe-area-inset-bottom))] z-30 mx-auto w-fit rounded-full border border-border bg-elevated/90 p-1.5 shadow-[var(--shadow-float)] backdrop-blur supports-[backdrop-filter]:bg-elevated/80 lg:hidden"
      >
        <ul className="flex items-center gap-1.5">
          {TABS.map((t) => {
            const active = t.match(pathname);
            return (
              <li key={t.label}>
                <Link
                  href={hrefs[t.label]}
                  aria-current={active ? "page" : undefined}
                  aria-label={active ? undefined : t.label}
                  className={cx(
                    "flex h-12 items-center justify-center gap-2 rounded-full transition-colors",
                    active ? "bg-accent px-5 text-[15px] font-semibold text-accent-ink" : "w-12 bg-surface text-text-2 hover:text-text",
                  )}
                >
                  <t.Icon size={20} />
                  {active && t.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
