/*
 * QUI-F21 — a project's limits on its page: in words, set in a dialog, one per line.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProjectLimits from "./ProjectLimits.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => vi.unstubAllGlobals());

const NONE = { project_id: "proj_1", limits: { repositories: [], web_domains: [], connections: [] }, summary: [] };
const SET = {
  project_id: "proj_1",
  limits: { repositories: ["acme/site"], web_domains: [], connections: [] },
  summary: ["Pushes only to acme/site"],
};

describe("QUI-F21 project limits", () => {
  it("says a project with no limits follows your permissions", async () => {
    stubFetch({ "GET /api/projects/proj_1/limits": NONE });
    render(ProjectLimits, { projectId: "proj_1" });
    expect(await screen.findByText("No limits. Work here follows your permissions.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set limits" })).toBeEnabled();
  });

  it("saves one entry per line and shows the limits in words", async () => {
    const fetchMock = stubFetch({
      "GET /api/projects/proj_1/limits": NONE,
      "PUT /api/projects/proj_1/limits": SET,
    });
    render(ProjectLimits, { projectId: "proj_1" });
    await fireEvent.click(await screen.findByRole("button", { name: "Set limits" }));
    await fireEvent.input(screen.getByLabelText("Repositories it may push to"), { target: { value: "acme/site\n" } });
    await fireEvent.click(screen.getByRole("button", { name: "Save limits" }));
    expect(await screen.findByText("Pushes only to acme/site")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT");
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({ repositories: ["acme/site"], web_domains: [], connections: [] });
    await waitFor(() => expect(screen.getByRole("button", { name: "Change limits" })).toBeInTheDocument());
  });
});

it("recovers a failed read without leaving a false loading message", async () => {
  const routes: Record<string, unknown> = { "GET /api/projects/proj_1/limits": { __status: 503 } };
  stubFetch(routes);
  render(ProjectLimits, { projectId: "proj_1" });
  expect(await screen.findByRole("alert")).toHaveTextContent("saved work boundaries are unconfirmed");
  expect(screen.queryByText("Reading this project's limits…")).toBeNull();
  routes["GET /api/projects/proj_1/limits"] = NONE;
  await fireEvent.click(screen.getByRole("button", { name: "Retry project limits" }));
  expect(await screen.findByText("No limits. Work here follows your permissions.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("retains entries and warns about saved-state uncertainty after a failed save", async () => {
  stubFetch({ "GET /api/projects/proj_1/limits": NONE, "PUT /api/projects/proj_1/limits": { __status: 503 } });
  render(ProjectLimits, { projectId: "proj_1" });
  await waitFor(() => expect(screen.getByRole("button", { name: "Set limits" })).toBeEnabled());
  await fireEvent.click(screen.getByRole("button", { name: "Set limits" }));
  await fireEvent.input(screen.getByLabelText("Repositories it may push to"), { target: { value: "acme/site" } });
  await fireEvent.click(screen.getByRole("button", { name: "Save limits" }));
  expect(await screen.findByText(/Saving project limits was not confirmed/)).toHaveTextContent("check the saved limits before starting work");
  expect(screen.getByLabelText("Repositories it may push to")).toHaveValue("acme/site");
});
