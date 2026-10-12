"use client";

import { useState, useSyncExternalStore } from "react";
import type { Team } from "@nflpi/shared";
import { teamAccent } from "@/lib/team";
import { cx } from "@/components/ui";

const DARK = "(prefers-color-scheme: dark)";
function subscribeScheme(cb: () => void) {
  const mq = window.matchMedia(DARK);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}
/** True in dark mode (the default before the browser answers: the app is dark-first). */
function useDark(): boolean {
  return useSyncExternalStore(subscribeScheme, () => window.matchMedia(DARK).matches, () => true);
}

/** Dark mode prefers ESPN's dark-background variant (/500-dark/) when the URL has the /500/ segment (design.md § 0, D38). */
function logoSources(url: string, dark: boolean): string[] {
  if (!url) return [];
  return dark && url.includes("/500/") ? [url.replace("/500/", "/500-dark/"), url] : [url];
}

/**
 * Team logo from team.logo_url (owner decision D37). While it loads, or if it never does, a stand-in is shown so the
 * gap is never empty: the abbreviation in a team-color ring when the ring fits 11px text (size >= 33, design.md § 4),
 * else a solid team-color dot. Every caller prints the team name or abbreviation beside the logo, so it is decorative.
 */
export function TeamLogo({ team, size = 24, className, onLight }: { team: Team; size?: number; className?: string; onLight?: boolean }) {
  const sources = logoSources(team.logo_url, useDark() && !onLight);
  // Which source is showing, and whether it loaded. A failure moves to the next source, then to the stand-in.
  const [state, setState] = useState<{ key: string; index: number; loaded: boolean }>({ key: "", index: 0, loaded: false });
  const key = sources.join("|");
  const current = state.key === key ? state : { key, index: 0, loaded: false };
  const src = sources[current.index];
  const status: "loading" | "loaded" | "failed" = !src ? "failed" : current.loaded ? "loaded" : "loading";
  const setLoaded = () => !current.loaded && setState({ ...current, loaded: true });
  const setFailed = () => setState({ key, index: current.index + 1, loaded: false });
  const standIn =
    size >= 33 ? (
      <span
        aria-hidden
        style={{ width: size, height: size, fontSize: Math.max(11, Math.round(size * 0.34)), ...teamAccent(team) }}
        className={cx(
          "inline-flex shrink-0 items-center justify-center rounded-full border-2 font-semibold tracking-tight",
          onLight ? "text-accent-ink" : "text-text-2",
          "[border-color:var(--tc-dark)] light-ring",
          className,
        )}
      >
        {team.abbr}
      </span>
    ) : (
      <span aria-hidden style={{ width: size, height: size, ...teamAccent(team) }} className={cx("team-accent inline-block shrink-0 rounded-full", className)} />
    );
  return (
    <>
      {status !== "loaded" && standIn}
      {status !== "failed" && (
        // eslint-disable-next-line @next/next/no-img-element -- static export, remote logo CDN
        <img
          key={src}
          ref={(el) => {
            if (el && el.complete && el.naturalWidth > 0) setLoaded();
          }}
          src={src}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          onLoad={setLoaded}
          onError={setFailed}
          style={status === "loaded" ? { width: size, height: size } : { position: "absolute", width: 1, height: 1, opacity: 0, pointerEvents: "none" }}
          className={cx("shrink-0 object-contain", className)}
        />
      )}
    </>
  );
}

/** 3px team-color accent bar. */
export function TeamBar({ team, className }: { team: Team; className?: string }) {
  return <span aria-hidden style={teamAccent(team)} className={cx("team-accent block w-[3px] shrink-0 rounded-full", className)} />;
}
