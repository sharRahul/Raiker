import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import MemoryControls from "./MemoryControls.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const skill = (skill_id: string, source: string, active = true) => ({
  skill_id, name: `Skill ${skill_id}`, description: "Writes the weekly summary", source, active,
});
const grant = (grant_id: string, revoked = false) => ({
  grant_id, tool_name: "write_file", scope_pattern: "notes/*", risk_ceiling: "medium", use_count: 3,
  expires_at: "2099-01-01T00:00:00Z", revoked, revoked_at: null,
});

describe("QUI-F09 Memory › Controls", () => {
  it("lists only what Raiker built and approvals still in force", async () => {
    stubFetch({
      "GET /api/skills": { skills: [skill("s1", "built"), skill("s2", "upload"), skill("s3", "built", false)] },
      "GET /api/standing-grants": { grants: [grant("g1"), grant("g2", true)] },
    });
    render(MemoryControls);
    expect(await screen.findByText("Skill s1")).toBeInTheDocument();
    expect(screen.queryByText("Skill s2")).not.toBeInTheDocument();
    expect(screen.queryByText("Skill s3")).not.toBeInTheDocument();
    expect(await screen.findByText(/On notes\/\* · up to medium risk · used 3 times/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Undo" })).toHaveLength(2);
  });

  it("turns a learned skill off with Undo", async () => {
    const fetchMock = stubFetch({
      "GET /api/skills": { skills: [skill("s1", "built")] },
      "GET /api/standing-grants": { grants: [] },
      "PUT /api/skills/s1/active": { ok: true },
    });
    render(MemoryControls);
    await fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes("/api/skills/s1") && (init as RequestInit).method !== "GET")).toBe(true),
    );
  });
});
