import { describe, expect, it } from "vitest";
import {
  REASON_LABELS,
  backendLabel,
  contextChoices,
  formatBytes,
  formatTokens,
  offloadLabel,
  operationReason,
  reasonLabel,
  slotTone,
  usage,
} from "./llamaRuntime";

describe("llama.cpp engine labels", () => {
  it("names every backend and falls back for unknown ones", () => {
    expect(backendLabel("cuda")).toBe("NVIDIA CUDA");
    expect(backendLabel("metal")).toBe("Apple Metal");
    expect(backendLabel(null)).toBe("Unknown");
    expect(backendLabel("rocm")).toBe("rocm");
  });

  it("never shows a raw reason code", () => {
    expect(reasonLabel("local_runtime_insufficient_memory")).toMatch(/Not enough free memory/);
    expect(reasonLabel("something_new")).toMatch(/Something went wrong/);
    expect(reasonLabel(null)).toBe("");
    for (const sentence of Object.values(REASON_LABELS)) expect(sentence).not.toMatch(/_/);
  });

  it("prefers an operation's specific detail over its generic code", () => {
    expect(operationReason({ error_code: "local_model_deploy_failed", error_detail: "llama_cpp_model_unsupported" }))
      .toMatch(/newer llama.cpp/);
    expect(operationReason({ error_code: "llama_cpp_install_failed", error_detail: null })).toMatch(/could not be installed/);
  });

  it("describes offload in words", () => {
    expect(offloadLabel({ gpu_layers: 33, total_layers: 32, full_offload: true, backend: "cuda" })).toBe("Entirely on the GPU");
    expect(offloadLabel({ gpu_layers: 18, total_layers: 32, full_offload: false, backend: "vulkan" })).toBe("18 of 32 layers on the GPU");
    expect(offloadLabel({ gpu_layers: 0, total_layers: 32, full_offload: false, backend: "cuda" })).toBe("Processor only");
  });

  it("formats sizes, tokens and usage", () => {
    expect(formatBytes(4.7 * 1024 ** 3)).toBe("4.7 GB");
    expect(formatBytes(24 * 1024 ** 3)).toBe("24 GB");
    expect(formatBytes(300 * 1024 ** 2)).toBe("300 MB");
    expect(formatBytes(null)).toBe("unknown");
    expect(formatTokens(8192)).toBe("8K");
    expect(formatTokens(1000)).toBe("1,000");
    expect(usage(5, 10)).toBe(0.5);
    expect(usage(20, 10)).toBe(1);
    expect(usage(5, null)).toBe(1);
    expect(usage(0, null)).toBeNull();
  });

  it("offers contexts up to the trained length", () => {
    expect(contextChoices(8192)).toEqual([2048, 4096, 8192]);
    expect(contextChoices(40000)).toEqual([2048, 4096, 8192, 16384, 32768, 40000]);
    expect(contextChoices(null)).toEqual([2048, 4096, 8192, 16384, 32768]);
  });

  it("colours slot states", () => {
    expect(slotTone("ready")).toBe("ok");
    expect(slotTone("restarting")).toBe("busy");
    expect(slotTone("failed")).toBe("bad");
  });
});
