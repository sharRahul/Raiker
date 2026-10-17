// SPDX-License-Identifier: Apache-2.0
import { defineConfig } from "@playwright/test";

// The desktop shell's own suite. `shell.spec.ts` needs nothing but a build of
// this directory: its Raiker is a fixture page on a loopback port. Specs whose
// name contains `live` drive a real `raiker-app` host and are run by hand, like
// the web app's live project.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  outputDir: "test-results",
  workers: 1,
  projects: [
    { name: "shell", testIgnore: /live/ },
    { name: "live", testMatch: /live/ },
  ],
});
