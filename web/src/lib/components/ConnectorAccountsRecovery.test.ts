import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import ConnectorAccounts from "./ConnectorAccounts.svelte";
import { stubFetch } from "../test-helpers";
import type { StoreConnector } from "../apiTypes";

afterEach(() => vi.unstubAllGlobals());

it("keeps a private account credential entry on failure without claiming rollback", async () => {
  const connector: StoreConnector = {
    connector_id: "gmail", display_name: "Gmail", category: "Email", description: "Email",
    auth_type: "oauth2", host: "gmail.googleapis.com", installed: true, enabled: false,
    auth_status: "not_connected", vault_configured: true, activity_status: "idle",
    active_operation: null, last_invoked_at: null, operations: [], support_level: "experimental",
    accounts: [{ account_id: "default", label: "Work Gmail", is_default: true, auth_status: "not_connected" }],
  };
  stubFetch({ "PUT /api/connector-store/gmail/accounts/default/credentials": {
    __status: 503, detail: { reason_code: "injected_failure" },
  } });
  const onchanged = vi.fn();
  render(ConnectorAccounts, { connector, onchanged });
  const input = screen.getByLabelText(/OAuth access token/);
  await fireEvent.input(input, { target: { value: "private-fixture" } });
  await fireEvent.click(screen.getByRole("button", { name: "Connect" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("saved account and sign-in are unconfirmed");
  expect(screen.getByRole("alert")).toHaveTextContent("Refresh connections");
  expect(input).toHaveValue("private-fixture");
  expect(input).toHaveAttribute("type", "password");
  expect(screen.getByRole("alert")).not.toHaveTextContent("private-fixture");
  expect(onchanged).not.toHaveBeenCalled();
});
