import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, expect, it, vi } from "vitest";
import ModelRuntimeSettings from "./ModelRuntimeSettings.svelte";
import { api } from "../../api";
import type { LocalModel } from "../../apiTypes";
import type { ModelRuntimeSettingsView } from "../../generated/apiContract";

const GIB = 1024 ** 3;

function model(): LocalModel {
  return {
    owner_principal_id: "o", root_path: "/m", model_id: "mdl_1", name: "Qwen 7B", architecture: "qwen2",
    quantization: "Q4_K_M", primary_path: "/m/qwen.gguf", shard_count: 1, expected_shards: 1, complete: true,
    size_bytes: 4 * GIB, indexed_at: "", format: "gguf",
  };
}

function view(over: Partial<ModelRuntimeSettingsView["plan"] & object> = {}, settings = {}): ModelRuntimeSettingsView {
  const base = { gpu_layers: null, context_size: null, threads: null, flash_attention: "auto" as const, kv_cache_type: "f16" as const, allow_overcommit: false, ...settings };
  return {
    model_id: "mdl_1",
    settings: base,
    plan: {
      backend: "cuda", gpu_layers: 29, total_layers: 28, full_offload: true, context_size: 8192, trained_context: 32768,
      threads: null, flash_attention: "auto", kv_cache_type: "f16", weights_bytes: 4 * GIB, kv_cache_bytes: GIB / 2,
      gpu_bytes: 5 * GIB, system_bytes: GIB / 4, system_weights_bytes: 0, gpu_budget_bytes: 10 * GIB,
      system_budget_bytes: 20 * GIB, verdict: "fits", allowed: true, notes: [], args: [], estimated: true, settings: base, ...over,
    },
    plan_error: null,
  };
}

beforeEach(() => vi.restoreAllMocks());

it("starts on automatic settings and shows what they cost", async () => {
  vi.spyOn(api, "modelLibrary").mockResolvedValue({ models: [model()], roots: [] } as never);
  vi.spyOn(api, "modelRuntimeSettings").mockResolvedValue(view());
  render(ModelRuntimeSettings);
  expect(await screen.findByText("Fits comfortably")).toBeInTheDocument();
  expect(screen.getByText(/Entirely on the GPU · 8K context/)).toBeInTheDocument();
  expect(screen.getByText("GPU 5.0 GB of 10 GB")).toBeInTheDocument();
  expect(screen.getByLabelText("GPU layers mode")).toHaveValue("auto");
  expect(screen.getByRole("option", { name: "32K tokens" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "64K tokens" })).not.toBeInTheDocument();
});

it("previews a change before saving and saves on request", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.spyOn(api, "modelLibrary").mockResolvedValue({ models: [model()], roots: [] } as never);
  vi.spyOn(api, "modelRuntimeSettings").mockResolvedValue(view());
  const preview = vi.spyOn(api, "previewModelRuntimePlan").mockResolvedValue(
    view({ verdict: "insufficient_memory", allowed: false, context_size: 32768, notes: ["This model needs more memory than is free."] }, { context_size: 32768 }),
  );
  const save = vi.spyOn(api, "saveModelRuntimeSettings").mockResolvedValue(view({}, { context_size: 32768 }));
  render(ModelRuntimeSettings);
  await fireEvent.change(await screen.findByLabelText("Context size"), { target: { value: "32768" } });
  await vi.advanceTimersByTimeAsync(300);
  await waitFor(() => expect(preview).toHaveBeenCalledWith("mdl_1", expect.objectContaining({ context_size: 32768 })));
  expect(await screen.findByText("Does not fit in free memory")).toBeInTheDocument();
  expect(screen.getByText(/needs more memory than is free/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
  expect(save).toHaveBeenCalledWith("mdl_1", expect.objectContaining({ context_size: 32768 }));
  expect(await screen.findByRole("status")).toHaveTextContent(/press Restart/);
  vi.useRealTimers();
});

it("says what to do when there are no GGUF models", async () => {
  vi.spyOn(api, "modelLibrary").mockResolvedValue({ models: [], roots: [] } as never);
  render(ModelRuntimeSettings);
  expect(await screen.findByText(/Add a folder with GGUF models/)).toBeInTheDocument();
});
