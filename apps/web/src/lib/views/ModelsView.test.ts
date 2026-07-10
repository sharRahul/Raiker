// Coverage for the model fallback-sequence editor on the Models view: it renders
// the persisted sequence, adds/removes/reorders entries, and PUTs the ordered
// list back. The read is the single GET /api/models; the write is PUT
// /api/model-fallback (human gate-manager only, enforced server-side).
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ModelProfile, ModelsView as ModelsData } from "../apiTypes";
import { stubFetch } from "../test-helpers";
import ModelsView from "./ModelsView.svelte";

afterEach(() => vi.unstubAllGlobals());

function profile(partial: Partial<ModelProfile>): ModelProfile {
  return {
    profile_id: "p",
    provider: "llama.cpp",
    model: "local-gguf",
    default_state: "disabled",
    local_only: true,
    requires_network: false,
    endpoint_kind: "local",
    requires_egress_policy: false,
    requires_budget_policy: false,
    runtime_gate: null,
    off_machine: false,
    selected: false,
    ...partial,
  };
}

function models(partial: Partial<ModelsData>): ModelsData {
  return {
    profiles: [
      profile({ profile_id: "raiker-local-llama-cpp", provider: "llama.cpp" }),
      profile({ profile_id: "anthropic-hosted", provider: "anthropic", off_machine: true }),
    ],
    current_profile_id: null,
    hosted_model_gate_state: "enabled_runtime",
    private_network_model_gate_state: "enabled_runtime",
    model_egress_allowlist_configured: false,
    remote_profile_count: 1,
    fallback_sequence: [],
    no_silent_hosted_fallback: true,
    ...partial,
  };
}

describe("ModelsView fallback sequence", () => {
  it("renders the persisted sequence in order", async () => {
    stubFetch({
      "GET /api/models": models({
        fallback_sequence: ["anthropic-hosted", "raiker-local-llama-cpp"],
      }),
    });
    render(ModelsView);
    await waitFor(() =>
      expect(screen.getByText("Model fallback sequence")).toBeTruthy(),
    );
    const list = screen.getByRole("list");
    expect(list.textContent).toContain("anthropic-hosted");
    expect(list.textContent).toContain("raiker-local-llama-cpp");
  });

  it("shows the empty state when no fallback is configured", async () => {
    stubFetch({ "GET /api/models": models({ fallback_sequence: [] }) });
    render(ModelsView);
    await waitFor(() =>
      expect(screen.getByText(/No fallback configured/)).toBeTruthy(),
    );
  });

  it("adds a backend and PUTs the sequence", async () => {
    const mock = stubFetch({
      "GET /api/models": models({ fallback_sequence: [] }),
      "PUT /api/model-fallback": { ok: true, fallback_sequence: ["raiker-local-llama-cpp"] },
    });
    render(ModelsView);
    await waitFor(() => expect(screen.getByText("Model fallback sequence")).toBeTruthy());

    const select = screen.getByLabelText("Add a fallback backend") as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: "raiker-local-llama-cpp" } });
    await fireEvent.click(screen.getByText("Add"));
    await fireEvent.click(screen.getByText("Save sequence"));

    await waitFor(() => {
      const put = mock.mock.calls.find(
        (c) => (c[1]?.method ?? "GET").toUpperCase() === "PUT",
      );
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({
        profile_ids: ["raiker-local-llama-cpp"],
      });
    });
  });

  it("surfaces a server rejection reason", async () => {
    const mock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const method = (init?.method ?? "GET").toUpperCase();
      if (method === "PUT") {
        return {
          ok: false,
          status: 403,
          json: async () => ({ detail: { reason_code: "not_authorized_gate_manager" } }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => models({ fallback_sequence: ["raiker-local-llama-cpp"] }),
      } as Response;
    });
    vi.stubGlobal("fetch", mock);

    render(ModelsView);
    await waitFor(() => expect(screen.getByText("Model fallback sequence")).toBeTruthy());
    // Reorder to make the form dirty, then save.
    await fireEvent.click(screen.getByLabelText("Remove"));
    await fireEvent.click(screen.getByText("Save sequence"));
    await waitFor(() =>
      expect(screen.getByText(/not_authorized_gate_manager/)).toBeTruthy(),
    );
  });
});
