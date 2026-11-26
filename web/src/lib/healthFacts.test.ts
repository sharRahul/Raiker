import { describe, expect, it } from "vitest";
import { healthFacts, type HealthSources } from "./healthFacts";

const NOW = Date.parse("2026-11-26T12:00:00Z");
const none: HealthSources = { sandbox: null, backups: null, memory: null, voice: null, update: null, host: null };

describe("healthFacts (RU-08)", () => {
  it("lists the six facts first run sets up, each with the page that fixes it", () => {
    const facts = healthFacts(none, NOW);
    expect(facts.map((f) => f.id)).toEqual(["sandbox", "backups", "embedding", "voice", "updates", "always-on"]);
    for (const f of facts) {
      expect(f.state).toBe("unknown");
      expect(f.href).toMatch(/^#\//);
    }
  });

  it("calls a WSL2 sandbox that is chosen but not set up a failure, and a set-up one ok", () => {
    const view = { windows_backend: "wsl", applies: true, wsl_configured: false, wsl_missing: ["python3"], wsl_setup_command: null, native_ready: null, native_install_command: null };
    expect(healthFacts({ ...none, sandbox: view }, NOW)[0]).toMatchObject({ state: "fail", detail: expect.stringContaining("python3") });
    expect(healthFacts({ ...none, sandbox: { ...view, wsl_configured: true } }, NOW)[0].state).toBe("ok");
    expect(healthFacts({ ...none, sandbox: { ...view, windows_backend: "account" } }, NOW)[0].state).toBe("fail");
  });

  it("warns on no backup, an unverified one, or one older than a week", () => {
    const b = (created_at: string, verified_at: string | null) => ({ backups: [{ created_at, verified_at }], key_fingerprint: "", retired_key_fingerprints: [] }) as never;
    const fact = (backups: never) => healthFacts({ ...none, backups }, NOW)[1];
    expect(fact({ backups: [], key_fingerprint: "", retired_key_fingerprints: [] } as never).state).toBe("warn");
    expect(fact(b("2026-11-26T08:00:00Z", null)).detail).toMatch(/not verified/);
    expect(fact(b("2026-11-10T08:00:00Z", "2026-11-10T08:01:00Z")).state).toBe("warn");
    expect(fact(b("2026-11-25T08:00:00Z", "2026-11-25T08:01:00Z"))).toMatchObject({ state: "ok", detail: "Last verified backup yesterday." });
  });

  it("says recall matches words only when no embedding model is set", () => {
    const memory = { retrieval: null, embedding_providers: [], unindexed_memories: 0, unindexed_file_chunks: 0 } as never;
    expect(healthFacts({ ...none, memory }, NOW)[2]).toMatchObject({ state: "warn", detail: expect.stringContaining("words only") });
  });

  it("names the Bubblewrap package on Linux when it is missing (RU-04)", () => {
    const view = { windows_backend: "account", applies: false, wsl_configured: false, wsl_missing: [], wsl_setup_command: null, native_ready: false, native_install_command: "sudo dnf install bubblewrap" };
    expect(healthFacts({ ...none, sandbox: view }, NOW)[0]).toMatchObject({ state: "fail", detail: expect.stringContaining("sudo dnf install bubblewrap") });
    expect(healthFacts({ ...none, sandbox: { ...view, native_ready: true } }, NOW)[0].state).toBe("ok");
  });
});
