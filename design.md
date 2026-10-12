# Design System — NFL Pick'em Intelligence

> Source of truth for visual and interaction decisions. Product context lives in PRODUCT.md.
> Last reviewed: 2026-10-12 · Register: product · Preset: high-end-visual-design ("Ethereal Glass", restrained) with design-taste-frontend dials VARIANCE 3 · MOTION 3 · DENSITY 6 phone / 7 desktop
>
> Runtime tokens live in `apps/web/app/globals.css`. `docs/design/design-tokens.json` mirrors them and marks each group `landed` or `proposed`. `docs/design/design-preview.html` renders them. A rule tagged **(proposed)** is decided here but not yet in the app.

## 0. Direction 2026-10-12 (owner D39, D40, D41): supersedes the sections below where they differ

The look and layout follow reference 06 (`docs/design/references/06-concept-dark-lime.jpg`) with this app's own information. Nothing from soccer. Never copied pixel for pixel. Where a later section says blue, Geist-only titles, "no uppercase", "a game is never its own card" or "no glow", this section wins.

**Color (tokens, frozen for step 3).** One accent: lime. Lime means "me / interactive / selected" (the job blue had). Text on lime is near-black. Lime never colors the model or the market.

| Token | Dark | Light | Role |
|---|---|---|---|
| `bg` | `#0a0a0a` | `#f4f5f0` | Page |
| `surface` | `#151515` | `#ffffff` | Cards, groups |
| `elevated` | `#1f1f1f` | `#ecede6` | Controls, chips, tab bar |
| `border` | `#2a2a2a` | `#d9dbd2` | Hairlines |
| `border-strong` | `#6b6b6b` | `#7d8076` | Control boundaries (3:1) |
| `text` / `text-2` | `#f5f5f5` / `#a8a8a8` | `#141414` / `#52554c` | Ink |
| `accent` (fill) | `#c6f135` | `#c6f135` | Selected pill, active tab, primary button, my series fill |
| `accent-ink` | `#0a0a0a` | `#0a0a0a` | Text and icons on lime |
| `accent-text` | `#c6f135` | `#4d6b00` | Links, focus ring, lime text on a page background (4.5:1) |
| `good` | `#38bdf8` | `#0369a1` | Correct (sky, so it is never confused with lime); always with ✓ icon and a word |
| `warn` / `bad` | `#fbbf24` / `#f87171` | `#92400e` / `#b91c1c` | Moderate, stale, questionable / incorrect, high, out |

Chart series stay fixed by entity: me = lime, model = orange, market = teal; stats/elo/home pick values that are ≥ 3:1 on `surface`, not purple, and at least 30° of hue away from lime.
Landed values (step 3): dark me `#c6f135`, model `#d95926`, market `#199e70`, stats `#5b8def`, elo `#d55181`, home `#7d8794`; light me `#5f8700`, model `#c9501c`, market `#168a61`, stats `#2f6fd6`, elo `#c93673`, home `#727c87`. `subtle` is `#8a8a8a` dark / `#62655c` light (≥ 4.5:1 on `elevated`). Contrast in `docs/design/design-tokens.json`.

**Type.** Display face: **Barlow Condensed 700**, self-hosted from `@fontsource/barlow-condensed` (offline PWA), UPPERCASE, used for page titles, the big kickoff time on a card, final scores and the big win-chance figures. A small sentence-case kicker in Geist sits above a title ("Picks" over "WEEK 6"), as in the reference. Everything else stays Geist (body) and Geist Mono (machine values). Nothing under 11px. Uppercase is allowed only in the display face.

