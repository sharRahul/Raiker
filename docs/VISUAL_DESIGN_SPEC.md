# Visual Design Specification — "Control Deck"

> **Status:** adopted and implemented. The tokens described here live in
> `apps/web/src/app.css`; the icon set in `apps/web/src/lib/icons.ts`; the shared
> components in `apps/web/src/lib/components/`. Where this document and the code
> disagree, the code wins and this document must be updated.
>
> `docs/WEB_UI_CONTROL_DECK_PLAN.md` decides *what each screen is for*. This
> document decides *how anything is drawn*, so a contributor can build a new page
> without inventing a size, a shade, a duration, or a bar.

## Why this exists

Raiker's visual language was correct before it was finished (BUG-37). The
colours, the dual themes, the radii, and the shadow ladder were all decided and
enforced. What was not decided was everything a *new page* has to answer: which
of three barely-separated heading sizes to use, how tall a table row should be,
what a loading state looks like, which icon means "diagnostics" rather than
"checkpoints", how to draw a proportion, and how long anything should take to
move. Each page answered those on its own, so the app was consistent in its
palette and inconsistent in everything downstream of it.

Six sections follow, one per decision. Each states the rule, the token, and the
reason — because a rule whose reason is not written down is a rule the next
contributor is entitled to ignore.

## 1. Type

**One modular scale at 1.22, anchored on the 15px body.**

| Token | Size | Used for |
|---|---|---|
| `--text-2xs` | 0.68rem | Table headers, kickers — uppercase, tracked wide |
| `--text-xs` | 0.74rem | Field labels, timestamps, secondary metadata |
| `--text-sm` | 0.82rem | Table body, card bodies, buttons |
| `--text-md` | 0.9rem | Form controls, `h4` |
| `--text-base` | 1rem | Body copy |
| `--text-lg` | 1rem | `h3` |
| `--text-xl` | 1.22rem | `h2` |
| `--text-2xl` | 1.49rem | `h1` |
| `--text-display` | 1.82rem | `.display` — serif |

Headings used to sit at 1.45 / 1.08 / 0.95rem. The first interval was 14%, which
reads as "the same size, only bolder": heading level was carried by weight alone,
and a page of headings read as one long run of bold text. Every step is now a
visible interval, and `apps/web/src/lib/appCss.test.ts` fails if any of them
falls below 1.15×.

**The serif is a voice, not a decoration.** `Source Serif 4` appears where Raiker
is speaking to the owner rather than labelling a control — the Workbench
greeting, an empty state's title, a sign-in headline — through the `.display`
class, and nowhere else. It is set at weight 500 because a serif at 700 above
1.5rem reads as shouting.

**Tracking.** `--tracking-tight` (−0.018em) on `h1` and `.display`: type set
large keeps the letter spacing it was drawn with, which reads loose.
`--tracking-wide` (0.07em) on uppercase micro-labels, which need the opposite.

**Never** write a bare `rem` font size in a view. Use a step, or add one here.

## 2. Density

**Three modes, chosen in Settings → Personalisation, applied through tokens.**

| Token | Compact | Comfortable | Spacious |
|---|---|---|---|
| `--control-y` / `--control-x` | 0.3 / 0.7rem | 0.42 / 0.85rem | 0.55 / 1rem |
| `--row-y` / `--row-x` | 0.32 / 0.5rem | 0.5 / 0.6rem | 0.7 / 0.8rem |
| `--space-3` … `--space-6` | tightened | default | loosened |

This workspace is dense by nature and its two readers want opposite things:
someone following a long transcript wants air, someone scanning a pricing table
wants rows. Density previously moved only the spacing scale, so a table stayed
exactly as tall while the gaps around it changed — which is why the setting
looked like it did nothing. `--control-y` and `--row-y` are what make it reach
the table itself.

A view that hard-codes control or row padding opts itself out of the owner's
choice. Use `.btn`, `.input`, `.table`, and `.card`, or spend the tokens
directly.

