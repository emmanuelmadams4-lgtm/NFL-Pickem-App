"use client";

import { useState } from "react";
import type { Team } from "@nflpi/shared";
import { teamAccent } from "@/lib/team";
import { cx } from "@/components/ui";

/**
 * Team logo from team.logo_url. A monogram ring in the team color stands in while the image loads
 * (so there is never a blank gap, even on a slow or offline connection) and if it never loads.
 */
export function TeamLogo({ team, size = 24, className }: { team: Team; size?: number; className?: string }) {
  const [status, setStatus] = useState<"loading" | "loaded" | "failed">("loading");
  const monogram = (
    <span
      role={status === "failed" ? "img" : undefined}
      aria-label={status === "failed" ? `${team.name} logo` : undefined}
      aria-hidden={status === "failed" ? undefined : true}
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
  return (
    <>
      {status !== "loaded" && monogram}
      {status !== "failed" && (
        // eslint-disable-next-line @next/next/no-img-element -- static export, remote logo CDN
        <img
          ref={(el) => {
            if (el && el.complete && el.naturalWidth > 0) setStatus("loaded");
          }}
          src={team.logo_url}
          alt={`${team.name} logo`}
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
