import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import CommandSandbox from "./CommandSandbox.svelte";

afterEach(() => vi.restoreAllMocks());

const windows = {
  windows_backend: "account",
  applies: true,
  wsl_configured: false,
  wsl_missing: ["distribution_present", "runner_installed"],
  wsl_setup_command: '"C:\\Raiker\\raiker-command-runner.exe" --setup-wsl --linux-runner "x" --rootfs <rootfs.tar>',
};

it("chooses WSL2 for commands and says what is still missing", async () => {
  vi.spyOn(api, "commandSandbox").mockResolvedValue(windows);
  const save = vi
    .spyOn(api, "setCommandSandbox")
    .mockResolvedValue({ ...windows, windows_backend: "wsl" });
  render(CommandSandbox);

  expect(await screen.findByText(/Raiker's WSL distribution is not installed/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole("radio", { name: /WSL2/ }));

  await waitFor(() => expect(save).toHaveBeenCalledWith("wsl"));
  expect(await screen.findByText("Commands now run in WSL2.")).toBeInTheDocument();
  expect(screen.getByText(/commands will be refused until it is/)).toBeInTheDocument();
  expect(screen.getByText(/--setup-wsl --linux-runner/)).toBeInTheDocument();
});

it("is not shown where the choice does not apply", async () => {
  const load = vi.spyOn(api, "commandSandbox").mockResolvedValue({ ...windows, applies: false });
  render(CommandSandbox);

  await waitFor(() => expect(load).toHaveBeenCalled());
  expect(screen.queryByRole("region", { name: "Command sandbox" })).not.toBeInTheDocument();
});
