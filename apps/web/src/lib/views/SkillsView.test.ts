// Extensions → Skills. The tab's promises are the ones worth testing: an
// inactive skill is visibly withheld, a rejected upload says *why* in the
// owner's words, and nothing claims to be installed until the server said so.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import SkillsView from "./SkillsView.svelte";
import { stubFetch } from "../test-helpers";
import type { SkillView } from "../apiTypes";

afterEach(() => {
  vi.unstubAllGlobals();
});

function skill(partial: Partial<SkillView> = {}): SkillView {
  return {
    skill_id: "skl_1",
    name: "algorithm-creator",
    description: "Design and verify an algorithm before writing production code.",
    version: "1.0.0",
    source: "builtin",
    source_ref: "algorithm-creator",
    checksum: "a".repeat(64),
    active: true,
    files: ["algorithm-creator/SKILL.md"],
    file_count: 1,
    byte_size: 4096,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...partial,
  };
}

describe("SkillsView", () => {
  it("lists installed skills with their description", async () => {
    stubFetch({ "GET /api/skills": { skills: [skill()] } });
    render(SkillsView);
    expect(await screen.findByText("algorithm-creator")).toBeInTheDocument();
    expect(
      screen.getByText(/Design and verify an algorithm before writing production code/),
    ).toBeInTheDocument();
  });

  it("says a skill grants nothing, so the tab cannot be mistaken for a permission", async () => {
    stubFetch({ "GET /api/skills": { skills: [] } });
    render(SkillsView);
    expect(
      await screen.findByText(/grants no capability, opens no gate/i),
    ).toBeInTheDocument();
  });

  it("offers an empty state rather than an empty list", async () => {
    stubFetch({ "GET /api/skills": { skills: [] } });
    render(SkillsView);
    expect(await screen.findByText(/No skills installed yet/i)).toBeInTheDocument();
  });

  it("shows an inactive skill as inactive and offers to activate it", async () => {
    stubFetch({ "GET /api/skills": { skills: [skill({ active: false })] } });
    render(SkillsView);
    expect(await screen.findByText("inactive")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activate" })).toBeInTheDocument();
  });

  it("deactivating says the instructions are withheld from every turn", async () => {
    const fetchMock = stubFetch({
      "GET /api/skills": { skills: [skill()] },
      "PUT /api/skills/skl_1/active": { ok: true, skill_id: "skl_1", active: false },
    });
    render(SkillsView);
    await fireEvent.click(await screen.findByRole("button", { name: "Deactivate" }));
    await waitFor(() =>
      expect(screen.getByText(/withheld from every turn/i)).toBeInTheDocument(),
    );
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/active"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ active: false });
  });

  it("filters to inactive skills only", async () => {
    stubFetch({
      "GET /api/skills": {
        skills: [skill(), skill({ skill_id: "skl_2", name: "mcp-builder", active: false })],
      },
    });
    render(SkillsView);
    await screen.findByText("algorithm-creator");
    await fireEvent.click(screen.getByRole("button", { name: /Inactive \(1\)/ }));
    expect(screen.queryByText("algorithm-creator")).not.toBeInTheDocument();
    expect(screen.getByText("mcp-builder")).toBeInTheDocument();
  });

  it("translates a rejected import into the reason the owner can act on", async () => {
    stubFetch({ "GET /api/skills": { skills: [] } });
    render(SkillsView);
    await screen.findByText(/No skills installed yet/i);
    await fireEvent.input(screen.getByLabelText("Skill URL"), {
      target: { value: "https://example.com/SKILL.md" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Verify and add" }));
    // The route is unstubbed, so the stub answers 404 with a reason code; the
    // view must still show prose rather than a raw code or a bare status.
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });

  it("installs an imported skill and reports its real name", async () => {
    stubFetch({
      "GET /api/skills": { skills: [] },
      "POST /api/skills/import": {
        ok: true,
        skill_id: "skl_9",
        skill: skill({ skill_id: "skl_9", name: "tidy-imports", source: "url" }),
      },
    });
    render(SkillsView);
    await screen.findByText(/No skills installed yet/i);
    await fireEvent.input(screen.getByLabelText("Skill URL"), {
      target: { value: "https://github.com/o/r/blob/main/skills/tidy/SKILL.md" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Verify and add" }));
    await waitFor(() =>
      expect(screen.getByText(/Verified and installed “tidy-imports”/)).toBeInTheDocument(),
    );
  });

  it("builds a skill from a name, a description, and a body", async () => {
    const fetchMock = stubFetch({
      "GET /api/skills": { skills: [] },
      "POST /api/skills/build": {
        ok: true,
        skill_id: "skl_b",
        skill: skill({ skill_id: "skl_b", name: "release-notes", source: "built" }),
      },
    });
    render(SkillsView);
    await fireEvent.click(await screen.findByRole("button", { name: "Build a skill" }));
    await fireEvent.input(screen.getByLabelText("Name"), { target: { value: "release-notes" } });
    await fireEvent.input(screen.getByLabelText(/Description/), {
      target: { value: "Draft release notes. Use when cutting a release." },
    });
    await fireEvent.input(screen.getByLabelText("Instructions"), {
      target: { value: "# Release notes" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Build and install" }));
    await waitFor(() => expect(screen.getByText(/Built “release-notes”/)).toBeInTheDocument());
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/skills/build"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      name: "release-notes",
      description: "Draft release notes. Use when cutting a release.",
      body: "# Release notes",
    });
  });

  it("reports where a skill came from and what it hashes to", async () => {
    stubFetch({ "GET /api/skills": { skills: [skill({ source: "upload" })] } });
    render(SkillsView);
    await screen.findByText("algorithm-creator");
    expect(screen.getByText("Uploaded")).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Details" }));
    expect(screen.getByText(/aaaaaaaaaaaaaaaa…/)).toBeInTheDocument();
    expect(screen.getByText("algorithm-creator/SKILL.md")).toBeInTheDocument();
  });
});
