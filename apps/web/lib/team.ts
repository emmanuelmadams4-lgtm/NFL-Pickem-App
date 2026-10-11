import type { CSSProperties } from "react";
import type { Team } from "@nflpi/shared";

function parse(hex: string): [number, number, number] | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function luminance(rgb: [number, number, number]): number {
  const [r, g, b] = rgb.map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function mix(rgb: [number, number, number], target: number, amount: number): string {
  const c = rgb.map((v) => Math.round(v + (target - v) * amount));
  return `rgb(${c[0]} ${c[1]} ${c[2]})`;
}

const css = (rgb: [number, number, number]) => `rgb(${rgb[0]} ${rgb[1]} ${rgb[2]})`;

/**
 * Team color as a small accent only. A navy team on a near-black surface (or a pale team on white)
 * would vanish, so each theme gets the first of color / color2 with enough luminance, else a tinted fallback.
 */
export function teamAccent(team: Team): CSSProperties {
  const a = parse(team.color);
  const b = parse(team.color2);
  const options = [a, b].filter((x): x is [number, number, number] => x !== null);
  const dark = options.find((c) => luminance(c) >= 0.07) ?? (options[0] ? mix(options[0], 255, 0.5) : "#6b7785");
  const light = options.find((c) => luminance(c) <= 0.45) ?? (options[0] ? mix(options[0], 0, 0.45) : "#6e7781");
  return {
    ["--tc-dark" as string]: typeof dark === "string" ? dark : css(dark),
    ["--tc-light" as string]: typeof light === "string" ? light : css(light),
  };
}