The 44px touch-target floor below 1024px is not negotiable and is applied after
density, so Compact on a phone is still tappable.

## 2b. What a page may say

**A component carries three things: the state, the next action, and — when
something failed — the reason with its remediation. Everything else lives in
`docs/guide/`.**

This is the rule that was missing, and its absence was measurable. Counted across
the component tree on 2026-08-15: **23,236 characters of static explanatory prose,
216 sentences, in 53 components** — about 3,700 words of documentation compiled
into the interface. `ModelsView` alone carried 2,783. Each sentence was
individually defensible, which is how it accumulated; together they meant a
returning owner read a paragraph to learn a state they already knew.

The honesty principle — *badges and copy always state what is real* — had been
read as *say all of it, on the card*. It does not follow. A page that explains
what a project **is** every time it lists projects is not being more honest; it
is teaching a reader who arrived to work.

**The test.** A sentence that would still be true if the owner had no data —
*"A project is a named scope for an ongoing piece of work…"*, *"The recorder
timeline: metadata snapshots taken at safe points…"* — is documentation. It goes
in the guide. A sentence that changes with the workspace — *"No sessions yet"*,
*"Provider unreachable"*, *"No price configured, so cost is unknown"* — is state.
It stays.

**Where it goes instead.** Every page carries one `GuideLink`, which opens that
page's section of the in-product guide (`#/guide?section=…`). Moving a paragraph
means confirming the guide already says it and adding it if not — the guide gains
what the interface loses, so the total stays truthful. Deleting the only copy an
owner can reach is not a density fix.

## 3. Empty and loading states

**An empty state is the first thing a new owner sees on almost every page.** It
gets a mark with depth (a tinted disc, a ring, a soft glow), a display-type
title, one line of body, and — where there is one — the next step as an action.
`EmptyState.svelte` provides all four; the `action` snippet is the way out, and
an empty state without one had better genuinely have no next step.

**Loading has two forms, and the choice is about honesty.** Where the eventual
shape is known — a list of cards, a table — use `PageState`'s `lines` prop for a
skeleton, which holds the space and stops the page jumping. Where the shape is
genuinely unknown, keep the one-line form: drawing a fake shape would be a guess
presented as information.

Errors keep `role="alert"`; loading and empty keep `role="status"`.

## 4. Iconography

**One optical size per role**, from `ICON_SIZE` in `icons.ts`:

| Name | Pixels | Used in |
|---|---|---|
| `sm` | 14 | Inline with dense text, inside a `.btn-sm` |
| `md` | 16 | Inside a control, beside a label |
| `lg` | 20 | A nav row, beside a heading |
| `xl` | 24 | An empty state's mark |

Call sites previously passed 14, 15, 16, 17, 18, 20 and 22 more or less
interchangeably. Pass a name; pass a number only where a bespoke control
genuinely needs an off-scale size.

**Filled is the selected state.** `Icon`'s `filled` prop washes the same paths
with `currentColor` at 16% behind the strokes. These are stroke icons, so filling
the geometry would misread badly on the open ones (a chevron, a pulse line), and
a second hand-drawn path set would eventually drift from the outline it belongs
to. This one cannot: it *is* the outline.

**No glyph means two unrelated things.** `diagnostics` was byte-for-byte the same
clock-with-a-rewind-arrow as `checkpoints`; `capabilities` was the sun with four
rays instead of eight; `projects` was the same folder outline as `folder`. All
three are now distinct, and `icons.test.ts` fails on any new collision.

## 5. Data-visual language

Three things all meant "a proportion of a whole" and looked like three unrelated
ideas. One set of rules:

- **A meter** is a proportion of a fixed capacity — context used of a window,
  spend against a budget. `.meter` + `.meter-fill`, with `--meter-value` (0–100)
  set by the view. It always shows the whole even when nearly empty, and it
  carries state through `.tone-ok` / `.tone-warn` / `.tone-danger`, which resolve
  to the same tokens the badge beside it uses.
