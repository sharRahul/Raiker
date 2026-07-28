import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { resetModels } from "./lib/models.svelte";

// The model-profiles store is a module-level singleton, so without an explicit
// reset it leaks the previous test's snapshot into the next case (a picker would
// briefly show a stale "selected" model until its own refresh resolves). Clear
// it after every test so each case starts from the empty default.
afterEach(() => resetModels());

// Node 25 can replace jsdom's Storage implementation with a nonfunctional
// object when its --localstorage-file flag has no path. Keep the test DOM
// standards-compatible without changing browser behavior.
if (typeof window !== "undefined" && typeof window.localStorage?.getItem !== "function") {
  const values = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      get length() { return values.size; },
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      key: (index: number) => [...values.keys()][index] ?? null,
      removeItem: (key: string) => values.delete(key),
      setItem: (key: string, value: string) => values.set(key, String(value)),
    } satisfies Storage,
  });
}
