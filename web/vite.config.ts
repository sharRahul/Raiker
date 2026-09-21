import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";
import { configDefaults } from "vitest/config";

// GCR-16 — the client bundle's own build identity, stamped in at build time
// from the same release version the rest of the pipeline is given. Unset — a
// development build, or `npm run dev` — it is the placeholder every other
// surface uses for "this was never released", which is the honest answer.
//
// It is here so Settings can show the host's build and the page's build side by
// side: a browser holding a cached bundle from before an update is the one
// support question neither number could answer on its own.
const clientBuild = process.env.RAIKER_VERSION?.trim() || "0.0.0";

export default defineConfig(({ mode }) => ({
  plugins: [svelte()],
  define: { __RAIKER_CLIENT_BUILD__: JSON.stringify(clientBuild) },
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
