"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import { useSelection } from "@/lib/selection";
import { useToast } from "@/components/toast";
import { FreshnessIndicator } from "@/components/freshness";
import { OfflineBanner, PickSync } from "@/components/pwa";
import { SeasonPicker, WeekPicker } from "@/components/pickers";
import { Button, cx, errorMessage } from "@/components/ui";
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
    <Button size="sm" onClick={run} loading={busy} disabled={!online} aria-live="polite" className="max-lg:h-10">
      {busy ? "Refreshing…" : "Refresh data"}
    </Button>
  );
}

const DESKTOP_NAV = [
  { label: "Week", match: (p: string) => p === "/" || p.startsWith("/game") },
  { label: "Performance", match: (p: string) => p.startsWith("/performance") },
  { label: "Backtest", match: (p: string) => p.startsWith("/backtest") },
  { label: "Settings", match: (p: string) => p.startsWith("/settings") },
];

const TABS = [
  { label: "Week", match: (p: string) => p === "/" || p.startsWith("/game") },
  { label: "Results", match: (p: string) => p.startsWith("/performance") || p.startsWith("/backtest") },
  { label: "Settings", match: (p: string) => p.startsWith("/settings") },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const { qs, season } = useSelection();
  const onBoard = pathname === "/";
  const onPerformance = pathname.startsWith("/performance");

  const hrefs: Record<string, string> = {
    Week: `/${qs}`,
    Performance: `/performance/?season=${season}`,
    Results: `/performance/?season=${season}`,
    Backtest: "/backtest/",
    Settings: "/settings/",
  };

  return (
    <div className="min-h-[100dvh]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-ctl focus:bg-accent-solid focus:px-3 focus:py-2 focus:text-white">
        Skip to content
      </a>
      <PickSync />

      <header className="sticky top-0 z-30 border-b border-border bg-surface/90 pt-[env(safe-area-inset-top)] backdrop-blur supports-[backdrop-filter]:bg-surface/80">
        <div className="mx-auto flex min-h-[52px] max-w-[1360px] items-center gap-x-6 px-4 lg:min-h-14 lg:px-5">
          <Link href={`/${qs}`} className="text-[15px] font-semibold tracking-tight whitespace-nowrap text-text">
            Pick&apos;em <span className="text-text-2">Intel</span>
          </Link>
          <nav aria-label="Primary" className="hidden gap-1 lg:flex">
            {DESKTOP_NAV.map((n) => {
              const active = n.match(pathname);
              return (
                <Link
                  key={n.label}
                  href={hrefs[n.label]}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "rounded-ctl px-3 py-1.5 text-sm transition-colors",
                    active ? "bg-elevated font-medium text-text" : "text-text-2 hover:bg-elevated/70 hover:text-text",
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

      <main id="main" className="mx-auto w-full max-w-[1360px] px-4 pt-4 pb-[calc(88px+env(safe-area-inset-bottom))] lg:px-5 lg:pt-6 lg:pb-6">
        {children}
      </main>
      <footer className="mx-auto hidden max-w-[1360px] px-5 pt-2 pb-10 text-xs text-subtle lg:block">
        Probabilities are estimates, not guarantees. Uncertainty says how reliable an estimate is; it is not the same as win probability.
      </footer>

      <nav
        aria-label="Primary"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur supports-[backdrop-filter]:bg-surface/85 lg:hidden"
      >
        <ul className="mx-auto grid max-w-lg grid-cols-3">
          {TABS.map((t) => {
            const active = t.match(pathname);
            return (
              <li key={t.label}>
                <Link
                  href={hrefs[t.label]}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "relative flex h-14 flex-col items-center justify-center text-[13px] transition-colors",
                    active ? "font-semibold text-text" : "text-text-2",
                  )}
                >
                  <span aria-hidden className={cx("absolute top-0 h-0.5 w-10 rounded-full transition-colors", active ? "bg-accent" : "bg-transparent")} />
                  {t.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
