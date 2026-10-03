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
    rememberPage("tasks");
    rememberPage("models");
    expect(recentPages("home").map((item) => item.id)).toEqual(["models", "tasks"]);
  });

  it("ignores routes that are not destinations", () => {
    rememberPage("not-a-page");
    expect(recentPages("home")).toEqual([]);
  });

  it("is empty rather than broken when storage refuses", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => rememberPage("models")).not.toThrow();
    expect(recentPages("home")).toEqual([]);
  });
});
