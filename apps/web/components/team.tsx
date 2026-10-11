"use client";

import { useState } from "react";
import type { Team } from "@nflpi/shared";
import { teamAccent } from "@/lib/team";
import { cx } from "@/components/ui";

/** Team logo from team.logo_url. If the image cannot load, a monogram ring in the team color stands in. */
export function TeamLogo({ team, size = 24, className }: { team: Team; size?: number; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span
        role="img"
        aria-label={`${team.name} logo`}
        style={{ width: size, height: size, fontSize: Math.max(8, Math.round(size * 0.34)), ...teamAccent(team) }}
        className={cx(
          "inline-flex shrink-0 items-center justify-center rounded-full border-2 font-semibold tracking-tight text-text-2",
          "[border-color:var(--tc-dark)] light-ring",
          className,
        )}
      >
        {team.abbr}
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- static export, remote logo CDN
    <img
      src={team.logo_url}
      alt={`${team.name} logo`}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      style={{ width: size, height: size }}
      className={cx("shrink-0 object-contain", className)}
    />
  );
}

/** 3px team-color accent bar. */
export function TeamBar({ team, className }: { team: Team; className?: string }) {
  return <span aria-hidden style={teamAccent(team)} className={cx("team-accent block w-[3px] shrink-0 rounded-full", className)} />;
}
