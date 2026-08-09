import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../test-helpers";
import ModelSetupView from "./ModelSetupView.svelte";

afterEach(() => vi.unstubAllGlobals());

const required = {
  owner_principal_id: "principal_owner", status: "required", step: "choose_path",
  path: null, selected_profile_id: null, selected_model: null,
  created_at: null, updated_at: null,
};

describe("ModelSetupView", () => {
  it("offers every approved setup path and preserves a resumable skip", async () => {
    const fetchMock = stubFetch({
      "GET /api/model-setup": required,
      "PUT /api/model-setup": { ...required, status: "skipped" },
      "GET /api/models": { profiles: [], chat_profiles: [] },
    });
    render(ModelSetupView);

    expect(await screen.findByRole("heading", { name: "Choose how to run models" })).toBeInTheDocument();
    for (const path of ["Provider", "Ollama", "LM Studio", "Local GGUF", "Hugging Face"]) {
      expect(screen.getByRole("button", { name: path })).toBeInTheDocument();
    }
    await fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/api/model-setup") && init?.method === "PUT")).toBe(true));
  });

  it("moves from path to provider and keeps the exact choice", async () => {
    stubFetch({
      "GET /api/model-setup": required,
      "PUT /api/model-setup": { ...required, status: "in_progress", step: "provider", path: "provider" },
      "GET /api/models": { profiles: [{ profile_id: "anthropic", provider: "anthropic", model: "claude", selected: true, configured: true, ready: false }], chat_profiles: [] },
    });
    render(ModelSetupView);
    await fireEvent.click(await screen.findByRole("button", { name: "Provider" }));
    expect(await screen.findByRole("heading", { name: "Choose a provider" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Anthropic.*Claude/i })).toBeInTheDocument();
  });
});
