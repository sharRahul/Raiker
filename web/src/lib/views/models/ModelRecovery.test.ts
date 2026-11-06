import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../../api";
import { stubFetch } from "../../test-helpers";
import DownloadsPanel from "./DownloadsPanel.svelte";
import LocalLibraryPanel from "./LocalLibraryPanel.svelte";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

function activity(state = "failed", partial = false) {
  stubFetch({ "GET /api/model-operations": { items: [{
    operation_id: "mop_recovery", kind: "download", target: "Recovery model",
    state, phase: state, progress_percent: null, retryable: true,
    partial_files_present: partial,
  }] } });
  render(DownloadsPanel);
}
const refused = () => Promise.reject(new ApiError(503, "test_refusal", "Injected failure"));
async function more(label: string) {
  await fireEvent.click(await screen.findByRole("button", { name: /More actions for/ }));
  await fireEvent.click(screen.getByRole("menuitem", { name: label }));
}

it("keeps a failed retry visible after a successful status poll", async () => {
  vi.useFakeTimers();
  const reads = vi.spyOn(api, "modelOperations");
  vi.spyOn(api, "retryModelOperation").mockImplementation(refused);
  activity();
  await vi.advanceTimersByTimeAsync(0);
  await fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await vi.advanceTimersByTimeAsync(0);
  expect(screen.getByRole("alert")).toHaveTextContent("Could not retry the model job");
  // Verify the scheduled read actually ran and did not erase the action error.
  expect(reads).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(15_000);
  expect(reads).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("alert")).toHaveTextContent("before retrying again");
});

it("reports a failed cancellation without claiming the running job stopped", async () => {
  vi.spyOn(api, "cancelModelOperation").mockImplementation(refused);
  activity("running");
  await fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Cancellation could not be confirmed");
});

it("reports a failed record cleanup and keeps the job", async () => {
  vi.spyOn(api, "cleanupModelOperation").mockImplementation(refused);
  activity();
  await more("Clear record");
  expect(await screen.findByRole("alert")).toHaveTextContent("Record removal could not be confirmed");
  expect(screen.getByText("Recovery model")).toBeInTheDocument();
});

it("shows a partial-file inspection error even when no confirmation opened", async () => {
  vi.spyOn(api, "partialFiles").mockImplementation(refused);
  activity("failed", true);
  await more("Delete partial files");
  expect(await screen.findByRole("alert")).toHaveTextContent("file list is unavailable");
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});

it("keeps the deletion review after a failed delete and avoids inventing an ACL refusal", async () => {
  vi.spyOn(api, "partialFiles").mockResolvedValue({
    path: "/models/partial", paths: ["/models/partial"], exists: true, bytes: 12, file_count: 1,
  });
  vi.spyOn(api, "deletePartialFiles").mockImplementation(refused);
  activity("failed", true);
  await more("Delete partial files");
  await fireEvent.click(await screen.findByRole("button", { name: "Delete files" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Deletion could not be confirmed");
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  expect(screen.queryByText(/not inside your approved/)).not.toBeInTheDocument();
});

it("offers status recovery when the activity read fails", async () => {
  stubFetch({ "GET /api/model-operations": { __status: 503 } });
  render(DownloadsPanel);
  expect(await screen.findByRole("alert")).toHaveTextContent("Choose Retry status");
  expect(screen.getByRole("button", { name: "Retry status" })).toBeEnabled();
  expect(screen.queryByText("No model activity yet")).not.toBeInTheDocument();
});

it("catches a failed folder removal and leaves the approved folder visible", async () => {
  stubFetch({ "GET /api/model-library": { roots: [{ path: "/models" }], models: [] } });
  vi.spyOn(api, "removeModelLibraryRoot").mockImplementation(refused);
  render(LocalLibraryPanel);
  await screen.findByText("/models");
  await fireEvent.click(screen.getByRole("button", { name: /Remove/ }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Could not remove the model folder"));
  expect(screen.getByText("/models")).toBeInTheDocument();
});

it("does not keep announcing loading after a library read failed", async () => {
  stubFetch({ "GET /api/model-library": { __status: 503 } });
  render(LocalLibraryPanel);
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the local model library");
  expect(screen.queryByText("Loading your model library…")).not.toBeInTheDocument();
});
