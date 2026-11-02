import { fireEvent, render, screen } from "@testing-library/svelte";
import { beforeEach, expect, it, vi } from "vitest";
import LocalFrameworkRow from "./LocalFrameworkRow.svelte";
import { api } from "../../api";
import { modelProfile } from "../../test-helpers";

const MODEL = {
  owner_principal_id: "o", root_path: "/m", model_id: "mdl_1", name: "Qwen 7B", architecture: "qwen2",
  quantization: "Q4_K_M", primary_path: "/m/qwen.gguf", shard_count: 1, expected_shards: 1, complete: true,
  size_bytes: 1, indexed_at: "", format: "gguf" as const,
};

function engine(source: "none" | "managed") {
  return { executable: { path: source === "none" ? null : "/x", source, backend: null } } as never;
}

beforeEach(() => vi.restoreAllMocks());

async function choose() {
  vi.spyOn(api, "modelLibrary").mockResolvedValue({ models: [MODEL], roots: [] } as never);
  render(LocalFrameworkRow, {
    provider: "llama.cpp", title: "GGUF", format: "gguf", description: "",
    profiles: [modelProfile({ profile_id: "raiker-local-llama-cpp", provider: "llama.cpp" })],
  });
  const select = await screen.findByLabelText("GGUF model 1");
  await screen.findByRole("option", { name: "Qwen 7B" });
  await fireEvent.change(select, { target: { value: "mdl_1" } });
}

it("asks before downloading the engine, then installs and serves", async () => {
  await choose();
  vi.spyOn(api, "llamaRuntime").mockResolvedValue(engine("none"));
  const deploy = vi.spyOn(api, "deployLocalModel").mockResolvedValue({} as never);
  await fireEvent.click(screen.getByRole("button", { name: "Serve selected (1)" }));
  const dialog = await screen.findByRole("alertdialog", { name: "Install the llama.cpp engine" });
  expect(dialog).toHaveTextContent(/official build/);
  expect(deploy).not.toHaveBeenCalled();
  await fireEvent.click(screen.getByRole("button", { name: "Install and serve" }));
  expect(deploy).toHaveBeenCalledWith("mdl_1", "raiker-local-llama-cpp", true);
});

it("serves straight away when the engine is already installed", async () => {
  await choose();
  vi.spyOn(api, "llamaRuntime").mockResolvedValue(engine("managed"));
  const deploy = vi.spyOn(api, "deployLocalModel").mockResolvedValue({} as never);
  await fireEvent.click(screen.getByRole("button", { name: "Serve selected (1)" }));
  expect(await screen.findByRole("status")).toHaveTextContent(/queued/);
  expect(deploy).toHaveBeenCalledWith("mdl_1", "raiker-local-llama-cpp", false);
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});
