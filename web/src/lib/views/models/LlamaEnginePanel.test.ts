import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, expect, it, vi } from "vitest";
import LlamaEnginePanel from "./LlamaEnginePanel.svelte";
import { api } from "../../api";
import type { ModelOperation } from "../../apiTypes";
import type { LlamaRuntimeOverview, SlotHealth } from "../../generated/apiContract";

const GIB = 1024 ** 3;

function plan(): SlotHealth["plan"] {
  return {
    backend: "cuda", gpu_layers: 33, total_layers: 32, full_offload: true, context_size: 8192,
    trained_context: 131072, threads: null, flash_attention: "auto", kv_cache_type: "f16",
    weights_bytes: 4 * GIB, kv_cache_bytes: GIB, gpu_bytes: 6 * GIB, system_bytes: GIB / 2,
    system_weights_bytes: 0, gpu_budget_bytes: 10 * GIB, system_budget_bytes: 20 * GIB,
    verdict: "fits", allowed: true, notes: [], args: [], estimated: true,
    settings: { gpu_layers: null, context_size: null, threads: null, flash_attention: "auto", kv_cache_type: "f16", allow_overcommit: false },
  };
}

function overview(over: Partial<LlamaRuntimeOverview> = {}): LlamaRuntimeOverview {
  return {
    installation: null,
    executable: { path: null, source: "none", backend: null },
    hardware: {
      os: "linux", arch: "x64", cpu_cores: 8, total_memory_bytes: 32 * GIB, available_memory_bytes: 20 * GIB,
      gpus: [{ vendor: "nvidia", name: "NVIDIA RTX 4070", memory_total_bytes: 12 * GIB, memory_free_bytes: 11 * GIB, discrete: true, cuda_version: "12.4", unified_memory: false }],
      vulkan_available: true, metal_available: false, backends: ["cuda", "vulkan", "cpu"],
      recommended_backend: "cuda", reason: "NVIDIA RTX 4070 runs local models fastest through CUDA.", detected_at: 0,
    },
    slots: [], restore_failures: [],
    release_page: "https://github.com/ggml-org/llama.cpp/releases",
    license_url: "https://github.com/ggml-org/llama.cpp/blob/master/LICENSE",
    ...over,
  };
}

function operation(over: Partial<ModelOperation>): ModelOperation {
  return {
    operation_id: "mop_1", owner_principal_id: "o", kind: "install", target: "llama.cpp", state: "running",
    phase: "downloading_llama_cpp", progress_bytes: 50, total_bytes: 100, progress_percent: 50, source_url: null,
    destination: null, error_code: null, error_detail: null, created_at: "2026-11-01T00:00:00Z",
    updated_at: "2026-11-01T00:00:00Z", retryable: true, partial_files_present: false, ...over,
  } as ModelOperation;
}

beforeEach(() => vi.restoreAllMocks());

it("shows the hardware and offers the recommended engine when none is installed", async () => {
  vi.spyOn(api, "llamaRuntime").mockResolvedValue(overview());
  vi.spyOn(api, "modelOperations").mockResolvedValue({ items: [] });
  render(LlamaEnginePanel);
  expect(await screen.findByText("Not installed")).toBeInTheDocument();
  expect(screen.getByText(/NVIDIA RTX 4070 · 12 GB/)).toBeInTheDocument();
  expect(screen.getByText(/fastest through CUDA/)).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Automatic (NVIDIA CUDA)" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /ggml-org\/llama.cpp/ })).toHaveAttribute("href", overview().release_page);
});

it("installs with the chosen backend and shows progress", async () => {
  vi.spyOn(api, "llamaRuntime").mockResolvedValue(overview());
  const ops = vi.spyOn(api, "modelOperations").mockResolvedValue({ items: [] });
  const install = vi.spyOn(api, "installLlamaRuntime").mockResolvedValue(operation({}) as never);
  render(LlamaEnginePanel);
  const select = await screen.findByLabelText("Engine build");
  await fireEvent.change(select, { target: { value: "vulkan" } });
  ops.mockResolvedValue({ items: [operation({})] });
  await fireEvent.click(screen.getByRole("button", { name: "Install llama.cpp" }));
  expect(install).toHaveBeenCalledWith("vulkan");
  expect(await screen.findByText("Downloading 50%")).toBeInTheDocument();
});

