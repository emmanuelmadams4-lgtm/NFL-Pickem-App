"use client";

import { useEffect, useState } from "react";
import { ago } from "@nflpi/shared";
import { useQueryClient } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import { flushPicks, isServerReachable, pendingCount, useOnline, useServerReachable } from "@/lib/sync";
import { safeGet, safeSet } from "@/lib/fmt";
import { useToast } from "@/components/toast";
import { Button, Card } from "@/components/ui";

/** Registers the service worker in production builds only. */
export function ServiceWorkerRegister() {
  const { toast } = useToast();
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    let registration: ServiceWorkerRegistration | undefined;
    let installed: ServiceWorker | null = null;
    let updateOffered = false;
    const offerUpdate = (reg: ServiceWorkerRegistration) => {
      if (updateOffered || !navigator.serviceWorker.controller || !reg.waiting) return;
      updateOffered = true;
      toast("New version ready.", "info", {
        label: "Reload",
        onClick: () => {
          if (!reg.waiting) {
            location.reload();
            return;
          }
          navigator.serviceWorker.addEventListener("controllerchange", () => location.reload(), { once: true });
          reg.waiting.postMessage("SKIP_WAITING");
        },
      });
    };
    const onStateChange = () => {
      if (installed?.state === "installed" && registration) offerUpdate(registration);
    };
    const onUpdateFound = () => {
      installed?.removeEventListener("statechange", onStateChange);
      installed = registration?.installing ?? null;
      installed?.addEventListener("statechange", onStateChange);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") void registration?.update().catch(() => {});
    };
    const register = () =>
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .then(() => navigator.serviceWorker.ready)
        .then((reg) => {
          registration = reg;
          reg.addEventListener("updatefound", onUpdateFound);
          if (reg.installing) onUpdateFound();
          offerUpdate(reg);
          document.addEventListener("visibilitychange", onVisible);
          // Hand the worker everything this page already loaded so a first-run offline reload works.
          const urls = performance
            .getEntriesByType("resource")
            .map((e) => e.name)
            .filter((u) => {
              try {
                const x = new URL(u);
                return x.origin === location.origin && (x.pathname.startsWith("/_next/static/") || x.pathname.startsWith("/icons/"));
              } catch {
                return false;
              }
            });
          reg.active?.postMessage({ type: "CACHE_URLS", urls });
        })
        .catch(() => {});
    if (document.readyState === "complete") register();
    else window.addEventListener("load", register, { once: true });
    return () => {
      window.removeEventListener("load", register);
      document.removeEventListener("visibilitychange", onVisible);
      registration?.removeEventListener("updatefound", onUpdateFound);
      installed?.removeEventListener("statechange", onStateChange);
    };
  }, [toast]);
  return null;
}

/** Shown on every page while the device is offline. */
export function OfflineBanner() {
  const online = useOnline();
  const reachable = useServerReachable();
  const qc = useQueryClient();
  const [at, setAt] = useState<number | null>(null);

  useEffect(() => {
    if (online && reachable) return;
    const cache = qc.getQueryCache();
    const update = () => {
      const oldest = cache.getAll().reduce((time, query) => (
        query.getObserversCount() > 0 && query.state.data !== undefined && query.state.dataUpdatedAt > 0
          ? Math.min(time, query.state.dataUpdatedAt)
          : time
      ), Infinity);
      setAt(Number.isFinite(oldest) ? oldest : null);
    };
    update();
    return cache.subscribe(update);
  }, [online, reachable, qc]);

  if (online && reachable) return null;
  return (
    <div role="status" className="border-b border-warn/40 bg-warn/12 px-4 py-2 text-center text-sm text-warn">
      {online ? "Can't reach the server. Is Tailscale on?" : "Offline"} &middot; showing data from {at ? ago(new Date(at).toISOString()) : "an earlier session"}
    </div>
  );
}

/** Flushes queued offline picks on load, when the connection returns, and when the app is foregrounded. */
export function PickSync() {
  const api = useApi();
  const qc = useQueryClient();
  const { toast } = useToast();

  useEffect(() => {
    const run = () => {
      if (!navigator.onLine || document.visibilityState !== "visible") return;
      const wasUnreachable = !isServerReachable();
      void api.health().then(async () => {
        await flushPicks(api, qc, toast);
        if (wasUnreachable) await qc.invalidateQueries();
      }).catch(() => {
        /* retry when the app returns or on the next tick */
      });
    };
    run();
    window.addEventListener("online", run);
    document.addEventListener("visibilitychange", run);
    const timer = window.setInterval(() => {
      if (!isServerReachable() || pendingCount() > 0) run();
    }, 15_000);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("online", run);
      document.removeEventListener("visibilitychange", run);
    };
  }, [api, qc, toast]);
  return null;
}

const INSTALL_KEY = "nflpi_install_dismissed";

function isIosSafariNotInstalled(): boolean {
  const ua = navigator.userAgent;
  const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = (navigator as Navigator & { standalone?: boolean }).standalone === true || window.matchMedia("(display-mode: standalone)").matches;
  return ios && !standalone;
}

/** iPhone only, and only until installed or dismissed. */
export function InstallHint() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    setShow(isIosSafariNotInstalled() && safeGet(INSTALL_KEY) !== "1");
  }, []);
  if (!show) return null;
  return (
    <Card className="flex items-start justify-between gap-3 p-4">
      <div>
        <p className="text-sm font-semibold text-text">Install on your iPhone</p>
        <p className="mt-0.5 text-sm text-text-2">Tap Share, then Add to Home Screen.</p>
      </div>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          safeSet(INSTALL_KEY, "1");
          setShow(false);
        }}
      >
        Dismiss
      </Button>
    </Card>
  );
}
