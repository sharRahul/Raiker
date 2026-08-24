// Extensions → Skills. The tab's promises are the ones worth testing: an
// inactive skill is visibly withheld, a rejected upload says *why* in the
// owner's words, and nothing claims to be installed until the server said so.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import SkillsView from "./SkillsView.svelte";
import { stubFetch } from "../test-helpers";
import type { SkillConformance, SkillView } from "../apiTypes";

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

// BUG-221 — a plugin's skill has to be readable as a plugin's, and the two
// controls that would be undone by the next sync must not be offered.
describe("SkillsView — skills a plugin contributed", () => {
  const fromPlugin = () =>
    skill({
      skill_id: "skl_p",
      name: "acme-review",
      description: "Review a change against Acme's internal checklist.",
      source: "plugin",
      source_ref: "acme-skills",
      active: false,
    });

  it("credits the plugin that provided it, by id", async () => {
    stubFetch({ "GET /api/skills": { skills: [fromPlugin()] } });
    render(SkillsView);
    expect(await screen.findByText("from plugin")).toBeInTheDocument();
    expect(screen.getByText(/Provided by plugin acme-skills/)).toBeInTheDocument();
  });

  it("arrives switched off, and can still be switched on here", async () => {
    stubFetch({ "GET /api/skills": { skills: [fromPlugin()] } });
    render(SkillsView);
    expect(await screen.findByText("inactive")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activate" })).toBeInTheDocument();
  });

  it("offers the plugin instead of Rename and Delete, which the next sync would undo", async () => {
    stubFetch({ "GET /api/skills": { skills: [fromPlugin()] } });
    render(SkillsView);
    await screen.findByText("acme-review");
    expect(screen.queryByRole("button", { name: "Rename" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage plugin" })).toHaveAttribute(
      "href",
      "#/extensions?tab=plugins",
    );
  });

  it("still lets the owner read what it says, by downloading it", async () => {
    stubFetch({ "GET /api/skills": { skills: [fromPlugin()] } });
    render(SkillsView);
    await screen.findByText("acme-review");
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });
});

// ADD-21 — `SKILL.md` is an open standard now. The tab answers the question an
// owner actually has about an installed skill: will this work anywhere else?
// It reports and never refuses, so a skill that installs today keeps installing.
describe("SkillsView — Agent Skills standard conformance", () => {
  function conformance(partial: Partial<SkillConformance> = {}): SkillConformance {
    return {
      conformant: true,
      spec_url: "https://agentskills.io/specification",
      findings: [],
      license: "",
      compatibility: "",
      metadata: {},
      refused_allowed_tools: [],
      ...partial,
    };
  }

  it("marks a conformant skill and says it will install elsewhere", async () => {
    stubFetch({ "GET /api/skills": { skills: [skill({ conformance: conformance() })] } });
    render(SkillsView);
    expect(await screen.findByText("standard")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: /Details/i }));
    expect(
      await screen.findByText(/should install in any tool that reads it/i),
    ).toBeInTheDocument();
  });

  it("says which direction an incompatibility runs, rather than just failing it", async () => {
    stubFetch({
      "GET /api/skills": {
        skills: [
          skill({
            conformance: conformance({
              conformant: false,
              findings: [
                {
                  field: "name",
                  code: "name_not_standard",
                  severity: "error",
                  message: "The standard allows lowercase letters and digits only.",
                },
              ],
            }),
          }),
        ],
      },
    });
    render(SkillsView);
    expect(await screen.findByText("1 portability issue")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: /Details/i }));
    // The skill works here. That is the half an owner would otherwise assume away.
    expect(
      await screen.findByText(/works in Raiker and may be refused by other tools/i),
    ).toBeInTheDocument();
  });

  it("names the tools a skill asked to pre-approve, and that they were not", async () => {
    stubFetch({
      "GET /api/skills": {
        skills: [
          skill({
            conformance: conformance({
              findings: [
                {
                  field: "allowed-tools",
                  code: "allowed_tools_not_honoured",
                  severity: "refused",
                  message: "Read and deliberately not honoured.",
                },
              ],
              refused_allowed_tools: ["shell", "write_file"],
            }),
          }),
        ],
      },
    });
    render(SkillsView);
    // A refusal is Raiker's choice, not the author's mistake, so the row still
    // reads as conformant.
    expect(await screen.findByText("standard")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: /Details/i }));
    expect(await screen.findByText(/Not pre-approved:/i)).toBeInTheDocument();
    expect(screen.getByText("shell, write_file")).toBeInTheDocument();
  });

  it("renders nothing about the standard when the payload did not measure", async () => {
    stubFetch({ "GET /api/skills": { skills: [skill()] } });
    render(SkillsView);
    await screen.findByText("algorithm-creator");
    expect(screen.queryByText("standard")).toBeNull();
    expect(screen.queryByText("1 portability issue")).toBeNull();
  });
});
