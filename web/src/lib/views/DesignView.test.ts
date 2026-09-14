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
import { render, screen, waitFor } from "@testing-library/svelte";
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
