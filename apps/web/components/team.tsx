"use client";

import { useState } from "react";
import type { Team } from "@nflpi/shared";
import { teamAccent } from "@/lib/team";
import { cx } from "@/components/ui";

/**
 * Team logo from team.logo_url (owner decision D37). While it loads, or if it never does, a stand-in is shown so the
 * gap is never empty: the abbreviation in a team-color ring when the ring fits 11px text (size >= 33, design.md § 4),
 * else a solid team-color dot. Every caller prints the team name or abbreviation beside the logo, so it is decorative.
 */
export function TeamLogo({ team, size = 24, className }: { team: Team; size?: number; className?: string }) {
  const [status, setStatus] = useState<"loading" | "loaded" | "failed">(team.logo_url ? "loading" : "failed");
  const standIn =
    size >= 33 ? (
      <span
        aria-hidden
        style={{ width: size, height: size, fontSize: Math.max(11, Math.round(size * 0.34)), ...teamAccent(team) }}
        className={cx(
          "inline-flex shrink-0 items-center justify-center rounded-full border-2 font-semibold tracking-tight text-text-2",
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
          ref={(el) => {
            if (el && el.complete && el.naturalWidth > 0) setStatus("loaded");
          }}
          src={team.logo_url}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          onLoad={() => setStatus("loaded")}
          onError={() => setStatus("failed")}
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
