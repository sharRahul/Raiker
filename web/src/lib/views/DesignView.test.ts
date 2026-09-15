/*
 * NEW-PROJ-02 — arriving at Design from a project, at the picture you clicked.
 *
 * The project image strip had no per-asset action and one generic `#/design`
 * link, so an owner who had just been looking at a picture in a project had to
 * search the whole account's Design history to find it again. Design now takes
 * two coordinates — the project, and the asset — and both are held to the rule
 * every other route key here follows: they name something the reader may
 * already open, and grant nothing.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DesignView from "./DesignView.svelte";
import { makeGate, stubFetch } from "../test-helpers";
import { resetModels } from "../models.svelte";

function generation(partial: Record<string, unknown>) {
  return {
    generation_id: "img_1",
    profile_id: "prof_1",
    provider: "openai",
    model: "an-image-model",
    prompt: "a maple leaf",
    size: "1024x1024",
    status: "ok",
    reason_code: null,
    has_image: true,
    media_type: "image/png",
    byte_size: 100,
    created_at: "2026-09-13T10:00:00Z",
    kind: "create",
    source_generation_id: null,
    project_id: "proj_1",
    ...partial,
  };
}

const GENERATIONS = [
  generation({ generation_id: "img_1", prompt: "a maple leaf" }),
  generation({ generation_id: "img_2", prompt: "an oak leaf" }),
  generation({ generation_id: "img_other", prompt: "someone else's project", project_id: "proj_2" }),
];

function routes(overrides: Record<string, unknown> = {}) {
  return {
    "GET /api/images": { sizes: ["1024x1024"], generations: GENERATIONS },
    "GET /api/capabilities/gates": [
      makeGate({ capability: "image_generation", state: "runtime", runtime_enabled: true }),
    ],
    "GET /api/models": { profiles: [], selected_profile_id: null },
    "GET /api/projects": {
      projects: [
        {
          project_id: "proj_1",
          name: "Quarterly note",
          root_subpath: "projects/quarterly-note",
          created_at: "2026-09-01T00:00:00Z",
          session_count: 1,
          selected: true,
          parent_id: null,
          path: "/",
          is_archived: false,
          archived_at: null,
        },
      ],
      active_project_id: "proj_1",
    },
    ...overrides,
  };
}

function arriveAt(hash: string): void {
  window.location.hash = hash;
}

beforeEach(() => {
  arriveAt("#/design");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetModels();
  arriveAt("#/design");
});

describe("arriving at Design from a project", () => {
  it("shows only that project's images, and says so", async () => {
    arriveAt("#/design?project=proj_1");
    stubFetch(routes());
    render(DesignView);

    // The filter is visible, named, and has a way out — a filter nobody can see
    // is a canvas that looks like it has lost work.
    const chip = await screen.findByText(/Showing images from/);
    await waitFor(() => expect(chip).toHaveTextContent("Quarterly note"));
    // Only this project's two, not the third that belongs to another.
    expect(chip).toHaveTextContent("2 images");
    expect(screen.getByRole("link", { name: "Show all images" })).toHaveAttribute(
      "href",
      "#/design",
    );
  });

  it("says it is scoped even when the project cannot be named", async () => {
    // The label is supplementary; the filter is not. A failed project read must
    // not leave the canvas quietly showing a subset.
    arriveAt("#/design?project=proj_1");
    stubFetch(routes({ "GET /api/projects": { __status: 500 } }));
    render(DesignView);

    const chip = await screen.findByText(/Showing images from/);
    await waitFor(() => expect(chip).toHaveTextContent(/one project/i));
  });

  it("leaves the canvas whole when no project was named", async () => {
    stubFetch(routes());
    render(DesignView);

    await waitFor(() => expect(screen.queryByText(/Showing images from/)).toBeNull());
  });

  it("opens the asset the link named (NEW-PROJ-02)", async () => {
    // The whole point of the coordinate. Design's composer says which of the
    // two things pressing Enter will do, and an image being selected is what
    // turns generating into editing — so the composer is where a selection is
    // visible without reaching into the canvas's internals.
    arriveAt("#/design?project=proj_1&asset=img_2");
    stubFetch(routes());
    render(DesignView);

    expect(await screen.findByText(/Enter edits/)).toBeInTheDocument();
  });

  it("selects nothing when no asset was named", async () => {
    stubFetch(routes());
    render(DesignView);

    expect(await screen.findByText(/Enter generates/)).toBeInTheDocument();
  });

  it("ignores an asset that is not in this owner's gallery", async () => {
    // The gallery is owner-scoped on the server, so an id belonging to somebody
    // else resolves to nothing — and the surface stays usable rather than
    // pointing at something that is not there.
    arriveAt("#/design?asset=img_does_not_exist");
    stubFetch(routes());
    render(DesignView);

    await waitFor(() => expect(screen.queryByText(/Showing images from/)).toBeNull());
    // Nothing is selected, so the composer is still generating rather than
    // editing a picture that is not there.
    expect(await screen.findByText(/Enter generates/)).toBeInTheDocument();
  });
});

/*
 * REM-DESIGN-01 — a control that decides nothing, and a record that says it did.
 *
 * The size select was drawn for every provider and its value recorded on the
 * row. Raiker's Gemini request carries prompt parts and a candidate count and no
 * size at all, so the owner picked a shape, Raiker filed it, and the provider
 * never heard it — and the gallery then printed that shape beside the returned
 * picture as though it described it.
 */
