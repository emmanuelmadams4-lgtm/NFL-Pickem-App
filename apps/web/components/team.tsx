"use client";

import type { Team } from "@nflpi/shared";
import { teamAccent } from "@/lib/team";
import { cx } from "@/components/ui";

/**
 * Team identity (PRODUCT.md: no logos): the abbreviation as a monogram inside a team-color ring.
 * Nothing is smaller than 11px (design.md § 4), so a ring too small for 11px text is drawn without text;
 * every caller prints the abbreviation or name beside it. Decorative either way.
 */
export function TeamLogo({ team, size = 24, className }: { team: Team; size?: number; className?: string }) {
  const fontSize = Math.round(size * 0.34);
  return (
    <span
      aria-hidden
      style={{ width: size, height: size, fontSize, ...teamAccent(team) }}
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full border-2 font-semibold tracking-tight text-text-2",
        "[border-color:var(--tc-dark)] light-ring",
        className,
      )}
    >
      {fontSize >= 11 ? team.abbr : null}
    </span>
  );
}

/** 3px team-color accent bar. */
export function TeamBar({ team, className }: { team: Team; className?: string }) {
  return <span aria-hidden style={teamAccent(team)} className={cx("team-accent block w-[3px] shrink-0 rounded-full", className)} />;
}
