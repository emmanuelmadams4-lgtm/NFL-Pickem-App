# Component sources (21st.dev) and brand assets

2026-10-12. Owner, his words: "make sure we update components using the design.md file and we use
21st.dev mcp to build out whats in the design md file and build out themes and logos for this app".
`design.md` stays the source of truth; this file maps its components to 21st.dev references.

## What the 21st.dev account allows (checked 2026-10-12 with `get_usage`)

* Free tier. Searching and theme CSS are free and unlimited.
* Component **code** retrieval: 2 a day, 0 left today. A locked retrieval returns a paywall, not code.
* Hosted AI generation: off (0 credits). So 21st cannot generate our components; builders adapt
  retrieved code or build from `design.md`.
* Theme search for "dark blue" and "dark navy blue accent dashboard theme" returned nothing. The
  app's theme stays the token set in `design-tokens.json`.

## Map: design.md component -> 21st.dev reference

Ids are 21st demo ids for `get_component`. "Retrieve" = worth one of the 2 daily retrievals.
Everything adopted must be restyled to our tokens (blue = me, orange = model, teal = market),
meet WCAG 2.2 AA, and add no dependency without a reason (`CLAUDE.md`).

| design.md component | 21st reference | Use |
|---|---|---|
| Floating pill tab bar, active tab = filled pill with icon + label (owner refs 06, 07) | Expanding Tabs `30168` (aicanvas); Bottom Nav Bar `8343` (arunachalam, uses Framer Motion) | **Retrieve 30168.** Closest match to reference 07. Port the morph with CSS transforms; no Framer Motion |
| Segmented control (filters, week views) | Segmented Control `23552` (ddoemonn), `35020` (kuratlielia) | Already recorded in design.md section 16: roving tabindex, arrow keys, `translateX` thumb |
| Chat thread + composer (D29, D36) | Message Thread `31661`, Prompt Input `28187` (mohammadshehadeh); Agent Chat `12402` | **Retrieve 31661.** Drop the model picker (D36: one chat, no picker) and attachments |
| Line / odds display, price moved since last shown (D20) | Odds Display `36175` (astralyxdev) | Retrieve when quota allows. The "moved since last shown" arrow fits change alerts |
| Confidence points 1 to N with swap (D3, D10) | Draggable Priority List `12556`, Reorder List `23550` (keyboard grab / move / drop, screen-reader announcements) | Pattern only: keyboard reorder and announcements. Points are also editable by number |
| Pick row, two pills (owner ref 01) | none good found ("Prediction Market Card" `2537` is a betting card) | Build from design.md section 8 and reference 01 |

## Themes

Dark and light already exist and follow the system setting only. To build: a three-way switch in
Settings (System / Dark / Light) driving `data-theme` on `<html>`, the `proposed` tokens landed in
`globals.css`, and the soft top glow on phone screens (D17). No extra colour themes: one accent,
fixed identity colours.

## Logo

Current icon: a blue "P" (`apps/web/public/icons/icon.svg`). Three options are in `brand/`
(`logo-options.html` shows them at 160, 60 and 29 px on both themes). The owner picks one; then the
PNG sizes (`icon-192`, `icon-512`, `maskable-512`, `apple-touch-icon`) are regenerated from it and a
wordmark lock-up is added to the header.

Team logos: official NFL team marks are trademarks and this repository is public. The app keeps
team abbreviations on team-colour tiles (`lib/team.ts`) unless the owner decides otherwise.
