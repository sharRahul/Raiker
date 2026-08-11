import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../test-helpers";
import ModelSetupView from "./ModelSetupView.svelte";

afterEach(() => vi.unstubAllGlobals());

const required = {
  owner_principal_id: "principal_owner",
  status: "required",
  stage: "model",
  selected_profile_id: null,
  selected_model: null,
  model_deferred: false,
  privacy_mode: null,
  privacy_acknowledged_at: null,
  backup_mode: "later",
  backup_target: null,
  backup_verified_at: null,
  background_service_enabled: false,
  created_at: null,
  updated_at: null,
};

describe("first-run setup", () => {
  it("presents the five-stage checklist and lets model setup be deferred", async () => {
    const fetchMock = stubFetch({
      "GET /api/setup": required,
      "PUT /api/setup": { ...required, status: "in_progress", stage: "privacy", model_deferred: true },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Choose where Raiker thinks" })).toBeInTheDocument();
    for (const stage of ["Account", "Model", "Privacy", "Backup", "Finish"]) {
      expect(screen.getByText(stage)).toBeInTheDocument();
    }
    await fireEvent.click(screen.getByRole("button", { name: "Decide later" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url).endsWith("/api/setup") && init?.method === "PUT",
    )).toBe(true));
  });

  it("states the privacy boundary as an explicit choice", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "privacy" },
      "PUT /api/setup": { ...required, status: "in_progress", stage: "backup", privacy_mode: "local_first" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);
    expect(await screen.findByRole("heading", { name: "Choose your privacy boundary" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Local-first/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Balanced/i })).toBeInTheDocument();
  });

  it("never calls a deferred backup protected", async () => {
    stubFetch({
      "GET /api/setup": { ...required, status: "in_progress", stage: "backup" },
      "PUT /api/setup": { ...required, status: "in_progress", stage: "finish", backup_mode: "later" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);
    expect(await screen.findByRole("heading", { name: "Create your first backup" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Set up later" })).toBeInTheDocument();
    expect(screen.getByText(/No backup is configured/)).toBeInTheDocument();
  });
});
