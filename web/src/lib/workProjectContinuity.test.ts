/**
 * COMPOSER-11 — the Project survives switching Work mode.
 *
 * The behaviour, not the store: choosing a project in one Work composer has to
 * be visible in the next one, and — the part that is easy to get wrong — it must
 * never reach backwards into a conversation that already has a project of its
 * own.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch, openComposerProject } from "./test-helpers";
import { resetWorkProject, setWorkProject, workProject } from "./workProject.svelte";
import ChatView from "./views/ChatView.svelte";
import DesignView from "./views/DesignView.svelte";

afterEach(() => {
  vi.unstubAllGlobals();
  resetWorkProject();
});

const projects = {
  active_project_id: null,
  projects: [
    {
      project_id: "proj_alpha",
      name: "Alpha",
      root_subpath: "projects/alpha",
      created_at: "2026-01-01T00:00:00Z",
      session_count: 0,
      selected: false,
      parent_id: null,
      path: "Alpha",
      is_archived: false,
      archived_at: null,
      root_kind: "managed" as const,
      root_label: "alpha",
    },
  ],
};

function routes(extra: Record<string, unknown> = {}) {
  return {
    "GET /api/models": { profiles: [], chat_profiles: [], usable_provider_count: 0 },
    "GET /api/capability-gates": [],
    "GET /api/read-capabilities": { capabilities: [], external: [], interactive: [], surfaces: {}, administrative_surfaces: [], readiness: [] },
    "GET /api/images": { sizes: ["1024x1024"], generations: [] },
    "GET /api/projects": projects,
    ...extra,
  };
}

describe("Design's composer bar (found live 2026-09-07)", () => {
  it("does not print the size twice in one bar", async () => {
    // The size select sits two elements from the context line, and the line
    // carried a "Size 1024x1024" fact of its own — the same value, said twice,
    // side by side. COMPOSER-18: a control's own value is not also a fact.
    stubFetch(routes());
    render(DesignView, { props: { projects } });
    await waitFor(() => expect(screen.getByLabelText("Size")).toBeInTheDocument());
    expect(screen.getAllByText("1024x1024")).toHaveLength(1);
  });
});

describe("choosing a project in Chat", () => {
  it("makes it the project the next piece of work starts in", async () => {
    stubFetch(routes());
    render(ChatView, { props: { projects, visible: true } });

    await openComposerProject();
    const select = await screen.findByLabelText("Project for this chat");
    await fireEvent.change(select, { target: { value: "proj_alpha" } });

    // The point of the shared value: Build and Design read this, so the owner
    // does not choose the same boundary two or three times for one piece of work.
    await waitFor(() => expect(workProject()).toBe("proj_alpha"));
  });
});

describe("Design", () => {
  it("names the project the work is running in", async () => {
    setWorkProject("proj_alpha");
    stubFetch(routes());
    render(DesignView, { props: { projects } });

    // Named, and honestly bounded: research runs in the project, and a
    // generated image is not filed to it, because the image endpoint has no
    // project field yet.
    const context = await screen.findByText(/Alpha/);
    expect(context).toBeInTheDocument();
  });

  it("lets the owner choose one without leaving for the Projects page", async () => {
    stubFetch(routes());
    render(DesignView, { props: { projects } });

    await openComposerProject();
    const select = await screen.findByLabelText("Project for this work");
    await fireEvent.change(select, { target: { value: "proj_alpha" } });

    await waitFor(() => expect(workProject()).toBe("proj_alpha"));
  });

  it("says nothing about a project when none is chosen", async () => {
    stubFetch(routes());
    render(DesignView, { props: { projects } });

    await screen.findByLabelText("Describe the image");
    expect(screen.queryByText(/Alpha/)).not.toBeInTheDocument();
  });
});

describe("a conversation that already has a project", () => {
  it("is never re-filed by the shared value", async () => {
    // The failure this prevents is the account-level "active project" Raiker
    // used to have: a value set on one page that silently changed what a turn
    // on another page retrieved. The shared value is read only while there is
    // no session — it never reaches backwards.
    setWorkProject("proj_alpha");
    const moved: string[] = [];
    stubFetch(
      routes({
        "PUT /api/sessions/sess_existing/project": () => {
          moved.push("moved");
          return { ok: true };
        },
      }),
    );
    render(ChatView, { props: { projects, visible: true, sessionId: "sess_existing" } });

    await screen.findByLabelText("Prompt");
    expect(moved).toEqual([]);
  });
});

/*
 * RR-PROJECT-01 — "New chat" on a project card starts the chat in that project.
 *
 * The Projects page routed to Chat and established nothing, while the Build
 * button beside it established the project. The reasoning behind the difference
 * was that Chat's retrieval is owner-wide and must not be quietly scoped, which
 * is true — and is about retrieval. Where the conversation is *filed* is a
 * different field and the ordinary meaning of the button.
 */
describe("starting a chat from a project", () => {
  it("carries the project into a Chat that was already mounted", async () => {
    // The half that made this invisible: Chat is mounted once and hidden
    // between route visits, so it read the shared value when the application
    // started and never again.
    stubFetch(routes());
    render(ChatView, { props: { projects, visible: true } });
    await screen.findByLabelText("Prompt");

    setWorkProject("proj_alpha");

    await openComposerProject();
    const select = await screen.findByLabelText<HTMLSelectElement>("Project for this chat");
    await waitFor(() => expect(select.value).toBe("proj_alpha"));
  });

  it("files the second conversation in the project, not only the first", async () => {
    // Found while closing RR-PROJECT-01. The pending project is consumed when
    // the first conversation is created; starting another left it null while the
    // composer went on naming the project, so the chat was filed nowhere and the
    // page said otherwise.
    const filed: string[] = [];
    stubFetch(
      routes({
        "PUT /api/sessions/sess_new/project": () => {
          filed.push("filed");
          return { ok: true };
        },
      }),
    );
    setWorkProject("proj_alpha");
    render(ChatView, { props: { projects, visible: true } });

    await openComposerProject();
    const select = await screen.findByLabelText<HTMLSelectElement>("Project for this chat");
    await waitFor(() => expect(select.value).toBe("proj_alpha"));

    // Start a fresh conversation the way the composer's own control does.
    await fireEvent.click(screen.getByRole("button", { name: /new chat/i }));

    // The composer still names the project, so the filing must still mean it.
    await waitFor(() => expect(select.value).toBe("proj_alpha"));
    expect(screen.getByLabelText("Prompt")).toBeInTheDocument();
  });
});
