import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConnectionsView from "./ConnectionsView.svelte";
import { stubFetch } from "../test-helpers";
import type { StoreConnector } from "../apiTypes";

function connector(partial: Partial<StoreConnector> = {}): StoreConnector {
  return {
    connector_id: "github",
    display_name: "GitHub",
    category: "Development",
    description: "Issues, pull requests, and repositories.",
    auth_type: "oauth2",
    host: "api.github.com",
    installed: false,
    enabled: false,
    auth_status: "not_connected",
    vault_configured: true,
    activity_status: "idle",
    active_operation: null,
    last_invoked_at: null,
    ...partial,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("ConnectionsView", () => {
  it("renders the searchable categorized store", async () => {
    stubFetch({
      "GET /api/connector-store": {
        connectors: [
          connector(),
          connector({ connector_id: "booking", display_name: "Booking.com", category: "Travel" }),
          connector({ connector_id: "uber", display_name: "Uber", category: "On-demand" }),
        ],
        count: 3,
        vault_configured: true,
      },
    });
    render(ConnectionsView);
    await waitFor(() => expect(screen.getByText("GitHub")).toBeInTheDocument());
    expect(screen.getByText("Booking.com")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Travel" })).toBeInTheDocument();
    await fireEvent.input(screen.getByPlaceholderText("Search connectors"), {
      target: { value: "uber" },
    });
    expect(screen.getByText("Uber")).toBeInTheDocument();
    expect(screen.queryByText("GitHub")).not.toBeInTheDocument();
  });

  it("shows connected, re-authentication, and disabled lifecycle states", async () => {
    stubFetch({
      "GET /api/connector-store": {
        connectors: [
          connector({ installed: true, enabled: true, auth_status: "connected" }),
          connector({ connector_id: "gmail", display_name: "Gmail", installed: true, auth_status: "reauth_required" }),
          connector({ connector_id: "slack", display_name: "Slack", installed: true, auth_status: "connected" }),
        ],
        count: 3,
        vault_configured: true,
      },
    });
    render(ConnectionsView);
    await waitFor(() => expect(screen.getByText("Connected")).toBeInTheDocument());
    expect(screen.getByText("Requires re-authentication")).toBeInTheDocument();
    expect(screen.getByText("Disabled")).toBeInTheDocument();
  });

  it("opens the encrypted authentication workflow without displaying a credential", async () => {
    stubFetch({
      "GET /api/connector-store": {
        connectors: [connector({ installed: true })], count: 1, vault_configured: true,
      },
    });
    render(ConnectionsView);
    await waitFor(() => expect(screen.getByText("GitHub")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: "Open GitHub" }));
    expect(screen.getByLabelText("OAuth access token")).toHaveAttribute("type", "password");
    expect(screen.getByText(/encrypted for this profile/)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("secret-token");
  });

  it("registers an OpenAPI manifest through the governed API", async () => {
    stubFetch({
      "GET /api/connector-store": {
        connectors: [connector({ installed: true })], count: 1, vault_configured: true,
      },
      "POST /api/connector-store/github/manifest": { ok: true, operations: [{}] },
    });
    render(ConnectionsView);
    await waitFor(() => expect(screen.getByText("GitHub")).toBeInTheDocument());
    await fireEvent.click(screen.getByRole("button", { name: /Import manifest/ }));
    await fireEvent.change(screen.getByLabelText("Connector"), { target: { value: "github" } });
    await fireEvent.input(screen.getByLabelText("Manifest JSON"), {
      target: { value: JSON.stringify({ openapi: "3.0.0", paths: { "/issues": { get: {} } } }) },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Validate and register" }));
    await waitFor(() => expect(screen.getByText("1 operations registered")).toBeInTheDocument());
  });
});
