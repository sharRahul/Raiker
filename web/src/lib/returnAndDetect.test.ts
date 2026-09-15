// Returning to Raiker re-runs detection, once, and reports honestly.
import { afterEach, describe, expect, it, vi } from "vitest";
import { detectionNotice, onReturnToApp } from "./returnAndDetect";

function setVisibility(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => state,
  });
}

afterEach(() => setVisibility("visible"));

describe("onReturnToApp", () => {
  it("fires when the tab becomes visible again", () => {
    const seen = vi.fn();
    onReturnToApp(seen);
    setVisibility("visible");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(seen).toHaveBeenCalledTimes(1);
  });

  it("does not fire while the tab is still hidden", () => {
    // Opening the vendor page is what hides this tab. Detecting then would run
    // against the moment the owner *left*, which is the one moment it cannot
    // have changed.
    const seen = vi.fn();
    onReturnToApp(seen);
    setVisibility("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(seen).not.toHaveBeenCalled();
  });

  it("fires on focus for a window manager that never hides the tab", () => {
    const seen = vi.fn();
    onReturnToApp(seen);
    window.dispatchEvent(new Event("focus"));
    expect(seen).toHaveBeenCalledTimes(1);
  });

  it("fires once and then stops", () => {
    // A listener that survived would re-detect on every tab switch, which is a
    // background poll wearing a different name.
    const seen = vi.fn();
    onReturnToApp(seen);
    window.dispatchEvent(new Event("focus"));
    document.dispatchEvent(new Event("visibilitychange"));
    window.dispatchEvent(new Event("focus"));
    expect(seen).toHaveBeenCalledTimes(1);
  });

  it("can be cancelled before the owner returns", () => {
    const seen = vi.fn();
    const cancel = onReturnToApp(seen);
    cancel();
    window.dispatchEvent(new Event("focus"));
    expect(seen).not.toHaveBeenCalled();
  });

  it("survives being cancelled twice", () => {
    const cancel = onReturnToApp(() => {});
    cancel();
    expect(() => cancel()).not.toThrow();
  });
});

describe("detectionNotice", () => {
  it("says installed only when detection actually found it", () => {
    expect(detectionNotice({ vendor: "Ollama", detected: true })).toBe(
      "Ollama is now installed on this machine.",
    );
  });

  it("says what to try next when it did not", () => {
    // Not a failure and not a claim: Raiker opened a download, and whether the
    // owner ran it is theirs to say.
    const notice = detectionNotice({ vendor: "LM Studio", detected: false });
    expect(notice).toContain("still isn't detected");
    expect(notice).toContain("started once");
  });
});
