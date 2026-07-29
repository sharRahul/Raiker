import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../output/playwright/results",
  use: { viewport: { width: 1440, height: 1000 }, colorScheme: "light" },
});
