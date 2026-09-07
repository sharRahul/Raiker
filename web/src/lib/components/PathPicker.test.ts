import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import type { HostPathListing } from "../apiTypes";
import PathPicker from "./PathPicker.svelte";

afterEach(() => vi.restoreAllMocks());

function listing(partial: Partial<HostPathListing> = {}): HostPathListing {
  return {
    path: "",
    parent: null,
    separator: "\\",
    workspace_root: "C:\\ws",
    entries: [],
    truncated: false,
    missing: false,
    ...partial,
  };
}

it("opens somewhere and walks into a folder", async () => {
  const paths = vi.spyOn(api, "hostPaths");
  paths.mockResolvedValueOnce(
    listing({ entries: [{ name: "D:", path: "D:\\", is_directory: true }] }),
  );
  paths.mockResolvedValueOnce(
    listing({
      path: "D:\\",
      parent: "",
      entries: [{ name: "Models", path: "D:\\Models", is_directory: true }],
    }),
  );
  render(PathPicker, { props: { onchoose: vi.fn(), onclose: vi.fn() } });

  await fireEvent.click(await screen.findByRole("button", { name: /D:/ }));
  expect(await screen.findByRole("button", { name: /Models/ })).toBeInTheDocument();
});

it("answers with the absolute path a browser could not have produced", async () => {
  vi.spyOn(api, "hostPaths").mockResolvedValue(
    listing({
      path: "D:\\Models",
      parent: "D:\\",
      entries: [{ name: "gguf", path: "D:\\Models\\gguf", is_directory: true }],
    }),
  );
  const chose = vi.fn();
  render(PathPicker, { props: { start: "D:\\Models", onchoose: chose, onclose: vi.fn() } });

  // The folder being looked at is the default answer, so no selection is needed.
  await waitFor(() => expect(screen.getByRole("button", { name: "Use" })).toBeEnabled());
  await fireEvent.click(screen.getByRole("button", { name: "Use" }));
  expect(chose).toHaveBeenCalledWith("D:\\Models");
});

it("gives a workspace field a relative path and will not climb above the workspace", async () => {
  const paths = vi.spyOn(api, "hostPaths");
  // First call is the top, which is only how the host is asked where the
  // workspace is; the picker immediately lands there.
  paths.mockResolvedValueOnce(listing());
  paths.mockResolvedValueOnce(
    listing({
      path: "C:\\ws",
      parent: "C:\\",
      entries: [{ name: "projects", path: "C:\\ws\\projects", is_directory: true }],
    }),
  );
  paths.mockResolvedValueOnce(
    listing({ path: "C:\\ws\\projects", parent: "C:\\ws", entries: [] }),
  );
  const chose = vi.fn();
  render(PathPicker, { props: { insideWorkspace: true, onchoose: chose, onclose: vi.fn() } });

  await waitFor(() => expect(screen.getByRole("button", { name: "Up one level" })).toBeDisabled());
  await fireEvent.click(await screen.findByRole("button", { name: /projects/ }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Use" })).toBeEnabled());
  await fireEvent.click(screen.getByRole("button", { name: "Use" }));
  expect(chose).toHaveBeenCalledWith("projects");
});

it("says a location is gone rather than showing it as empty", async () => {
  vi.spyOn(api, "hostPaths").mockResolvedValue(
    listing({ path: "D:\\gone", parent: "D:\\", missing: true }),
  );
  render(PathPicker, { props: { start: "D:\\gone", onchoose: vi.fn(), onclose: vi.fn() } });

  expect(await screen.findByRole("alert")).toHaveTextContent(/gone, or Raiker cannot read it/);
  expect(screen.getByRole("button", { name: "Use" })).toBeDisabled();
});
