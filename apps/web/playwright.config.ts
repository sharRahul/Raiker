import { defineConfig } from "@playwright/test";

// Some environments ship a pre-installed Chromium whose build number does not
// match the one this @playwright/test version would download. Setting
// PLAYWRIGHT_CHROMIUM_EXECUTABLE points the runner at that browser instead of
// failing with "Executable doesn't exist". Unset — the normal case — Playwright
// resolves its own managed browser exactly as before.
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../output/playwright/results",
  use: {
    viewport: { width: 1440, height: 1000 },
    colorScheme: "light",
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
});
