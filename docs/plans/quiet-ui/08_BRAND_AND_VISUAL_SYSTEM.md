# 08 Brand and visual system

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.
[VISUAL_DESIGN_SPEC.md](../../architecture/VISUAL_DESIGN_SPEC.md) remains the
owner of tokens; this records the decisions to apply to it.

## QUI-V01 — Colour tokens

| Role | Light | Dark | Use |
|---|---|---|---|
| Background | `#F7F6F2` | `#121212` | App canvas |
| Surface | `#FFFFFF` | `#1B1B1B` | Cards, panels, sheets |
| Main text | `#1C1C1A` | `#F4F1EA` | Reading text |
| Secondary text | `#686761` | `#B7B4AC` | Metadata |
| Primary action | `#2F6F8F` | `#78B7D5` | Primary actions, focus |
| Attention | `#B8871B` fill / **`#8A6411` text** | `#E0B64A` | Decisions required |
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