describe("the size control says what it decides", () => {
  it("prints a provider-chosen size as chosen by the provider", async () => {
    stubFetch(
      routes({
        "GET /api/images": {
          sizes: ["1024x1024"],
          sized_providers: ["openai"],
          generations: [
            generation({ generation_id: "img_g", provider: "gemini", size: "1024x1536" }),
          ],
        },
      }),
    );
    arriveAt("#/design?asset=img_g");
    render(DesignView);

    await waitFor(() => expect(screen.getByText("chosen by gemini")).toBeInTheDocument());
    expect(screen.queryByText("1024x1536")).toBeNull();
  });

  it("prints the recorded size for a provider the size is sent to", async () => {
    stubFetch(
      routes({
        "GET /api/images": {
          sizes: ["1024x1024"],
          sized_providers: ["openai"],
          generations: [
            generation({ generation_id: "img_o", provider: "openai", size: "1536x1024" }),
          ],
        },
      }),
    );
    arriveAt("#/design?asset=img_o");
    render(DesignView);

    await waitFor(() => expect(screen.getByText("1536x1024")).toBeInTheDocument());
  });

  it("makes no claim on a host that does not report the field", async () => {
    // An older host says nothing about which providers take a size, and an
    // absent claim must not be read as "none of them do".
    stubFetch(
      routes({
        "GET /api/images": {
          sizes: ["1024x1024"],
          generations: [
            generation({ generation_id: "img_g", provider: "gemini", size: "1024x1536" }),
          ],
        },
      }),
    );
    arriveAt("#/design?asset=img_g");
    render(DesignView);

    await waitFor(() => expect(screen.getByText("1024x1536")).toBeInTheDocument());
  });
});

/**
 * BUG-281 — Design's research findings are text, *and* sources.
 *
 * The Tools menu runs a real governed research turn: it searches, reads and
 * extracts through the global read catalogue, and every governed read enters
 * the turn-source ledger. What came back on screen was the model's prose alone,
 * so opening the page a reference came from meant leaving Design for whichever
 * conversation the turn happened to run in.
 */
describe("Design research sources", () => {
  const SOURCES = {
    sources: [
      {
        source_id: "s1",
        turn_id: "turn_r1",
        ordinal: 1,
        kind: "web",
        title: "Maple leaf — reference plate",
        locator: "https://example.test/maple",
        detail: "",
        attachment_id: "",
        openable: true,
      },
      {
        // Another turn's source. The strip is scoped to the turn that answered,
        // or a second question would show the first one's pages as its own.
        source_id: "s1",
        turn_id: "turn_other",
        ordinal: 1,
        kind: "web",
        title: "Something else entirely",
        locator: "https://example.test/other",
        detail: "",
        attachment_id: "",
        openable: true,
      },
    ],
  };

  function researchRoutes(overrides: Record<string, unknown> = {}) {
    return routes({
      "GET /api/read-capabilities": {
        capabilities: ["web_search"],
        external: ["web_search"],
        interactive: [],
        surfaces: { design: ["web_search"] },
        administrative_surfaces: [],
        readiness: [],
      },
      "POST /api/prompts": {
        request_id: "req_1",
        session_id: "sess_research",
        turn_id: "turn_r1",
        status: "completed",
        message: "Maple leaves are palmate [s1].",
      },
      "GET /api/sessions/sess_research/sources": SOURCES,
      ...overrides,
    });
  }

  it("shows the pages the research turn read, scoped to that turn", async () => {
    stubFetch(researchRoutes());
    render(DesignView);
    await screen.findByLabelText("Describe the image");
    await fireEvent.input(screen.getByLabelText("Describe the image"), {
      target: { value: "a maple leaf" },
    });
    await fireEvent.click(await screen.findByRole("button", { name: /Tools/ }));
    await fireEvent.click(await screen.findByRole("menuitem", { name: /Search the web/i }));

    const panel = await screen.findByTestId("design-research");
    await waitFor(() => expect(panel).toHaveTextContent("Maple leaves are palmate"));
    // The ledger is a fact; this is the chip for it, openable here.
    expect(await screen.findByRole("button", { name: /Maple leaf — reference plate/ })).toBeInTheDocument();
    // Another turn's source is not this turn's provenance.
    expect(screen.queryByRole("button", { name: /Something else entirely/ })).not.toBeInTheDocument();
  });

  it("keeps the findings when the ledger read fails", async () => {
    // Provenance for an answer that already arrived: losing it costs the chips
    // and must never cost the answer.
    stubFetch(researchRoutes({ "GET /api/sessions/sess_research/sources": { __status: 500 } }));
    render(DesignView);
    await screen.findByLabelText("Describe the image");
    await fireEvent.input(screen.getByLabelText("Describe the image"), {
      target: { value: "a maple leaf" },
    });
    await fireEvent.click(await screen.findByRole("button", { name: /Tools/ }));
    await fireEvent.click(await screen.findByRole("menuitem", { name: /Search the web/i }));

    const panel = await screen.findByTestId("design-research");
    await waitFor(() => expect(panel).toHaveTextContent("Maple leaves are palmate"));
    expect(screen.queryByRole("button", { name: /reference plate/ })).not.toBeInTheDocument();
  });
});
