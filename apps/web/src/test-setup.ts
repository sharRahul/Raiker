import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { resetModels } from "./lib/models.svelte";

// Node 25 ships a built-in `localStorage` global. It shadows the one jsdom
// installs and is inert unless the process was started with a valid
// `--localstorage-file`, so `window.localStorage.clear is not a function` took
// out every theme and login test on a current Node while CI, pinned to Node 22,
// stayed green. Rather than pin harder — which only defers the same break to the
// next Node — the storage jsdom promises is restored when what is present is not
// a working `Storage`.
//
// Written as a real map rather than a stub returning undefined: the code under
// test persists a theme choice and reads it back, so a no-op would pass the
// type check and fail the behaviour.
function installStorage(name: "localStorage" | "sessionStorage") {
  const present = (globalThis as Record<string, unknown>)[name] as Storage | undefined;
  if (present && typeof present.clear === "function") return;
  const entries = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return entries.size;
    },
    clear: () => entries.clear(),
    getItem: (key) => (entries.has(key) ? (entries.get(key) as string) : null),
    key: (index) => Array.from(entries.keys())[index] ?? null,
    removeItem: (key) => void entries.delete(key),
    setItem: (key, value) => void entries.set(key, String(value)),
  };
  Object.defineProperty(globalThis, name, { value: storage, configurable: true, writable: true });
  if (typeof window !== "undefined" && window !== (globalThis as unknown)) {
    Object.defineProperty(window, name, { value: storage, configurable: true, writable: true });
  }
}

installStorage("localStorage");
installStorage("sessionStorage");

// The model-profiles store is a module-level singleton, so without an explicit
// reset it leaks the previous test's snapshot into the next case (a picker would
// briefly show a stale "selected" model until its own refresh resolves). Clear
// it after every test so each case starts from the empty default.
afterEach(() => resetModels());
