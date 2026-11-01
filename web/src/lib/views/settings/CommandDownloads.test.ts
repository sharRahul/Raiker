import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import CommandDownloads from "./CommandDownloads.svelte";

afterEach(() => vi.restoreAllMocks());

const off = { enabled: false, domains: ["pypi.org"], defaults: ["pypi.org", "registry.npmjs.org"] };

it("turns downloads on for exactly the listed hosts", async () => {
  vi.spyOn(api, "commandEgress").mockResolvedValue(off);
  const save = vi.spyOn(api, "setCommandEgress").mockResolvedValue({ ...off, enabled: true });
  render(CommandDownloads);

  await fireEvent.click(await screen.findByRole("checkbox", { name: /Allow downloads/ }));

  await waitFor(() => expect(save).toHaveBeenCalledWith(true, ["pypi.org"]));
  expect(await screen.findByText("Downloads allowed for the listed hosts.")).toBeInTheDocument();
});

it("restores the package registries into the list without saving", async () => {
  vi.spyOn(api, "commandEgress").mockResolvedValue(off);
  const save = vi.spyOn(api, "setCommandEgress");
  render(CommandDownloads);

  await fireEvent.click(await screen.findByRole("button", { name: "Restore package registries" }));

  expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("pypi.org\nregistry.npmjs.org");
  expect(save).not.toHaveBeenCalled();
});
