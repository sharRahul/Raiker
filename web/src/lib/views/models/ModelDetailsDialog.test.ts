// Hermes-parity local-server check and the context-window override, in Details.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ModelCapacitiesView } from "../../apiTypes";
import { modelProfile, stubFetch } from "../../test-helpers";
import ModelDetailsDialog from "./ModelDetailsDialog.svelte";

afterEach(() => vi.unstubAllGlobals());

const ollama = modelProfile({
  profile_id: "ollama-local-openai-compatible",
  provider: "ollama",
  model: "qwen2.5-coder:7b",
  selected: true,
});

function show(profile = ollama, capacities: ModelCapacitiesView | null = null, onchanged = vi.fn()) {
  render(ModelDetailsDialog, {
    props: {
      profile,
      capacities,
      disconnecting: false,
      onclose: () => {},
      onreconnect: () => {},
      ondisconnect: () => {},
      onchanged,
    },
  });
  return onchanged;
}

describe("model details", () => {
  it("checks a local server and names the setting that fixes it", async () => {
    stubFetch({
      "POST /api/models/ollama-local-openai-compatible/server-check": {
        ok: true,
        profile_id: ollama.profile_id,
        model: ollama.model,
        tool_calling: "as_text",
        reason_code: null,
        context_tokens: 32768,
        advice: ["This model's Ollama template returns tool calls as plain text."],
      },
    });
    show();
    await fireEvent.click(screen.getByRole("button", { name: "Check this server" }));
    const list = await screen.findByLabelText("Server check result");
    expect(list).toHaveTextContent("Returned as text");
    expect(list).toHaveTextContent("32,768 tokens");
    expect(screen.getByText(/returns tool calls as plain text/)).toBeInTheDocument();
  });

  it("offers no server check for a hosted API", () => {
    show(modelProfile({ profile_id: "openai-hosted", provider: "openai", model: "gpt-x", local_only: false }));
    expect(screen.queryByRole("button", { name: "Check this server" })).toBeNull();
  });

  it("saves an exact context window with its reason instead of browser prompts", async () => {
    const mock = stubFetch({
      "PUT /api/models/ollama-local-openai-compatible/capacity": {
        ok: true,
        profile_id: ollama.profile_id,
        model: ollama.model,
        tokens: 65536,
      },
    });
    const capacities = { can_override: true, entries: [], sync: [] } as unknown as ModelCapacitiesView;
    const onchanged = show(ollama, capacities);
    const form = screen.getByRole("heading", { name: "Context window override" }).closest("form")!;
    await fireEvent.input(within(form).getByLabelText("Tokens"), { target: { value: "65536" } });
    await fireEvent.input(within(form).getByLabelText("Why"), { target: { value: "Set with OLLAMA_CONTEXT_LENGTH" } });
    await fireEvent.click(within(form).getByRole("button", { name: "Save override" }));
    await waitFor(() => {
      const put = mock.mock.calls.find((c) => String(c[0]).includes("/capacity"));
      expect(put).toBeTruthy();
      expect(JSON.parse(put![1]!.body as string)).toEqual({
        model: ollama.model,
        tokens: 65536,
        reason: "Set with OLLAMA_CONTEXT_LENGTH",
      });
    });
    expect(onchanged).toHaveBeenCalled();
  });
});
