# 08 Brand and visual system

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.
[VISUAL_DESIGN_SPEC.md](../../architecture/VISUAL_DESIGN_SPEC.md) remains the
owner of tokens; this records the decisions to apply to it.

## Status

**Applied 2026-10-25**
([FIXED-1168](../FIXED_ITEMS.md#fixed-1168--the-app-mark-was-the-eye-orb-qui-w01-qui-v03-qui-v04)
and [FIXED-1169](../FIXED_ITEMS.md#fixed-1169--the-palette-and-type-were-not-the-ones-08-decided-qui-v01-qui-v02);
live cases RT-QUI-57 and RT-QUI-70).

| Item | State |
|---|---|
| QUI-V01 | **Done.** Both themes use these roles in `web/src/app.css` and the desktop shell; soft fills were set so success and risk text stay at 4.5:1 on them (`appCss.test.ts`). |
| QUI-V02 | **Done** for type: Inter everywhere, bundled. Body stays 15 px. Radius and spacing were already on this scale. |
| QUI-V03 | **Done.** The eye-orb is gone from the app, the lock screen, the icons, the desktop Setup window and the installer art. |
| QUI-V04 | **Done.** The owner chose the open ring on 2026-10-25. `Logo.svelte` draws it; `scripts/render_brand_icons.py` renders every PNG from the same geometry. No route cue on one end. |
| QUI-V05 | **Open.** The companion's art does not exist. |
| QUI-V06 | **Done** earlier (Home's Continue and This week, the path line in plans and steps). |
| QUI-V07 | **Unchanged.** |
| QUI-V08 | **Done** earlier (QUI-Q06); this round also replaced the last glyph icons (a star and a cross in Threads) with drawn ones. |

## QUI-V01 — Colour tokens

| Role | Light | Dark | Use |
|---|---|---|---|
| Background | `#F7F6F2` | `#101216` (was `#121212`) | App canvas |
| Surface | `#FFFFFF` | `#1C2027` (was `#1B1B1B`) | Cards, panels, sheets, the composer |
| Main text | `#1C1C1A` | `#F2F4F7` (was `#F4F1EA`) | Reading text |
| Secondary text | `#686761` | `#C1C7D0` (was `#B7B4AC`); muted `#A0A7B2` (was `#8C8A84`) | Metadata, descriptions, placeholders |
| Primary action | `#2F6F8F` | gold `#E0B64A` with `#101216` text (`--action`, 2026-11-07) | Primary actions and key highlights |
| Interactive accent | `#2F6F8F` | `#78B7D5` | Secondary interaction, selection, focus |
| Attention | `#B8871B` fill / **`#8A6411` text** | amber `#EE9A4D` (2026-11-08; gold is the primary action) | Decisions required |
| Success | `#2F7D5C` | `#62B68D` | Verified completion |
| Risk | `#B5453C` | `#E47B70` | Destructive and error |

**Contrast check (WCAG 2.x).** Every token passes 4.5:1 on its background except
the light attention colour: `#B8871B` on `#F7F6F2` is 2.98:1, below even the
3:1 minimum for UI components. Use `#8A6411` (4.96:1) for attention text and
icons, and keep `#B8871B` only for fills with dark text on top. Success is the
tightest of the rest at 4.61:1.

## QUI-V02 — Type and spacing

* Inter for all interface text. Source Serif 4 deferred: add only if a welcome or
  reflection moment truly needs it.
* Body 15–16 px (now about 14.4 px, `--text-md: 0.9rem`; raising it touches
  every page, so it is its own change). Metadata 12–13 px. Page headings
  24–30 px semibold.
* Radius 10–14 px. Spacing scale 4, 8, 12, 16, 24, 32, 40, 48, 64.
* Default theme: follow the system.

## QUI-V03 — Remove the eye-orb

Remove it from the app icon, favicon, lock screen, loading and empty states,
avatar picker, copy and animation. Today `web/src/lib/components/Logo.svelte`
renders `raiker-mark.png` (the sphere with the prompt eye).

## QUI-V04 — App mark: the open ring

The owner does not want an R. Recommended mark: a rounded ring with one
deliberate gap.

* It reads as one bounded workspace with a single deliberate opening, which fits
  an approval-driven product without explanation.
* It echoes a snow-leopard rosette (a broken ring) without a face, so the mark
  and the companion stay separate but related.
* At 16 px it is one thick stroke and one gap.
* Optional route cue: one end of the gap slightly heavier, suggesting forward
  motion.
* Rules: never rotate or animate it (it would read as a spinner). Place the gap
  around 1–2 o'clock so it does not read as a "C" or a power icon.
* The wordmark is lowercase "raiker" in Inter at a tuned weight.

Alternatives considered: a threshold (rounded square open on one side; more
literal, colder) and two dots joined by a bend (warmer, drifts toward map
imagery).

## QUI-V05 — Companion

The companion gives personality inside Raiker; it is not the logo.

* Default: snow leopard. Collection later: bear, panda, penguin, wolf, tiger,
  cat, dog. Fox deliberately excluded (widely used by other products).
* Small accessories only: scarf, headphones, glasses, satchel, hat, route patch.
  No explorer costumes, maps, tents, globes or hiking imagery.
* **First release: one companion, static art, three moments**: empty or welcome,
  completed, blocked. The selector and animated states come later. Eight animals
  × six accessories × seven states is an illustration pipeline, not a first
  release.
* Never shown on risk or destructive errors.
* Never a loading spinner, never pretends to reveal reasoning, never on every page.
* Reduced motion: static art.

## QUI-V06 — Journey layer, without travel words

Four touches only:

1. **Continue where you left off** first on Home.
2. **The path line** in plans and step lists: done solid, current a point, later
   dotted. Only for plans that exist.
3. **Forward motion**: going deeper slides content in from the right, going back
   slides it left. Reduced motion swaps instantly.
4. **This week** on Home: finished outcomes named.

Words: Continue, Next step, Pick up, Ready for you, In progress, Needs your
decision, Completed, Partially completed, Outcome unknown, Scheduled. Never:
journey, destination, expedition, waypoint, trail, quest, arrived.

## QUI-V07 — Motion

Functional transitions around 100–240 ms. Hover paints instantly; only the
return eases. Motion follows state and never delays it. Everything beyond a fade
respects `prefers-reduced-motion`.

## QUI-V08 — Icons

Every icon has an accessible name. An icon-only control also gets a tooltip,
except where hover would teach nothing new (Hermes's rule): menu triggers, close
buttons, and controls whose visible label already says it.

## 2026-11-06 — Shared UI refinement across pages and subpages

The owner requested the macOS design references across all UI pages. Apply
QUI-V01/V02/V07/V08 through shared primitives, then inspect the complete routed
catalogue. The [Apple reviewer](https://github.com/dickwu/apple-design-skill),
[macOS skill](https://github.com/ceorkm/macos-design-skill), its
[Build with Claude version](https://github.com/davepoon/buildwithclaude/tree/main/plugins/all-skills/skills/macos-design)
(linked by HappyCapy and SkillRepo), and Impeccable inform this refinement.
Raiker's adopted palette, Inter, desktop target sizes, native window controls
and truthful completion/authority rules take precedence over sample recipes.

1. [x] Simplify shared empty-state decoration while keeping its title/action.
2. [x] Keep shared form-dialog headings and Close reachable while content scrolls.
3. [x] Bound confirmation dialogs and wrap long actions within the viewport.
4. [x] Let shared page headings and action groups wrap without squeezing content.
5. [x] Give native disclosures a consistent, keyboard-visible interaction floor.
6. [x] Apply immediate hover feedback and eased return to shared controls.
7. [x] Highlight a table row containing keyboard focus as well as pointer hover.
8. [x] Make shared tabs compact rounded rectangles with unclipped keyboard focus.
9. [x] Give explicitly invalid fields a consistent semantic error outline.
10. [x] Distinguish readonly text fields from disabled controls without dimming text.
11. [x] Replace the Permissions attention stripe with a quiet complete boundary.
12. [x] Remove the thick answer-callout edge; retain its icon, label and tone.
13. [x] Use fine quote rules consistently in transcript, file and source previews.
14. [x] Remove decorative side accents from reasoning and recalled-memory content.
15. [x] Cover nested Advanced/model settings and Add sources in the page catalogue;
    repair tab/panel associations, capture both themes/laptop widths, reconcile
    the visual specification, and run regressions and GitHub workflows.

Implementation and screenshot evidence are recorded in
[Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-06-shared-ui-refinement)
and [FIXED-1293/1294](../FIXED_ITEMS.md#fixed-1293--shared-ui-primitives-drifted-across-pages-and-subpages).

This refinement does not supply QUI-V05 companion art or qualify native macOS,
Windows, screen-reader or five-person usability acceptance. Keep this document
until its remaining work is complete.

## 2026-11-06 — Icon and option-control scale

The owner asked for larger icons and option sliders, then reviewed and rejected
the proposed long-pill composer shape, asking to restore the previous design.
Chat, Build and Design therefore retain their existing rounded-card geometry
and action sizes. The accepted blend pairs Muse's quieter spacing and
progressive disclosure with Apple's legible icon scale, familiar slider thumb
and clear switch state. This is a design direction, not a pixel-for-pixel copy:
Raiker keeps the QUI-V01 palette, Inter, and restrained surfaces. Do not add
Liquid Glass or replace the existing brand colors. *(Superseded for the
composer on 2026-11-07: the owner chose a glass capsule, see
[03](03_WELCOME_HOME_AND_CHAT.md#2026-11-07--composer-control-deck); and the
dark palette below.)*

The accepted changes use shared icon roles and consistent switch/range controls
across every page. The composer proposal was removed from source and its former
shape/size rules were restored from the previous revision.

| Item | State |
|---|---|
| UI-SCALE-01 | [x] Raise the small icon role to 16 px for legible inline actions. |
| UI-SCALE-02 | [x] Raise the medium icon role to 18 px for controls and navigation. |
| UI-SCALE-03 | [x] Raise the large icon role to 22 px for headings and nav emphasis. |
| UI-SCALE-04 | [x] Raise the empty-state icon role to 28 px. |
| UI-SCALE-05 | [x] Assert the four icon sizes remain ordered and fixed in the icon regression. |
| UI-SCALE-06 | [x] Give range sliders a taller 28 px interaction box and a useful minimum width. |
| UI-SCALE-07 | [x] Use a clear 6 px track and a 12×20 px lozenge thumb across browser engines. |
| UI-SCALE-08 | [x] Enlarge the Model picker Thinking switch to 48×28 px with a 22 px thumb. |
| UI-SCALE-09 | [x] Give the Privacy switch the same dimensions, focus ring and reduced-motion behavior. |
| UI-SCALE-10 | [x] Review the long-pill proposal; the owner rejected it. Keep the existing desktop/mobile card radii. |
| UI-SCALE-11 | [x] Preserve the existing 20 px focus radius; do not add a new focus shape. |
| UI-SCALE-12 | [x] Preserve the existing rounded-card draft shape, including after blur. |
| UI-SCALE-13 | [x] Keep attachment, drop and running states on the existing shared card surface. |
| UI-SCALE-14 | [x] Restore the existing 40 px desktop composer actions and 44 px narrow-window targets. |
| UI-SCALE-15 | [x] Review Chat, Build and Design, plus Privacy and Knowledge Map controls, in both themes and narrow layouts; retain screenshots and live cases. |

The slider thumb uses Apple's linear-slider lozenge shape, while the track and
switches inherit Raiker's accent and semantic tokens. The composer pill was
captured and reviewed, but the owner rejected it; those screenshots are
exploratory only. Final evidence uses the restored rounded-card shape.

## 2026-11-07 — Dark theme luminance ladder

**Owner decision, 2026-11-07.** The owner reviewed the dark theme and supplied
the palette and priorities below. They apply to the dark theme; light keeps its
QUI-V01 values, including blue primary actions, until the owner decides
otherwise.

| Role | Was | Now | Token |
|---|---|---|---|
| Main background | `#121212` | `#101216` | `--bg` |
| Sidebar | `#1B1B1B` (as cards) | `#15181E` | `--sidebar-bg` |
| Cards, panels, composer | `#1B1B1B` | `#1C2027` | `--surface` |
| Hover and wells | `#161616` (darker than cards) | `#232832` | `--sunken` |
| Raised surfaces, menus, dialogs | `#222222` | `#272D36` | `--raised`, `--dialog-bg` |
| Borders | `#2A2A2A` | `#343B46` (strong `#4A5361`) | `--border`, `--border-strong` |
| Composer edge | as borders | `#5A6474` (3.1:1 on the canvas) | `--composer-edge` |
| Primary text | `#F4F1EA` | `#F2F4F7` | `--text-1` |
| Secondary text | `#B7B4AC` | `#C1C7D0` | `--text-2` |
| Muted text | `#8C8A84` (`--text-3` aliased secondary) | `#A0A7B2` | `--text-3` |
| Primary actions | blue (kept 2026-11-08: the light gold fails as text) | gold `#E0B64A`, `#101216` text | `--action` |
| Attention | `#8A6411` text, `#B8871B` fill | amber `#EE9A4D`, 6.2:1 on `--raised` (2026-11-08) | `--warn` |
| Selected navigation | blue at 13 % | blue at 20 % | `--nav-selected` |

The 15-item checklist:

1. [x] Canvas, sidebar, cards, hover wells and menus form one ordered ladder.
2. [x] The sidebar is its own step between the canvas and the cards.
3. [x] Dialog shells (Add, form and confirm dialogs) sit on the raised step.
4. [x] Primary, secondary and muted text use the supplied values; muted is its own step again.
5. [x] Borders and strong borders use the supplied values.
6. [x] Hover moves up the ladder in dark: `--sunken` was darker than a card, so hovers barely showed.
7. [x] Selected navigation is a clearer tint than hover.
8. [x] Focus stays a blue 2 px ring with its halo, at least 3:1 on every step.
9. [x] The composer has its own edge token at 3:1 against the workspace.
10. [x] Gold is the primary action (`.btn-primary`, Send, Run, the model-setup primaries); blue stays for secondary interaction.
11. [x] Semantic status colours are unchanged.
12. [x] A unit test keeps the ladder ordered and every text role at AA on every step.
13. [x] axe colour-contrast runs on every destination in dark and light against a running host.
14. [x] Dark screenshots of every destination are kept for review.
15. [x] All composers stop growing at five lines (owner decision, same day), and Build shows dictation beside Run.

Evidence: [FIXED-1305](../FIXED_ITEMS.md#fixed-1305--the-dark-theme-had-no-surface-ladder-and-hover-was-invisible)
and the [Live Test docs](../../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-07-dark-ladder-and-five-line-composer).

