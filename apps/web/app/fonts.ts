import localFont from "next/font/local";

/*
 * Geist and Geist Mono, self-hosted from the `geist` npm package so the PWA renders offline (design.md § 4).
 * next/font/local only takes paths relative to this file, so these point at the workspace-hoisted package.
 * The @font-face families are the plain "Geist" / "Geist Mono", which globals.css names in --font-sans / --font-mono
 * ahead of the fallback stack. The `variable` classes go on <html> so the faces and the preload are emitted.
 */
export const geist = localFont({
  src: "../../../node_modules/geist/dist/fonts/geist-sans/Geist-Variable.woff2",
  weight: "100 900",
  variable: "--font-geist",
  adjustFontFallback: false,
  declarations: [{ prop: "font-family", value: "Geist" }],
});

export const geistMono = localFont({
  src: "../../../node_modules/geist/dist/fonts/geist-mono/GeistMono-Variable.woff2",
  weight: "100 900",
  variable: "--font-geist-mono",
  adjustFontFallback: false,
  preload: false,
  declarations: [{ prop: "font-family", value: "Geist Mono" }],
});