**Layout (D40).**
* Page head: kicker + huge condensed title; filter chips (pills) under it, horizontally scrollable on the phone.
* Week board: **one card per game** (24px radius `surface`), a grid of 2–3 columns on desktop, one column on the phone. Card top: away logo + name left, a round "VS" badge center, home logo + name right. Card middle: day and kickoff time large in the display face ("Time TBD" when unknown), model pick with win chance and its bar, uncertainty chip. Card bottom: the two pick pills; status chips (Backfilled, Upset watch, Locked, what changed, differs from model). The next game to kick off may be the one lime-filled card (one highlight per board).
* Matchup: header like the reference's detail screen (logos, names, VS or the final score in the display face); **split win-chance tiles** (away % and home %, the model's side filled lime, labeled "Model pick"); the pick panel; **pill section tabs** (Factors, Teams, Injuries, Conditions, Market, AI, History, Meetings) that jump to each section.
* Shell: desktop keeps a top bar (owner's P logo, nav, week picker) with nav items as pills (active = lime fill). Phone: a **floating pill tab bar** 12px above the safe area; the active tab is a lime pill with icon + label, the others icon-only circles with accessible names.
* Results, Backtest, Settings: same page head and chips; summaries in rounded cards; charts unchanged in meaning.
* Radius: card 24, control 12, chip/pill full. Soft lime glow allowed only behind the page head on the phone.

**Team logos (D38).** In dark mode use ESPN's dark-background variant (`/500-dark/` path) and fall back to the regular `logo_url` if it fails, then to the team-color mark.

**App icon (D41).** The owner's lime P (`docs/design/brand/app-icon/`) for the manifest, apple-touch-icon and favicon; `theme_color` and `background_color` `#0a0a0a`.

**Carried rules (still binding):** probability and uncertainty never share a visual; missing = en dash + reason; backfill always labeled and never in a live figure; one tap to pick; tap again to clear; locked = no outline + lock icon + 60% ink + the word "Locked"; a "differs from model" state is visible as a chip with words; what changed shows on the card and in the pick panel.

## 1. Product Design Philosophy

A private instrument for one person making sixteen decisions a week. It should feel like a well-made scoreboard: dark, quiet, exact. Numbers are the content. One surface per screen is allowed to feel like machined hardware (the pick); everything else recedes to type, alignment and hairlines.

The premium preset is applied to three things only: the pick surface, the phone tab bar and the press feel of controls. Its marketing-page habits (huge section padding, scroll-reveal on every element, eyebrow pills, glowing orbs) are rejected, because this is a tool read in seconds, often one-handed.

## 2. Core Design Principles

1. **Type and alignment carry hierarchy before containers do.** A box is the last resort.
2. **Probability and uncertainty never share a visual.** Probability is a number with a bar. Uncertainty is a text chip.
3. **Color means identity or state, never decoration.** Blue is me. Orange is the model. Green-teal is the market.
4. **Every number shows its source and age** within one tap or hover.
5. **Missing is drawn as missing**: an en dash plus a reason, never a zero, never a guess.
6. **One elevated surface per screen.** If two things float, neither is important.
7. **The pick is one tap, thumb-reachable, and its state is unmistakable** (open, mine, differs from model, waiting to sync, locked).
8. **Calm by default, loud only for what changes a pick.**

## 3. Visual Hierarchy

Order of preference: position, then size, then weight, then ink level (`text` → `text-2` → `subtle`), then spacing, then a hairline, then a surface. Color comes last and only with a meaning from section 5.

Per game the reading order is fixed: matchup → model pick and probability → uncertainty → what changed → my pick. The largest figure on any screen is a win probability or an accuracy, never a title.

## 4. Typography

Geist for text, Geist Mono for machine values. Self-hosted through the `geist` npm package: `apps/web/app/layout.tsx` uses its `GeistSans` and `GeistMono` exports, so the CSS family names are "GeistSans" and "GeistMono" (reason for the dependency: the PWA must render offline, and both chosen presets ban a default system/Inter stack). Fallback: `ui-sans-serif, -apple-system, "SF Pro Text", "Segoe UI", sans-serif`. No serif anywhere.

| Role | Size / line | Weight | Tracking | Used for |
|---|---|---|---|---|
| `display` | 40 / 44 | 600 | -0.02em | The win probability on Matchup |
| `stat` | 24 / 32 | 600 | -0.02em | KPI figures, accuracy |
| `title` | 22 / 28 | 600 | -0.01em | Page title ("Week 5") |
| `row-lead` | 16 / 22 | 600 | 0 | Team abbreviation, model pick in a row |
| `heading` | 14 / 20 | 600 | 0 | Section headings |
| `body` | 14 / 21 | 400 | 0 | Everything else |
| `label` | 12 / 16 | 400 | 0 | Field labels, captions, ages |
| `micro` | 11 / 16 | 500 | 0 | Chips only. Nothing is smaller than 11px |

* Weights in use: 400, 500, 600. No 700, no italics.
* Numerals: `tabular-nums` everywhere (set on `body`). `display` and `stat` switch to proportional via `.num-display`.
* Geist Mono is for moneylines, spreads, totals, Elo, timestamps and model version ids. Not for probabilities or scores.
* Prose lines cap at 65ch. Form controls are 16px on the phone so iOS does not zoom.
* No uppercase labels, no letter-spaced eyebrows.

## 5. Color System

Hex, dark-first, light follows the system setting. Values and measured contrast are in `design-tokens.json`.

| Token | Dark | Light | Role |
|---|---|---|---|
| `bg` | `#0b0f14` | `#f6f8fa` | Page |
| `surface` | `#11161d` | `#ffffff` | Grouped rows, bars |
| `elevated` | `#171e27` | `#f0f3f6` | Controls, tooltips, the pick core |
| `border` | `#232c38` | `#d8dee4` | Hairlines and dividers (decorative, 1.3:1) |
| `border-strong` | `#64707f` | `#818b95` | Boundary of inputs, selects and unselected pick buttons (3:1) |
| `text` / `text-2` / `subtle` | `#e6edf3` / `#9aa7b4` / mix | `#1f2328` / `#57606a` / mix | 15:1 / 7:1 / 4.8:1 on `surface` |
| `accent` / `accent-solid` | `#3b82f6` / `#2563eb` | `#0969da` | Me, and anything I can act on |
| `good` / `warn` / `bad` | `#3fb950` / `#d29922` / `#f85149` | `#166f31` / `#855700` / `#b91c25` | Correct or low uncertainty / moderate, stale, questionable / incorrect, high, out. Light values clear 4.5:1 on `elevated` and on their own chip tint |
| `series-me` / `-model` / `-market` | `#3987e5` / `#d95926` / `#199e70` | `#2a78d6` / `#c9501c` / `#168a61` | Fixed identity colors |
| `series-stats` / `-elo` / `-home` | `#d9ae2e` / `#d55181` / `#6b7785` | `#957100` / `#c93673` / `#727c87` | Backtest models. Every series is at least 3:1 on `surface` in both themes and none is purple (§ 15) |

Rules:

* **Blue means me or interactive.** Selected pick, links, focus ring, primary button, the Me series. It must not color the model's probability bar, headings, icons at rest, or any second chart series.
* **The probability bar fill is `text-2`**, with a tick at 50%.
* Model orange and market teal appear in charts and as a 6px identity dot beside the words "Model" and "Market". Never as fills behind text.
* Semantic colors appear only in chips, marks, notices and chart reference lines, always with a word.
* Team identity is the team logo (owner decision D38) with a 3px team-color bar. When the logo cannot load: the abbreviation in a team-color ring where it fits at 11px or more, else a solid team-color dot beside the printed abbreviation. Team color comes from `apps/web/lib/team.ts` per theme. Never a background, never text.
* `subtle` text sits on `bg` or `surface` only. On `elevated` it measures 4.47:1 in dark, so use `text-2` there.
* No pure black, no gradients, no glow. One accent.

## 6. Spacing and Layout

* 4px grid. Scale: 4, 8, 12, 16, 20, 24, 32, 48. No other values.
* Page: max width 1360px, gutters 16px below 1024 and 20px above. Top padding 16 / 24.
* Rhythm is deliberately uneven: 8 inside a row, 12 between a label and its value group, 24 between sections, 32 before a new day group or a new page region.
* Row heights: 56px minimum per game line on desktop, pick buttons 48px on the phone; on desktop 32px in a board row and 44px in the pick panel.
* Matchup on desktop is a `2fr 1fr` grid: evidence left, the pick panel right and sticky under the header.
* The phone leaves `88px + safe-area` clear at the bottom for the tab bar.

## 7. Surfaces and Containers

In order of preference:

1. **Nothing.** Content on `bg`, grouped by spacing. Default for Matchup sections, KPI strips, Results summaries.
2. **Hairline.** `border-t` or `divide-y` between rows and between sections.
3. **Group surface.** One `surface` block with 12px radius per day on the Week board, per table, per chart. Rows inside divide with hairlines. A game is never its own card.
4. **Bezel** (the one elevated surface): outer shell `elevated` at 60%, hairline ring, 6px padding, 18px radius; inner core `surface`, 12px radius, inset top highlight, `shadow-float`. Used for the Model pick panel on Matchup, the sign-in card and permission sheets. Nowhere else.
5. **Overlay.** Tooltip and toast: `elevated`, 8px radius, `shadow-pop`.

Radius: bezel 18, group 12, control 8, chip 6, pill for pick buttons, bars, and the phone tab bar. Cards are never nested. `backdrop-blur` only on the fixed header and tab bar.

## 8. Components

| Component | Source | Decision |
|---|---|---|
| Button | `components/ui.tsx` `Button` | Variants primary, secondary, ghost, danger. 40px phone, 36px desktop. One primary per view |
| Pick buttons | `components/pick-buttons.tsx` | Two pills, side by side, away left, home right. States: open (`border-strong` outline), mine (`accent-solid` fill, white text, check icon), waiting to sync (dashed outline, "Waiting to sync"), locked (no outline, lock icon, 60% ink). Tap the selected one to clear |
| Chip | `ui.tsx` `Chip` | Tones neutral, good, warn, warn-soft, bad, accent. Text always. At most two per game row on the phone; the rest fold into "+n" with a tooltip |
| Segmented, Select | `ui.tsx` | Segmented for 2 to 3 mutually exclusive views; a native `select` above that. Labels sit above or inline-left, never as placeholder |
| Tooltip | `ui.tsx` `Tip` | Keyboard and tap focusable. Explains a chip or a figure; never holds an action |
| Section | `ui.tsx` `Section` | Unboxed: heading, optional note, hairline, content. The boxed card version is retired |
| Stat / KPI strip | `ui.tsx` `Stat`, `components/week/kpi-strip.tsx` | One unboxed strip, cells divided by vertical hairlines, on every width. "Needs attention" is a filter chip, not a KPI |
| Game row | `components/week/game-row.tsx` | Table row on desktop, two-line row inside the day group on the phone |
| Navigation | `components/app-shell.tsx` | Desktop: full-width sticky bar (it holds the week picker and freshness, so it stays docked). Phone: **(proposed)** floating pill tab bar, 12px above the safe area, three text tabs, 48px targets, active tab on an `elevated` pill |
| Notice / freshness | `ui.tsx` `Notice`, `components/freshness.tsx` | Full-width banner only when a source that feeds the model is stale (schedules, lines, injuries). The header indicator turns amber for those only. Weather is a note on Settings |
| Toast | `components/toast.tsx` | Bottom, above the tab bar. Confirms saves and sync; errors stay until dismissed |
| Empty / loading / error | `ui.tsx` `EmptyState`, `Skeleton`, `ErrorState` | Skeletons match the final layout. Empty states say what will appear and when. Errors are inline with a Retry |

Not used: modals for confirmation, sidebars, dropdown menus, carousels, avatars.

## 9. Interaction Design

* **Hover** (desktop): rows lift to `elevated` at 50%; controls go from `border` to `border-strong`.
* **Focus**: 2px `accent` outline, 2px offset, always visible, never removed.
* **Press**: `translateY(1px)` on buttons, `scale(0.98)` on pick pills, 120ms.
* **Selected**: fill plus an icon or weight change. Never color alone.
* **Disabled and locked**: 50 to 60% ink, `not-allowed`, plus a word ("Locked").
* **Feedback**: a pick saves optimistically and shows "Saved" in a toast; a failure rolls back and says why.
* **Destructive**: clearing a pick is undoable by tapping again, so no confirm. Token reset and data wipe on Settings use an inline two-step button ("Reset" → "Confirm reset"), no modal.

## 10. Motion

Motion marks a state change or a spatial change. Nothing moves on its own except the skeleton shimmer and the spinner.

| Token | Value | Used for |
|---|---|---|
| `duration-press` | 120ms | Press, hover |
| `duration-state` | 200ms | Pick select, tab pill slide, chip change |
| `duration-enter` | 320ms | Toast, tooltip, bezel panel first mount, probability bar (`scaleX` from the left) |
| `ease-out` | `cubic-bezier(0.32, 0.72, 0, 1)` | Everything. No `linear`, no `ease-in-out` (the skeleton shimmer moves to this curve too) |

Only `transform` and `opacity` animate. No scroll-triggered reveals, no stagger, no parallax, no magnetic hover, no perpetual loops. With `prefers-reduced-motion`, transforms are removed and opacity changes cap at 120ms.

## 11. Responsive Design

| Layout | Phone < 768 | Tablet 768 to 1023 | Desktop ≥ 1024 |
|---|---|---|---|
| Shell | Compact top bar, floating tab bar | Same as phone | Docked top bar with nav and week picker |
| Week board | Day group; each game two lines plus pick pills | Same, pills inline on the right | Table, sticky header, picks in the row |
| KPI strip | Four cells, one row, `stat` drops to 20 / 28, one-word labels, no sub-line | Four cells | Four cells plus a text summary on the right |
| Matchup | Pick panel first, then sections in one column, section tabs scroll sideways | Same | `2fr 1fr`, pick panel sticky |
| Charts | Full width, 220px tall, direct labels | 280px | 320px, hover tooltips |

Full-height regions use `min-h-[100dvh]`. No horizontal page scroll at 320px. Tables that cannot fit become rows; they do not scroll sideways.

## 12. Accessibility

* WCAG 2.2 AA. Text 4.5:1, large text and control boundaries 3:1. Measured values are in `design-tokens.json`.
* Targets 44px on the phone, 24px minimum on desktop.
* Landmarks: one `header`, `nav aria-label="Primary"`, `main`, a skip link (exists).
* Pick pills are a `radiogroup` per game; arrow keys move, space selects, the row announces "locked" when locked.
* Chips, marks and results carry text or `sr-only` text. Charts have a data table alternative on Results and Backtest.
* Reduced motion per section 10. Text reflows at 200% zoom without loss.

## 13. Data Visualization

Recharts, wrappers in `components/charts/`.

* Series colors are fixed by entity (section 5) on every chart. Me is 2px, others 1.5px. No area fills, no gradients.
* Grid is `border` hairlines, horizontal only. Axis text is `label` in `text-2`. No axis titles when the unit is in the chart title.
* Three series or fewer are labeled at the line end; a legend appears only above that.
* Reference lines are dashed `subtle`: 50% on probability charts, the diagonal on calibration, the market's 66.6% on accuracy.
* Probabilities show whole percents in rows and one decimal in tables. Log loss shows three decimals. Intervals are written "66.5% (95% CI 64.9 to 68.1)". Formatting comes from `packages/shared/src/format.ts`, never from a component.
* Backfilled points are hollow; live points are solid.
* No dual axes, no pie or donut, no 3D.

## 14. Iconography

One file, `components/icons.tsx`, of inline SVGs: chevron-left, chevron-right, check, x, lock, warning, refresh, bell, cloud-off, clock, info, calendar, bar-chart, gear (the last three for the phone tab bar). 1.5px stroke, round caps, `currentColor`, 16px beside `body` text and 20px in controls. No icon library (a dozen icons do not justify a dependency). An icon never stands alone without an `aria-label`; tabs and buttons use text.

## 15. Anti-Patterns

Banned in this app:

* The words "lock" (as a pick), "guaranteed", "sure thing".
* A card per game, nested cards, or a row of equal KPI cards.
* Blue on anything that is not mine or interactive.
* Color as the only signal. A chip without text.
* Gradients, glows, glass panels in scrolling content, purple.
* Emoji and text glyphs used as icons.
* Uppercase letter-spaced labels, serif type, Inter or a bare system stack.
* Scroll-reveal, stagger, perpetual or magnetic motion.
* Invented placeholder data. A zero where a value is missing.
* Modals for confirmation.

Found in the 2026-10-11 audit of the current build (fix in the UI steps):

| Finding | Where | Rule | Status |
|---|---|---|---|
| Five equal KPI cards on desktop | `docs/screenshots/web-week-light.png`, `components/week/kpi-strip.tsx` | §7, §8 | Fixed 2026-10-12 |
| Every Matchup section is a boxed card | `docs/screenshots/web-matchup.png`, `ui.tsx` `Section` | §7 | Fixed 2026-10-12 |
| Each game is its own card on the phone | `docs/screenshots/pwa-week-dark.png` | §7 | Open (phone step) |
| Model probability bar is accent blue | `components/prediction-bits.tsx` | §5 | Fixed 2026-10-12 |
| `✓ ✗` and the week chevrons typed as characters | `ui.tsx` `Mark`, `components/pickers.tsx` | §14 | Fixed 2026-10-12 |
| Control borders at 1.29:1 | `ui.tsx` `SelectField`, pick buttons | §5 `border-strong` | Fixed 2026-10-12 |
| Light `series-market` at 2.82:1 and `series-model` at 3.20:1 on white | `globals.css` | §5 | Fixed 2026-10-12 |
| Font stack names Inter and falls back to the system | `globals.css` `--font-sans` | §4 | Fixed 2026-10-12 |
| Full-width "Stale data: weather" banner | `components/week/week-board.tsx`, `components/freshness.tsx` | §8 | Fixed 2026-10-12 |
| Skeleton uses `ease-in-out` | `globals.css` `.skeleton` | §10 | Fixed 2026-10-12 |

## 16. Reference Components

* `apps/web/components/ui.tsx` `Tip`: tooltips that work with keyboard and touch and stay inside the viewport. Copy its approach for any disclosure.
* `apps/web/components/ui.tsx` `Segmented`: right roles and target sizes, but no arrow-key navigation yet (see External references).
* `apps/web/components/week/game-row.tsx` (desktop table): the alignment of team bar, monogram, record and score is the model for every team listing.
* `apps/web/components/week/kpi-strip.tsx` (phone variant): the unboxed, hairline-divided strip is the pattern for all widths.
* `apps/web/lib/team.ts`: per-theme team color selection. Use it; never read a team color directly.
* `apps/web/components/game/recommendation.tsx`: content order of the pick panel (pick, probability, reliability, comparison, my pick). Keep the order; rebuild the container as the bezel.

### External references (21st.dev, source read 2026-10-11)

Patterns to copy by hand into `components/`. Do not install them: both assume shadcn paths, and the first needs `motion`, which this app does not have.

| Reference | Adopt | Do not adopt |
|---|---|---|
| [Segmented Control, ddoemonn](https://21st.dev/@ddoemonn/components/segmented-control) | Roving tabindex (selected option is the only tab stop). Arrow, Home and End keys move and select, skip disabled options and wrap. The thumb slides with `translateX(index * 100%)`, never `left` or `width`, and jumps straight there under reduced motion. Apply to `Segmented` and to keyboard handling on the pick pills | The sliding thumb on pick pills: a pick can be empty and clears on a second tap, so there is no thumb position for "none". The stone palette and its own focus color |
| [Leaderboard Table, eugeneshilow](https://21st.dev/@eugeneshilow/components/leaderboard-table) | Row anatomy: fixed label column, flexible bar on a track, right-aligned value, then fixed numeric columns. Whiskers over the bar for a real interval. Hovering a row dims the others and thickens its bar. Bars grow with `scaleX` from the left. Tick labels under the bar column. Use for the Backtest comparison (market, stats, blend with their 95% intervals) and for the desktop Week board's probability column | Whiskers on a game's win probability: uncertainty here is a grade, not an interval, and drawing one would invent a number. The enter stagger, uppercase letter-spaced headers, a 700px minimum width with sideways scroll, and the per-row series palette |
