import { describe, expect, it } from "vitest";
import type { ExecutionEnvironment, ProbeVerdict } from "./apiTypes";
import {
  boundaryLabel,
  fullyProven,
  observationRows,
  posturaLine,
} from "./sandboxPosture";

function environment(overrides: Partial<ExecutionEnvironment> = {}): ExecutionEnvironment {
  return {
    profile_id: "native_sandbox",
    kind: "native",
    name: "Native OS sandbox",
    enabled: true,
    configured: true,
    available: true,
    status: "ready",
    selected: true,
    credential_configured: true,
    budget: null,
    cost: null,
    boundary: "appcontainer",
    probe_observations: {
      relay: "enforced",
      workspace_write: "enforced",
      escape_write: "enforced",
      masked_read: "enforced",
      egress: "enforced",
      descendant_reaped: "enforced",
    },
    ...overrides,
  } as ExecutionEnvironment;
}

describe("boundaryLabel", () => {
  it("names the measured boundary, not the configured one", () => {
    expect(boundaryLabel(environment())).toBe("AppContainer · network denied");
    expect(boundaryLabel(environment({ boundary: "bubblewrap" }))).toBe(
      "bubblewrap · network denied",
    );
  });

  it("never calls host access a sandbox", () => {
    const local = environment({ kind: "local", name: "Local strict", boundary: undefined });
    expect(boundaryLabel(local)).toBe("Host access — reduced isolation");
  });

  it("does not claim network denial from an unproven observation", () => {
    const unproven = environment({
      probe_observations: {
        relay: "enforced",
        workspace_write: "enforced",
        escape_write: "enforced",
        masked_read: "enforced",
        egress: "indeterminate",
        descendant_reaped: "enforced",
      },
    });
    expect(boundaryLabel(unproven)).toBe("AppContainer · network not proven");
  });
});

describe("observationRows", () => {
  it("renders indeterminate as not proven rather than as a partial pass", () => {
    const rows = observationRows({ egress: "indeterminate" as ProbeVerdict });
    expect(rows).toHaveLength(1);
    expect(rows[0].verdictLabel).toBe("Not proven");
  });

  it("keeps a stable order so the card does not reshuffle between probes", () => {
    const rows = observationRows(environment().probe_observations);
    expect(rows.map((row) => row.name)).toEqual([
      "relay",
      "workspace_write",
      "escape_write",
      "masked_read",
      "egress",
      "descendant_reaped",
    ]);
  });

  it("shows nothing rather than something reassuring when nothing was measured", () => {
    expect(observationRows(undefined)).toEqual([]);
  });
});

describe("fullyProven", () => {
  it("requires every observation, so one unproven leg is not a pass", () => {
    expect(fullyProven(environment())).toBe(true);
    expect(
      fullyProven(
        environment({
          probe_observations: { ...environment().probe_observations!, egress: "unenforced" },
        }),
      ),
    ).toBe(false);
  });

  it("is false when there is nothing to prove it with", () => {
    expect(fullyProven(environment({ probe_observations: {} }))).toBe(false);
    expect(fullyProven(null)).toBe(false);
  });
});

describe("posturaLine", () => {
  it("states what the boundary does not do, not only what it does", () => {
    expect(posturaLine(environment())).toContain("no PTY, background or network grant");
    expect(posturaLine(environment({ kind: "local" }))).toContain("no PTY");
  });
});
