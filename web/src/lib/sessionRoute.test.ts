// BUG-242 — the address bar has to follow the open conversation, and only for
// the surface the browser is actually on. Both halves are asserted here: the
// pure rewrite, and the guard that stops a hidden view rewriting a visible
// one's URL.
import { afterEach, describe, expect, it } from "vitest";
import { hashWithSession, rememberSessionInRoute } from "./sessionRoute";
import { routeStateFromHash } from "./routeState";

afterEach(() => {
  window.location.hash = "";
});

describe("hashWithSession", () => {
  it("adds the session to a bare route", () => {
    expect(hashWithSession("#/build", "sess_1")).toBe("#/build?session=sess_1");
  });

  it("keeps every other parameter the route already carried", () => {
    const next = hashWithSession("#/build?tab=repositories", "sess_1");
    expect(next).toContain("tab=repositories");
    expect(routeStateFromHash(next).sessionId).toBe("sess_1");
  });

  it("replaces a stale session rather than appending a second one", () => {
    expect(hashWithSession("#/build?session=old", "new")).toBe("#/build?session=new");
  });

  it("removes the session when the conversation is cleared", () => {
    expect(hashWithSession("#/build?session=old", null)).toBe("#/build");
    expect(hashWithSession("#/build?tab=repositories&session=old", null)).toBe(
      "#/build?tab=repositories",
    );
  });
});

describe("rememberSessionInRoute", () => {
  it("records the session without navigating away from the route", () => {
    window.location.hash = "#/build";
    rememberSessionInRoute("build", "sess_1");
    expect(routeStateFromHash(window.location.hash).sessionId).toBe("sess_1");
    expect(window.location.hash.startsWith("#/build")).toBe(true);
  });

  it("does nothing when the browser is on another route", () => {
    window.location.hash = "#/new-chat";
    rememberSessionInRoute("build", "sess_1");
    expect(window.location.hash).toBe("#/new-chat");
  });

  it("clears the session when the conversation is reset", () => {
    window.location.hash = "#/new-chat?session=sess_1";
    rememberSessionInRoute("new-chat", null);
    expect(routeStateFromHash(window.location.hash).sessionId).toBeNull();
  });
});
