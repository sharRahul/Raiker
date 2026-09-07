import { afterEach, describe, expect, it } from "vitest";
import {
  applyTheme,
  isThemeChoice,
  loadThemeChoice,
  resolvedTheme,
  saveThemeChoice,
  THEME_STORAGE_KEY,
} from "./theme";

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme controller", () => {
  it("validates theme choices", () => {
    expect(isThemeChoice("light")).toBe(true);
    expect(isThemeChoice("dark")).toBe(true);
    expect(isThemeChoice("system")).toBe(true);
    expect(isThemeChoice("neon")).toBe(false);
    expect(isThemeChoice(null)).toBe(false);
  });

  it("defaults to system when nothing is stored or the value is invalid", () => {
    expect(loadThemeChoice()).toBe("system");
    window.localStorage.setItem(THEME_STORAGE_KEY, "bogus");
    expect(loadThemeChoice()).toBe("system");
  });

  it("applies an explicit theme via data-theme and removes it for system", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    applyTheme("system");
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("persists explicit choices and clears storage for system", () => {
    saveThemeChoice("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(loadThemeChoice()).toBe("dark");
    saveThemeChoice("system");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  });

  it("resolves explicit choices to themselves", () => {
    expect(resolvedTheme("light")).toBe("light");
    expect(resolvedTheme("dark")).toBe("dark");
  });
});
