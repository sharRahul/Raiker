import "@testing-library/jest-dom/vitest";

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
