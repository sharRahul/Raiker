import { afterEach, describe, expect, it, vi } from "vitest";

import { announceResponseReady } from "./desktopNotice";
import { applyUiPrefs, uiPrefs } from "./prefs.svelte";

class FakeNotification {
  static permission = "granted";
  static shown: { title: string; body: string }[] = [];
  onclick: (() => void) | null = null;
  constructor(title: string, options: { body: string }) {
    FakeNotification.shown.push({ title, body: options.body });
  }
  close() {}
}

function hidden(value: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => value });
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeNotification.shown = [];
  hidden(false);
});

describe("QUI-F05 Response ready", () => {
  it("is said on the desktop only while Raiker is in the background", () => {
    vi.stubGlobal("Notification", FakeNotification);
    applyUiPrefs({ "notification.desktop": true });
    hidden(false);
    expect(announceResponseReady("Plan my week", "#/new-chat?session=s1", "r1", false)).toBe(false);
    hidden(true);
    expect(announceResponseReady("Plan my week", "#/new-chat?session=s1", "r1", false)).toBe(true);
    expect(FakeNotification.shown).toEqual([{ title: "Response ready", body: "Raiker answered in “Plan my week”." }]);
  });

  it("follows its own switch and quiet hours", () => {
    vi.stubGlobal("Notification", FakeNotification);
    hidden(true);
    applyUiPrefs({ "notification.desktop": true, "notification.interrupt.responses": false });
    expect(uiPrefs.responses).toBe(false);
    expect(announceResponseReady("x", "#/new-chat", "r2", false)).toBe(false);
    applyUiPrefs({ "notification.desktop": true });
    expect(announceResponseReady("x", "#/new-chat", "r3", true)).toBe(false);
    expect(FakeNotification.shown).toEqual([]);
  });
});
