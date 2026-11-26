import { describe, expect, it } from "vitest";
import type { CapabilityGate } from "./apiTypes";
import { currentPosture, postureChanges, postureMode, READ_ONLY_DENIED, sandboxEnforced, SANDBOX_ALLOWED } from "./postures";

const gate = (capability: string, decision_mode: string) => ({ capability, decision_mode }) as unknown as CapabilityGate;

describe("postures (RU-07)", () => {
  it("maps each posture to decision modes: sandbox allows only in-copy changes and commands", () => {
    expect(postureMode("ask", "shell_execution")).toBe("ask");
    expect(postureMode("sandbox", "shell_execution")).toBe("allow");
    expect(postureMode("sandbox", "file_write_execution")).toBe("allow");
    for (const leaves of ["git_push_execution", "memory_write_execution", "email_runtime", "web_fetch", "finance_runtime"]) {
      expect(postureMode("sandbox", leaves)).toBe("ask");
    }
    expect(postureMode("read_only", "git_push_execution")).toBe("deny");
    expect(postureMode("read_only", "web_fetch")).toBe("ask");
  });

  it("never lets Work in the sandbox allow something Read-only does not refuse", () => {
    for (const cap of SANDBOX_ALLOWED) expect(READ_ONLY_DENIED).toContain(cap);
  });

  it("names the posture the modes match, or custom", () => {
    expect(currentPosture([gate("shell_execution", "ask"), gate("web_fetch", "ask")])).toBe("ask");
    expect(currentPosture([gate("shell_execution", "allow"), gate("web_fetch", "ask")])).toBe("sandbox");
    expect(currentPosture([gate("shell_execution", "deny"), gate("web_fetch", "ask")])).toBe("read_only");
    expect(currentPosture([gate("shell_execution", "auto"), gate("web_fetch", "ask")])).toBe("custom");
  });

  it("lists only the capabilities whose mode would change", () => {
    const gates = [gate("shell_execution", "ask"), gate("git_push_execution", "auto"), gate("web_fetch", "ask")];
    expect(postureChanges("sandbox", gates)).toEqual([
      { capability: "shell_execution", from: "ask", to: "allow" },
      { capability: "git_push_execution", from: "auto", to: "ask" },
    ]);
  });

  it("offers Work in the sandbox only while the sandbox is enforced", () => {
    const view = { windows_backend: "wsl", applies: true, wsl_configured: true, wsl_missing: [], wsl_setup_command: null, native_ready: null, native_install_command: null };
    expect(sandboxEnforced(view)).toBe(true);
    expect(sandboxEnforced({ ...view, wsl_configured: false })).toBe(false);
    expect(sandboxEnforced({ ...view, windows_backend: "account" })).toBe(false);
    expect(sandboxEnforced({ ...view, applies: false, native_ready: true })).toBe(true);
    expect(sandboxEnforced({ ...view, applies: false, native_ready: false })).toBe(false);
    expect(sandboxEnforced({ ...view, applies: false, native_ready: null })).toBe(false);
    expect(sandboxEnforced(null)).toBe(false);
  });
});
