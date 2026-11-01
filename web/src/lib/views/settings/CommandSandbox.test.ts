import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../../api";
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
  expect(screen.getByRole("button", { name: "Set up WSL2" })).toBeInTheDocument();
});

it("is not shown where the choice does not apply", async () => {
  const load = vi.spyOn(api, "commandSandbox").mockResolvedValue({ ...windows, applies: false });
  render(CommandSandbox);

  await waitFor(() => expect(load).toHaveBeenCalled());
  expect(screen.queryByRole("region", { name: "Command sandbox" })).not.toBeInTheDocument();
});

it("sets WSL2 up from a root filesystem the owner names", async () => {
  vi.spyOn(api, "commandSandbox").mockResolvedValue(windows);
  const setup = vi
    .spyOn(api, "setupCommandSandboxWsl")
    .mockResolvedValue({ ...windows, wsl_configured: true, wsl_missing: [] });
  render(CommandSandbox);

  const field = await screen.findByRole("textbox", { name: /Linux root filesystem/ });
  await fireEvent.input(field, { target: { value: "  C:\\Temp\\ubuntu-base.tar.gz " } });
  await fireEvent.click(screen.getByRole("button", { name: "Set up WSL2" }));

  await waitFor(() => expect(setup).toHaveBeenCalledWith("C:\\Temp\\ubuntu-base.tar.gz"));
  expect(await screen.findAllByText("WSL2 is set up.")).not.toHaveLength(0);
});

it("explains a refused setup in words the owner can act on", async () => {
  vi.spyOn(api, "commandSandbox").mockResolvedValue(windows);
  vi.spyOn(api, "setupCommandSandboxWsl").mockRejectedValue(
    new ApiError(422, "native_sandbox_wsl_rootfs_invalid", "refused"),
  );
  render(CommandSandbox);

  await fireEvent.input(await screen.findByRole("textbox", { name: /Linux root filesystem/ }), {
    target: { value: "C:\\notes.txt" },
  });
  await fireEvent.click(screen.getByRole("button", { name: "Set up WSL2" }));

  expect(await screen.findByText("That file is not a .tar or .tar.gz root filesystem.")).toBeInTheDocument();
});

it("removes WSL2 only after the owner confirms", async () => {
  vi.spyOn(api, "commandSandbox").mockResolvedValue({ ...windows, windows_backend: "wsl", wsl_configured: true, wsl_missing: [] });
  const remove = vi.spyOn(api, "removeCommandSandboxWsl").mockResolvedValue(windows);
  render(CommandSandbox);

  await fireEvent.click(await screen.findByRole("button", { name: "Remove WSL2…" }));
  expect(remove).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent(/every task copy inside it/);
  await fireEvent.click(screen.getByRole("button", { name: "Remove WSL2" }));

  await waitFor(() => expect(remove).toHaveBeenCalled());
  expect(await screen.findByText("WSL2 removed. Commands run as the sandbox account.")).toBeInTheDocument();
});
