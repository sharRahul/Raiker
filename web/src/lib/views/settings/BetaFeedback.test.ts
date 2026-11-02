import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, expect, it, vi } from "vitest";
import BetaFeedback from "./BetaFeedback.svelte";
import { api, ApiError } from "../../api";

beforeEach(() => vi.restoreAllMocks());

function stubHost() {
  vi.spyOn(api, "hostUpdate").mockResolvedValue({
    installation: { version: "0.9.0-beta.1", commit: "abcdef1234567" },
  } as never);
}

it("links to prefilled GitHub forms with the host build", async () => {
  stubHost();
  render(BetaFeedback);
  await waitFor(() => expect(screen.getByText("0.9.0-beta.1 (abcdef1)")).toBeInTheDocument());
  const report = screen.getByRole("link", { name: "Report a problem" });
  const href = new URL(report.getAttribute("href") ?? "");
  expect(href.hostname).toBe("github.com");
  expect(href.searchParams.get("template")).toBe("beta-bug.yml");
  expect(href.searchParams.get("version")).toContain("0.9.0-beta.1 (abcdef1)");
  expect(report).toHaveAttribute("rel", "noopener noreferrer");
  expect(screen.getByRole("link", { name: "Suggest an improvement" }).getAttribute("href")).toContain("beta-feedback.yml");
});

it("copies the redacted support bundle only when asked", async () => {
  stubHost();
  const bundle = vi.spyOn(api, "diagnosticsExport").mockResolvedValue({ redacted: true } as never);
  const write = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText: write } });
  render(BetaFeedback);
  expect(bundle).not.toHaveBeenCalled();
  await fireEvent.click(screen.getByRole("button", { name: "Copy diagnostics" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/Copied/));
  expect(write).toHaveBeenCalledWith(expect.stringContaining("redacted"));
});

it("explains a support bundle that redaction refused", async () => {
  stubHost();
  vi.spyOn(api, "diagnosticsExport").mockRejectedValue(new ApiError(422, "support_export_blocked", "blocked"));
  render(BetaFeedback);
  await fireEvent.click(screen.getByRole("button", { name: "Copy diagnostics" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/still looked like a secret/));
});

it("still offers the forms when the host build cannot be read", async () => {
  vi.spyOn(api, "hostUpdate").mockRejectedValue(new Error("offline"));
  render(BetaFeedback);
  expect(await screen.findByRole("link", { name: "Report a problem" })).toBeInTheDocument();
});
