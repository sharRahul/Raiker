import { afterEach, describe, expect, it, vi } from "vitest";
import { recentPages, rememberPage } from "./recentPages";

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("recent pages (UX-SETPOP-02)", () => {
  it("lists the newest first and leaves out the page you are on", () => {
    rememberPage("models");
    rememberPage("capabilities");
    rememberPage("tasks");
    expect(recentPages("tasks").map((item) => item.id)).toEqual(["capabilities", "models"]);
  });

  it("remembers a route once, at its latest visit", () => {
    rememberPage("models");
    rememberPage("work");
    rememberPage("models");
    expect(recentPages("home").map((item) => item.id)).toEqual(["models", "work"]);
  });

  it("ignores routes that are not destinations", () => {
    rememberPage("not-a-page");
    expect(recentPages("home")).toEqual([]);
  });

  it("is empty rather than broken when storage refuses", () => {
    // A storage object that refuses, whichever implementation the runtime
    // provides: Node 25's global localStorage is not jsdom's Storage.prototype.
    const blocked = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    } as unknown as Storage;
    const real = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", { configurable: true, get: () => blocked });
    try {
      expect(() => rememberPage("models")).not.toThrow();
      expect(recentPages("home")).toEqual([]);
    } finally {
      if (real) Object.defineProperty(window, "localStorage", real);
      else delete (window as { localStorage?: Storage }).localStorage;
    }
  });
});