it("explains a failed install in words", async () => {
  vi.spyOn(api, "llamaRuntime").mockResolvedValue(overview());
  vi.spyOn(api, "modelOperations").mockResolvedValue({
    items: [operation({ state: "failed", phase: "failed", error_code: "llama_cpp_install_failed", error_detail: "llama_cpp_digest_mismatch" })],
  });
  render(LlamaEnginePanel);
  expect(await screen.findByRole("alert")).toHaveTextContent(/did not match its published checksum/);
});

it("lists served models with their sizing and can stop one", async () => {
  const slot: SlotHealth = {
    slot_profile_id: "raiker-local-llama-cpp", model_id: "mdl_1", model_path: "/models/qwen-7b.gguf",
    state: "ready", endpoint: "http://127.0.0.1:8080/v1", pid: 42, restarts: 1,
    last_error: "local_runtime_out_of_memory", backend: "cuda", plan: plan(), log_path: null,
  };
  vi.spyOn(api, "llamaRuntime").mockResolvedValue(
    overview({
      installation: { tag: "b7000", backend: "cuda", os: "linux", arch: "x64", cuda_version: "12.8", directory: "/d", executable: "/d/llama-server", version_text: "", devices: [], installed_at: "", assets: [] },
      executable: { path: "/d/llama-server", source: "managed", backend: "cuda" },
      slots: [slot],
    }),
  );
  vi.spyOn(api, "modelOperations").mockResolvedValue({ items: [] });
  const stop = vi.spyOn(api, "stopLlamaSlot").mockResolvedValue(overview());
  render(LlamaEnginePanel);
  expect(await screen.findByText("b7000 · NVIDIA CUDA")).toBeInTheDocument();
  expect(screen.getByText("qwen-7b.gguf")).toBeInTheDocument();
  expect(screen.getByText("Serving")).toBeInTheDocument();
  expect(screen.getByText(/Entirely on the GPU · 8K context/)).toBeInTheDocument();
  expect(screen.getByText(/restarted 1×/)).toBeInTheDocument();
  expect(screen.getByText(/ran out of memory while loading/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole("button", { name: "Stop" }));
  expect(stop).toHaveBeenCalledWith("raiker-local-llama-cpp");
  await waitFor(() => expect(screen.queryByText("qwen-7b.gguf")).not.toBeInTheDocument());
});

it("asks before removing the engine and explains a refusal", async () => {
  vi.spyOn(api, "llamaRuntime").mockResolvedValue(
    overview({
      installation: { tag: "b7000", backend: "cpu", os: "linux", arch: "x64", cuda_version: null, directory: "/d", executable: "/d/llama-server", version_text: "", devices: [], installed_at: "", assets: [] },
      executable: { path: "/d/llama-server", source: "managed", backend: "cpu" },
    }),
  );
  vi.spyOn(api, "modelOperations").mockResolvedValue({ items: [] });
  const { ApiError } = await import("../../api");
  vi.spyOn(api, "uninstallLlamaRuntime").mockRejectedValue(new ApiError(409, "local_runtime_in_use", "conflict"));
  render(LlamaEnginePanel);
  await fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
  const dialog = screen.getByRole("alertdialog", { name: "Remove the engine" });
  expect(dialog).toHaveTextContent(/Your models stay in your library/);
  await fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[1]);
  expect(await screen.findByRole("alert")).toHaveTextContent(/Stop every served model/);
});

it("reports an available update", async () => {
  vi.spyOn(api, "llamaRuntime").mockResolvedValue(
    overview({
      installation: { tag: "b6900", backend: "cpu", os: "linux", arch: "x64", cuda_version: null, directory: "/d", executable: "/d/x", version_text: "", devices: [], installed_at: "", assets: [] },
      executable: { path: "/d/x", source: "managed", backend: "cpu" },
    }),
  );
  vi.spyOn(api, "modelOperations").mockResolvedValue({ items: [] });
  vi.spyOn(api, "checkLlamaRuntimeUpdate").mockResolvedValue({ installed_tag: "b6900", latest_tag: "b7000", update_available: true, published_at: null });
  render(LlamaEnginePanel);
  await fireEvent.click(await screen.findByRole("button", { name: "Check for updates" }));
  expect(await screen.findByText(/llama.cpp b7000 is available \(you have b6900\)/)).toBeInTheDocument();
});
