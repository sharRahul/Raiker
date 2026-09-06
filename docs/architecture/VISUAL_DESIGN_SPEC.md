# Visual Design Specification — "Control Deck"

> **Status:** adopted and implemented. The tokens described here live in
> `apps/web/src/app.css`; the icon set in `apps/web/src/lib/icons.ts`; the shared
> components in `apps/web/src/lib/components/`. Where this document and the code
> disagree, the code wins and this document must be updated.
>
> `docs/architecture/WEB_UI_CONTROL_DECK_PLAN.md` decides *what each screen is for*. This
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

**A glyph may be reused where the meaning really is the same.** The tool-family
icons (BUG-206) map nine families to a glyph each, and four of them reuse one the
set already had *for the same idea*: `file` for a file read, `branch` for the
repository, `connections` for a connector, `tasks` for the turn's own plan. The
rule the collision test enforces is that no two glyphs are identical, not that no
two names may point at one — pointing a second name at an existing glyph is how a
family stays legible, where drawing a near-duplicate is how a set stops being
one. The five new ones (`file-edit`, `terminal`, `globe`, `memory`, `agent`) exist
because nothing in the set already meant them.

**A fallback is part of the set, not an omission.** `tool` — a spanner,
deliberately not the `settings` gear — renders a tool Raiker does not recognise.
A row with no glyph would read as an empty line, which is the silence BUG-206
was filed about.

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

- **Three colours per theme, named once.** The palette was reset on 2026-08-16 to
  the owner's choice, and every other token is *derived* from one of the three
  rather than introduced beside it:

  | | Light ("paper") | Dark ("deck") |
  |---|---|---|
  | Action / active state | steel blue `#2779a7` | gold `#ecd06f` |
  | Brand mark, pending / ask | gold `#ecd06f` | gold `#ecd06f` |
  | Neutral scaffold — borders, muted text | grey `#9c9c9c` | grey `#9c9c9c` |
  | Ground | near-white `#f4f4f5`, surfaces white | black `#000000` |
  | Ink | `#1b1c1e` | white `#ffffff` |

  `--brand-gold`, `--brand-blue`, `--brand-grey`, `--brand-black` and
  `--brand-white` are declared on `:root` so the three are addressable by name and
  a view cannot invent a fourth.
- **Two hues survive outside the three, and they are facts rather than
  decoration.** `--ok` (a run happened) and `--danger` (a run was refused) are how
  the four governed states — allow, pending, deny, read-only — stay tellable apart
  at a glance; they are mixed toward the palette so they read as part of it.
  Pending/ask is gold, and read-only/info is the accent's quieter half, so neither
  needs a hue of its own.
- **`--text-inverse` is the contrast pair for the accent**, not a synonym for
  white: white on light's blue, black on dark's gold. Every accent-backed control
  reads it rather than hard-coding a colour, which is what let the accent change
  hue without a single button becoming illegible.
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

## The five surfaces

VIS-04: the token system is mature, but subsystems were reading as visually
distinct because they were *implemented* separately rather than because they
differ. There are five surfaces and no sixth. Anything that feels like it needs
a new one is almost always one of these with a different name.

| # | Surface | What it is | Built from |
|---|---|---|---|
| 1 | **Page ground** | The room the work sits in. Never bordered, never raised. | `--bg`, `ResponsivePage` |
| 2 | **Primary work surface** | The one thing this route is for — a transcript, a graph, a repository tree. Fills the room; owns its own scrolling. | `--surface`, the route's own layout |
| 3 | **Secondary panel** | Something *about* the work surface, beside or over it — an inspector, a side rail, a popover. Raised, dismissible or collapsible. | `--raised`, `--r-lg`, `--shadow-2` |
| 4 | **Entity card or row** | One object the owner can act on: a project, a task, a model, an approval. A card when it stands alone, a row when it repeats — repeated entities are a list or a table, never a wall of cards (VIS-05). | `.card`, `.table`, `--r-md` |
| 5 | **Transient overlay** | A dialog, a drawer, the command palette. Modal, focus-trapped, escapable. | `--overlay`, `modalDrawer.ts` |

Two rules follow from the table rather than being separate opinions:

- **A container has to earn its border.** If a group of things is not one of the
  five, it is whitespace and a heading, not a card.
- **A label mark is declared once.** `.kicker` (muted) and `.eyebrow` (accent)
  are the two tiny-metadata marks; a view may adjust their spacing or colour and
  may not restate their type. `visualRubric.test.ts` holds this, because
  `.eyebrow` had already fragmented into six private copies at four weights and
  five trackings without anyone disagreeing on purpose.

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
| The rail stays short, every route stays reachable, the header contract is declared once, every empty state offers a way out, the shared label marks are not restated per view | `apps/web/src/lib/visualRubric.test.ts` |

## The visual rubric

Everything above proves the interface **works**. None of it proves the
interface looks calm or intentional — a page can pass the width sweep, the axe
scan and every token check and still be a wall of cards shouting in five
colours. That judgement is a review, not a test, and this is what the review
asks (VIS-24).

**Mechanised**, in `visualRubric.test.ts`, because each one was broken in
practice rather than merely disagreed with:

- the permanent rail carries at most eight destinations — it reached nine peers
  one reasonable addition at a time;
- everything off the rail is still reachable, from the gear's window and the
  command palette;
- the page-header contract is declared once in `app.css`, not privately per
  view — eight views each held a byte-identical copy;
- every empty state offers one action, or is on the short list where offering
  one would be wrong (a filtered list with no matches, a success state, a real
  error);
- no interface copy names a configuration path the product no longer reads.

**Human**, on any change to the shell, the composer or navigation. Review at
1440 in both themes and answer each of these out loud:

1. Is there a page whose first screen is more than about four primary cards?
2. Does every empty state have one obvious primary action?
3. Are there more than two accent colours in a normal, non-status area?
4. Is any technical identifier — a provider id, a model string, a protocol
   version — sitting at the top of the hierarchy, where the owner did not
   choose to put it?
5. Are the heading levels distinguishable without measuring them?
6. Would a first-time user find Chat, Build and Projects in five seconds?
7. Does a normal chat require understanding Permissions, Models, MCP or hooks?

A shell, composer or navigation change also needs an explicit visual approval
alongside the screenshot diff. "The tests pass" is not an answer to any of the
seven questions above.

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