- **A bar** is one value in a comparison — a provider's share of spend. Same
  geometry, `.bar` + `.bar-fill`, and **no capacity tones**: a large share is not
  a warning.
- **A number compared vertically** is set in tabular figures. Mark the cell
  `.numeric` (or any element `.numeric`), never the whole table — the label
  columns stay in the reading face.

A non-zero fill is never rounded down to nothing: `min-width: 2px`, because a 1%
fill drawn as a sliver reads as "none", which is a different fact.

## 6. Motion

**Three named intents.** A transition is chosen, not invented.

| Class | Token | Duration | Meaning |
|---|---|---|---|
| `.motion-enter` | `--motion-enter` | 180ms | Something arriving |
| `.motion-exit` | `--motion-exit` | 120ms | Something leaving |
| `.motion-emphasis` | `--motion-emphasis` | 240ms | A value changing on its own |
| — | `--motion-fast` | 120ms | Hover/focus/press feedback |

Enter is slower than exit because appearing needs to be noticed and disappearing
needs to be out of the way. Emphasis is the only duration long enough to read as
a deliberate movement and is reserved for something changing without the owner
touching it.

Nothing moves layout. Under `prefers-reduced-motion` every duration collapses
*and* the end state is named explicitly — a collapsed duration still paints the
first frame for an instant, which is enough to flash.

## Surfaces, colour, and depth (already decided)

Unchanged from the token pass that shipped with the first half of BUG-37, and
restated here so this document is complete:

- **One accent.** Teal is brand, primary action, and active state. Green, amber,
  red and blue are semantic only — success, warning, danger, information — and
  never decorative.
- **Radii climb with importance.** `--r-sm` for controls, `--r-md` for cards,
  `--r-lg`/`--r-xl` for panels that hold a whole object.
- **Depth is a ladder.** Each `--shadow-*` level pairs a tight contact shadow
  with a wider ambient one; `--shadow-0` is the faintest surface.
- **Focus is a 2px outline plus a 4px soft halo**, dropped under
  `forced-colors`, where the system owns focus.
- **Selection names both halves**, so selected text inside an accent bubble stays
  readable.
- **Scrollbars follow the theme** with an unchanged hit area.

Both themes are peers. A component uses tokens only — never a raw colour — so
neither theme can drift from the other without the other moving too.

## How this is enforced

| Rule | Enforced by |
|---|---|
| The scale exists, and the heading intervals are real | `apps/web/src/lib/appCss.test.ts` |
| Density reaches control padding and row height | `apps/web/src/lib/appCss.test.ts` |
| Motion names three intents and honours reduced motion | `apps/web/src/lib/appCss.test.ts` |
| One meter, one bar, tabular figures, no zero-rounding | `apps/web/src/lib/appCss.test.ts` |
| No two icons share a glyph; one optical size per role | `apps/web/src/lib/icons.test.ts` |
| Primitives are token-only (no hex, no `rgb()`) | `apps/web/src/lib/appCss.test.ts` |
| Every page renders in both themes at four widths | `apps/web/e2e/all-pages-theme-live.spec.ts`, `apps/web/e2e/visual-refresh-live.spec.ts` |
| Contrast and focus order | `apps/web/src/a11y.test.ts`, the live axe scans |

## Building a new page

1. Start from `ResponsivePage` and `.card`. Do not invent a container.
2. Take every size from the type scale and every gap from `--space-*`.
3. Use `.btn`, `.input`, `.select`, `.textarea`, `.table`, `.chip`,
   `.property-list`, `.card-grid` — a new pill or a new filter row is almost
   always one of these with a different name.
4. Give the page an `EmptyState` with an action, and a `PageState` for loading
   and error, before you give it data.
5. Draw a proportion as a meter or a bar; mark compared numbers `.numeric`.
6. Pick an icon by role and size, and use `filled` for selected.
7. Give the page one `GuideLink` and no explanatory prose — see "What a page
   may say". If the page needs to teach something, teach it in `docs/guide/`.
8. Check it at 375 / 768 / 1024 / 1440 px in both themes before you call it done.
