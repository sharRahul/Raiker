import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "../../test-helpers";
import ProvidersPanel from "./ProvidersPanel.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("ProvidersPanel local runtime setup", () => {
  it("opens only the reviewed Ollama source returned by the server", async () => {
    const open = vi.fn();
    vi.stubGlobal("open", open);
    stubFetch({
      "POST /api/model-operations/preview": {
        runtime: "ollama",
        action: "download_official_installer",
        source_url: "https://ollama.com/download/OllamaSetup.exe",
        argv: [],
        requires_elevation: false,
        terms_url: "https://github.com/ollama/ollama/blob/main/LICENSE",
        redistribution: false,
      },
    });
    render(ProvidersPanel);
    await fireEvent.click(
      screen.getByRole("button", { name: "Open official installer" }),
    );
    await waitFor(() =>
      expect(open).toHaveBeenCalledWith(
        "https://ollama.com/download/OllamaSetup.exe",
        "_blank",
        "noopener,noreferrer",
      ),
    );
  });

  it("requires confirmation before starting an Ollama pull", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
    const mock = stubFetch({
      "POST /api/ollama/pull": { operation_id: "mop_1", state: "queued" },
    });
    render(ProvidersPanel);
    await fireEvent.click(screen.getByRole("button", { name: "Pull model" }));
    await waitFor(() =>
      expect(mock).toHaveBeenCalledWith(
        "/api/ollama/pull",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("refreshes the Ollama catalogue after its pull completes", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const onCatalogueChanged = vi.fn();
    stubFetch({
      "POST /api/ollama/pull": { operation_id: "mop_1", state: "queued" },
      "GET /api/model-operations": {
        items: [
          {
            operation_id: "mop_1",
            kind: "pull",
            target: "qwen3",
            state: "complete",
          },
        ],
      },
    });
    render(ProvidersPanel, { props: { onCatalogueChanged } });

    await fireEvent.click(screen.getByRole("button", { name: "Pull model" }));

    await waitFor(() =>
      expect(onCatalogueChanged).toHaveBeenCalledWith([
        "ollama-local-openai-compatible",
      ]),
    );
  });
});
