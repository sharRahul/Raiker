/// <reference types="vitest/config" />
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";
import { configDefaults } from "vitest/config";

export default defineConfig(({ mode }) => ({
  plugins: [svelte({ hot: false })],
  // Local-first: the dev server binds to localhost only and proxies /api to the local Raiker
  // API server (`raiker-web`, default 127.0.0.1:8765). In production the SPA is served by the
  // same FastAPI origin, so these relative /api paths resolve directly.
  server: {
    host: "127.0.0.1",
    port: 5174,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  // Resolve Svelte's browser entry under jsdom so component tests can mount.
  resolve: mode === "test" ? { conditions: ["browser"] } : {},
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
}));
