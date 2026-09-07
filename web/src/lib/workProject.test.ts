// VIS2-11 / COMPOSER-11 — one Work project, and the three rules that keep it
// from becoming the account-level "active project" that used to exist.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetWorkProject, setWorkProject, startInBuild, workProject } from "./workProject.svelte";

beforeEach(() => {
  window.localStorage.clear();
  resetWorkProject();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("the shared Work project", () => {
  it("starts empty rather than guessing one", () => {
    expect(workProject()).toBe("");
  });

  it("is what every Work surface reads, so choosing once is choosing everywhere", () => {
    setWorkProject("proj_alpha");
    expect(workProject()).toBe("proj_alpha");
  });

  it("survives a reload", () => {
    setWorkProject("proj_alpha");
    expect(window.localStorage.getItem("raiker.build.project")).toBe("proj_alpha");
  });

  it("keeps the original key, so an existing Build preference is not lost", () => {
    // Renaming the key would silently drop the project every current owner has
    // already chosen — an upgrade that looks like a bug.
    window.localStorage.setItem("raiker.build.project", "proj_existing");
    expect(window.localStorage.getItem("raiker.build.project")).toBe("proj_existing");
  });

  it("clears to nothing rather than to a leftover string", () => {
    setWorkProject("proj_alpha");
    setWorkProject("");
    expect(workProject()).toBe("");
    expect(window.localStorage.getItem("raiker.build.project")).toBeNull();
  });

  it("still stands for this session when storage refuses to keep it", () => {
    // A blocked storage is a lost preference, never a blocked turn — and the
    // owner did choose it, so it holds until the tab closes.
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {
        throw new Error("denied");
      },
      removeItem: () => {
        throw new Error("denied");
      },
    });
    expect(() => setWorkProject("proj_alpha")).not.toThrow();
    expect(workProject()).toBe("proj_alpha");
  });

  it("opens Build in the project it was handed", () => {
    startInBuild("proj_alpha");
    expect(workProject()).toBe("proj_alpha");
    expect(window.location.hash).toBe("#/build");
  });
});
