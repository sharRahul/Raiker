/// <reference types="vitest/config" />
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  plugins: [svelte({ hot: false })],
  // Local-first: the dev server binds to localhost only. M1 makes no backend calls.
  server: { host: "127.0.0.1", port: 5174 },
  // Resolve Svelte's browser entry under jsdom so component tests can mount.
  resolve: mode === "test" ? { conditions: ["browser"] } : {},
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
}));
