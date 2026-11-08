import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import BrowserSignIn from "./BrowserSignIn.svelte";
import { api, ApiError } from "../api";

const URL = "https://accounts.google.com/o/oauth2/v2/auth?client_id=x&state=s";

function store(status: string) {
  return { connectors: [{ connector_id: "gmail", auth_status: status }], count: 1, vault_configured: true };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

it("opens the provider's sign-in page and turns connected when the browser comes back", async () => {
  vi.spyOn(api, "startConnectorSignIn").mockResolvedValue({ ok: true, connector_id: "gmail", authorize_url: URL });
  const opened = vi.spyOn(window, "open").mockReturnValue(null);
  const listing = vi.spyOn(api, "connectorStore")
    .mockResolvedValueOnce(store("not_connected") as never)
    .mockResolvedValue(store("connected") as never);
  const onconnected = vi.fn();
  render(BrowserSignIn, { connectorId: "gmail", name: "Gmail", provider: "google", onconnected });

  await fireEvent.click(screen.getByRole("button", { name: "Sign in with Google" }));
  expect(opened).toHaveBeenCalledWith(URL, "_blank", "noopener,noreferrer");
  expect(await screen.findByText(/Finish signing in to Google in your browser/)).toBeInTheDocument();

  await vi.advanceTimersByTimeAsync(4500);
  await waitFor(() => expect(onconnected).toHaveBeenCalled());
  expect(screen.getByText("Gmail is connected.")).toBeInTheDocument();
  expect(listing).toHaveBeenCalledTimes(2);
});

it("asks for the owner's own client once, then signs in", async () => {
  const start = vi.spyOn(api, "startConnectorSignIn")
    .mockRejectedValueOnce(new ApiError(409, "oauth_client_not_configured", "not configured"))
    .mockResolvedValue({ ok: true, connector_id: "outlook", authorize_url: URL });
  const saved = vi.spyOn(api, "saveConnectorOauthClient").mockResolvedValue({ ok: true, provider: "microsoft" });
  vi.spyOn(window, "open").mockReturnValue(null);
  vi.spyOn(api, "connectorStore").mockResolvedValue(store("not_connected") as never);
  render(BrowserSignIn, { connectorId: "outlook", name: "Outlook", provider: "microsoft" });

  await fireEvent.click(screen.getByRole("button", { name: "Sign in with Microsoft" }));
  expect(await screen.findByText(/Mobile and desktop/)).toBeInTheDocument();
  // Microsoft public clients have no secret, so none is asked for.
  expect(screen.queryByLabelText("Client secret")).toBeNull();
  await fireEvent.input(screen.getByLabelText("Client ID"), { target: { value: "00000000-aaaa" } });
  await fireEvent.click(screen.getByRole("button", { name: "Save and sign in with Microsoft" }));

  await waitFor(() => expect(saved).toHaveBeenCalledWith("microsoft", "00000000-aaaa", undefined));
  await waitFor(() => expect(start).toHaveBeenCalledTimes(2));
});
