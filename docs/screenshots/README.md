# Raiker current UI screenshots

This is the canonical location for **current-product** screenshot evidence.

The older `docs/plans/screenshots/` tree is historical review evidence. It is intentionally not treated as current because it contains previous navigation/model states and 4K/8K capture classes that are no longer required.

## Required capture classes

Capture both light and dark themes at only these practical viewport sizes:

| Name | Viewport | Purpose |
|---|---:|---|
| `mobile` | `390×844` | phone layout, touch targets, overflow and compact composer behavior |
| `1080p` | `1920×1080` | normal desktop/laptop product evidence |

4K and 8K committed screenshots are **retired**. The responsive layout should still behave correctly at larger widths, but the repository does not need duplicate evidence images for rarely used 3840×2160 and 7680×4320 viewports.

## Generator

Use:

```bash
cd web
RAIKER_LIVE_BASE_URL=http://127.0.0.1:8765 \
RAIKER_LIVE_USER='<owner>' \
RAIKER_LIVE_PASSWORD='<password>' \
npx playwright test e2e/ui-sweep-responsive-live.spec.ts --project=live
```

The sweep writes viewport-only PNGs into:

```text
docs/screenshots/pages/
```

It also checks page-level properties such as horizontal overflow, missing icon glyphs, selected hub tabs being off-screen, control target sizing and console errors.

Do not commit credentials. `RAIKER_LIVE_USER` and `RAIKER_LIVE_PASSWORD` are runtime-only test inputs.

## Current route/tab expectations

The generator derives destinations from the app's navigation registry rather than maintaining a second handwritten route list.

Important current hub states include:

```text
Models
  overview
  models
  add
  runtime
  usage

Extensions
  overview
  connectors
  mcp
  skills
  hooks
  plugins

Observability
  overview
  sessions
  activity
  checkpoints
  work
  notifications

Settings
  general
  notification
  personalisation
  security
  privacy
  account
  web-access
  git-credential
  runtime
  updates
```

The legacy screenshot tree contains older Models names such as Hosted, Local, Hugging Face, Pricing and Routing. Those files must not be copied here and represented as current screenshots.

## Evidence rules

1. A screenshot is evidence only for the commit/runtime it was captured from.
2. Do not substitute stale PNGs when a current live host is unavailable.
3. Do not place real API keys, provider credentials, tokens, private paths or personal data in screenshots.
4. Capture populated states where useful, but seed them with disposable test data.
5. Preserve refusal/error/empty states in dedicated live tests when they express a security or product invariant; the page catalogue itself should represent the normal current state.
6. Screenshot changes do not prove functionality. The corresponding unit/e2e/API tests remain the implementation evidence.

## 2026-09-07 audit status

The audit branch moved the generator to this directory and removed 4K/8K capture classes. It did **not** fabricate or copy current PNGs because no authenticated live Raiker instance or current screenshot artifact was available to this repository review. Regeneration therefore remains a live-test step before the screenshot refresh can be called complete.
