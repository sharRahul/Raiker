import { defineConfig } from "@playwright/test";

// Some environments ship a pre-installed Chromium whose build number does not
// match the one this @playwright/test version would download. Setting
// PLAYWRIGHT_CHROMIUM_EXECUTABLE points the runner at that browser instead of
// failing with "Executable doesn't exist". Unset — the normal case — Playwright
// resolves its own managed browser exactly as before.
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;

// BUG-41 — two suites with genuinely different requirements, told apart by
// filename so neither can be run by accident:
//
// * `mocked` needs `npm run build` and nothing else. Every response comes from a
//   fixture, so it is deterministic and belongs in CI. A redesign that outruns
//   it now fails a pull request instead of rotting unnoticed.
// * `live` drives a running `raiker-web` holding real provider credentials. It
//   is the evidence behind the FIXED-* entries in docs/plans/FIXED_ITEMS.md and
//   is deliberately a local, credentialled run — CI has no key and must not
//   pretend the scenario passed.
//
// **The convention: a spec whose filename contains `live` needs a real host.**
// Matching the whole filename rather than a `-live.spec.ts` suffix is deliberate
// — `live-end-to-end.spec.ts` is a live spec that does not end that way, and a
// rule that quietly misses one live spec would hand CI a scenario it cannot pass
// and blame the pull request for it.
const LIVE = /live/;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../output/playwright/results",
  use: {
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  projects: [
    { name: "mocked", testIgnore: LIVE },
    { name: "live", testMatch: LIVE },
  ],
});
