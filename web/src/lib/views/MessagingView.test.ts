// Messaging is the destination a channel reaches Raiker through. It was a tab
// inside Extensions, beside the connectors, servers and hooks the agent *uses*;
// a channel is a place a person writes from, which is a different thing.
//
// The contract these tests hold is the one that matters about any channel: a
// message is untrusted content with a named sender who is not you, and pairing,
// enabling, allowlisting and reaching are four separate facts that must never
// be allowed to imply one another.
import { render, screen } from "@testing-library/svelte";
import { fireEvent, within } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import MessagingView from "./MessagingView.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MessagingView", () => {
  // BUG-225 — the transport was built and had no owner surface, so the tab said
  // channels did not exist. It has to state the contract *and* the three facts
  // that decide whether anything can actually be delivered.
  const channelsView = (overrides: Record<string, unknown> = {}) => ({
    profiles: [
      {
        connector_id: "channel.webhooks",
        channel_type: "webhooks",
        display_name: "Webhooks",
        transport: "signed_http_callback",
        auth_method: "shared_secret",
        default_state: "disabled",
        requires_pairing: true,
        requires_sender_allowlist: true,
        requires_network: true,
        linked: false,
        enabled: false,
        pairing_id: null,
        display_label: null,
        sender_count: 0,
        senders: [],
      },
    ],
    error: null,
    outbound: {
      capability: "external_channel_runtime",
      gate_state: "disabled",
      runtime_enabled: false,
      egress_configured: false,
      egress_host_count: 0,
      signing_configured: false,
    },
    inbound: {
      secret_configured: false,
      rate_limit_per_minute: 60,
      quarantined: true,
      instructions_inert: true,
    },
    ...overrides,
  });

  it("states what a channel message is, in the owner's words", async () => {
    stubFetch({ "GET /api/channels": channelsView() });
    render(MessagingView);
    expect(
      await screen.findByText(/untrusted content with a named sender who is not you/i),
    ).toBeInTheDocument();
  });

  it("reports the three things that decide whether anything can be delivered", async () => {
    stubFetch({ "GET /api/channels": channelsView() });
    render(MessagingView);
    await screen.findByText("Outbound");
    const posture = screen.getByTestId("channel-posture");
    // Each has its own remedy, so each is its own row rather than one flag.
    expect(within(posture).getByText("Outbound").closest("li")).toHaveTextContent(
      "Capability off",
    );
    expect(within(posture).getByText("Egress").closest("li")).toHaveTextContent(
      "None allowlisted",
    );
    expect(within(posture).getByText("Inbound").closest("li")).toHaveTextContent(
      "Refusing everything",
    );
    // Allowlisting says *who* may speak; the budget says how often. An
    // allowlisted sender was unbounded until this row existed.
    expect(within(posture).getByText("Rate limit").closest("li")).toHaveTextContent("60/min");
    // The webhook profile declares a *signed* callback. Whether a delivery is
    // actually signed is a fact about the bytes, not about the profile.
    expect(within(posture).getByText("Signing").closest("li")).toHaveTextContent("Unsigned");
  });

  it("offers pairing, and says pairing is not switching on", async () => {
    stubFetch({ "GET /api/channels": channelsView() });
    render(MessagingView);
    await screen.findByText("Webhooks");
    const profiles = screen.getByTestId("channel-profiles");
    expect(within(profiles).getByText("Webhooks").closest("li")).toHaveTextContent("Not linked");
    await fireEvent.click(within(profiles).getByRole("button", { name: "Pair" }));
    expect(
      screen.getByText(/Pairing does not switch it on, and it does not trust anyone/i),
    ).toBeInTheDocument();
    // The profile requires a sender allowlist, so pairing must ask for one.
    expect(screen.getByLabelText("Allowed senders")).toBeInTheDocument();
  });

  it("a linked channel that is off reads as linked and off, not as ready", async () => {
    stubFetch({
      "GET /api/channels": channelsView({
        profiles: [
          {
            ...channelsView().profiles[0],
            linked: true,
            enabled: false,
            pairing_id: "chp_1",
            display_label: "Webhooks",
            sender_count: 2,
            senders: ["ops", "oncall"],
          },
        ],
      }),
    });
    render(MessagingView);
    await screen.findByText("Webhooks");
    const profiles = screen.getByTestId("channel-profiles");
    const row = within(profiles).getByText("Webhooks").closest("li");
    expect(row).toHaveTextContent("Linked, off");
    expect(row).toHaveTextContent("2 senders");
    expect(within(profiles).getByRole("button", { name: "Turn on" })).toBeInTheDocument();
    expect(within(profiles).getByRole("button", { name: "Unpair" })).toBeInTheDocument();
  });

  it("a test delivery says it runs the governed path, not a shortcut", async () => {
    stubFetch({
      "GET /api/channels": channelsView({
        profiles: [
          {
            ...channelsView().profiles[0],
            linked: true,
            enabled: true,
            pairing_id: "chp_1",
            display_label: "Webhooks",
            sender_count: 1,
            senders: ["ops"],
          },
        ],
      }),
    });
    render(MessagingView);
    await screen.findByText("Webhooks");
    const profiles = screen.getByTestId("channel-profiles");
    await fireEvent.click(
      within(profiles).getByRole("button", { name: "Send a test delivery" }),
    );
    expect(screen.getByLabelText("Destination URL")).toBeInTheDocument();
    expect(
      screen.getByText(/the capability gate, the decision mode, the egress allowlist and the audit event all apply/i),
    ).toBeInTheDocument();
  });

  // The contract used to be a standalone "Routing contract" card at the foot of
  // the tab, restating in different words a note already sitting inside the
  // routing form. Two statements of one contract on one page, and the card was
  // the copy nobody read at a decision point. It is asserted here where the
  // choice is actually made, which is the only place it changes an outcome.
  it("states the routing contract where the route is chosen", async () => {
    stubFetch({
      "GET /api/channels": channelsView({
        profiles: [
          {
            connector_id: "channel.webhooks",
            channel_type: "webhooks",
            display_name: "Webhooks",
            transport: "signed_http_callback",
            auth_method: "shared_secret",
            default_state: "disabled",
            requires_pairing: true,
            requires_sender_allowlist: true,
            requires_network: true,
            linked: true,
            enabled: false,
            pairing_id: "chp_1",
            display_label: "Webhooks",
            sender_count: 1,
            senders: ["ops@example.com"],
          },
        ],
      }),
    });
    render(MessagingView);
    await fireEvent.click(await screen.findByRole("button", { name: "Routing" }));

    expect(await screen.findByText(/Record only is the default/i)).toBeInTheDocument();
    expect(screen.getByText(/messages cannot choose their route/i)).toBeInTheDocument();
    expect(screen.getByText(/side questions have no tool budget/i)).toBeInTheDocument();
    expect(
      screen.getByText(/approvals require the exact relay and action identity/i),
    ).toBeInTheDocument();
  });

  it("does not restate that contract a second time on the page", async () => {
    stubFetch({ "GET /api/channels": channelsView() });
    render(MessagingView);
    await screen.findByText(/untrusted content with a named sender who is not you/i);
    expect(screen.queryByRole("heading", { name: "Routing contract" })).toBeNull();
  });
});
