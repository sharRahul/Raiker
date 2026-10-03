// Messaging is the destination a channel reaches Raiker through. It was a tab
// inside Extensions, beside the connectors, servers and hooks the agent *uses*;
// a channel is a place a person writes from, which is a different thing.
//
// The contract these tests hold is the one that matters about any channel: a
// message is untrusted content with a named sender who is not you, and pairing,
// enabling, allowlisting and reaching are four separate facts that must never
// be allowed to imply one another.
import { render, screen } from "@testing-library/svelte";
import { fireEvent, waitFor, within } from "@testing-library/dom";
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
        routing_mode: "record_only",
        target_session_id: null,
        target_session_title: null,
        owner_sender_id: null,
        approval_relay_enabled: false,
        supports_side_questions: true,
        supports_interrupts: true,
        supports_approvals: true,
        env_requirements: [],
        destination: { kind: "url", configured: false, host: null, allowlisted: null },
        last_test: null,
        route_scope: {
          conversation_scope: "endpoint",
          mention_required: false,
          thread_mapping: "none",
          starts_work: "nobody",
          bot_loop_protection: "rate_limit_only",
          reply_path: "none",
        },
        receipts: [],
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

  it("a test delivery names no address: it goes where the channel delivers", async () => {
    const fetchMock = stubFetch({
      "GET /api/channels": channelsView({
        profiles: [
          {
            ...channelsView().profiles[0],
            linked: true,
            enabled: false,
            pairing_id: "chp_1",
            display_label: "Webhooks",
            sender_count: 1,
            senders: ["ops"],
            owner_sender_id: "ops",
            destination: { kind: "url", configured: true, host: "hooks.example.com", allowlisted: true },
          },
        ],
      }),
      "POST /api/channels/deliver-test": { ok: true, delivered: true, connector_id: "channel.webhooks", channel_type: "webhooks", sent_bytes: 10, status: 200, signed: false },
    });
    render(MessagingView);
    await screen.findByText("Webhooks");
    const profiles = screen.getByTestId("channel-profiles");
    expect(within(profiles).getByText("hooks.example.com")).toBeInTheDocument();
    expect(
      within(profiles).getByText(/the capability gate, the decision mode, the egress allowlist and the audit event all apply/i),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Destination URL")).toBeNull();
    await fireEvent.click(within(profiles).getByRole("button", { name: "Send a test delivery" }));
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes("/api/channels/deliver-test"));
    expect(call).toBeDefined();
    const body = JSON.parse(String((call![1] as RequestInit).body));
    expect(body).toEqual({ connector_id: "channel.webhooks", text: "Raiker test delivery." });
  });

  // Found by the 2026-10-03 live round: a refused test is recorded on the
  // channel, and the page went on showing the state from before it.
  it("re-reads the channel after a refused test, so its recorded failure shows", async () => {
    const linked = {
      ...channelsView().profiles[0],
      linked: true,
      pairing_id: "chp_1",
      display_label: "Webhooks",
      sender_count: 1,
      senders: ["ops"],
      owner_sender_id: "ops",
      destination: { kind: "url", configured: true, host: "127.0.0.1", allowlisted: true },
    };
    const fetchMock = stubFetch({
      "GET /api/channels": channelsView({ profiles: [linked] }),
      "POST /api/channels/deliver-test": {
        __status: 403,
        detail: { reason_code: "disabled_by_capability_gate" },
      },
    });
    render(MessagingView);
    await fireEvent.click(await screen.findByRole("button", { name: "Send a test delivery" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/The external channel capability is turned off/),
    );
    const reads = fetchMock.mock.calls.filter(
      ([url, init]) => String(url).endsWith("/api/channels") && !(init as RequestInit | undefined)?.method,
    );
    expect(reads.length).toBeGreaterThanOrEqual(2);
  });

  // UX-MSG-03 — the order is the contract, and the first unfinished step
  // carries its own control.
  it("walks a paired channel through its setup in order", async () => {
    stubFetch({
      "GET /api/channels": channelsView({
        profiles: [
          {
            ...channelsView().profiles[0],
            linked: true,
            pairing_id: "chp_1",
            display_label: "Webhooks",
            sender_count: 1,
            senders: ["ops"],
            owner_sender_id: "ops",
          },
        ],
      }),
    });
    render(MessagingView);
    const steps = await screen.findByRole("list", { name: "Webhooks setup" });
    const items = within(steps).getAllByRole("listitem");
    expect(items.map((item) => item.querySelector("strong")?.textContent)).toEqual([
      "Connected",
      "Owner verified",
      "Allowed senders",
      "Routing",
      "Test delivery",
      "Turned on",
    ]);
    const current = items.find((item) => item.getAttribute("aria-current") === "step");
    expect(current).toHaveTextContent("Test delivery");
    expect(within(current!).getByRole("button", { name: "Set delivery address" })).toBeInTheDocument();
    // No address yet, so the plain test button cannot be pressed either.
    expect(screen.getByRole("button", { name: "Send a test delivery" })).toBeDisabled();
  });

  it("says what the route does and keeps each stage of a message separate", async () => {
    stubFetch({
      "GET /api/channels": channelsView({
        profiles: [
          {
            ...channelsView().profiles[0],
            channel_type: "telegram",
            display_name: "Telegram",
            linked: true,
            enabled: true,
            pairing_id: "chp_1",
            display_label: "Telegram",
            sender_count: 1,
            senders: ["4242"],
            owner_sender_id: "4242",
            routing_mode: "new_turn",
            destination: { kind: "owner_chat", configured: true, host: null, allowlisted: true },
            last_test: { at: "2026-10-03T10:00:00Z", ok: true, reason_code: null },
            route_scope: {
              conversation_scope: "direct_and_group",
              mention_required: false,
              thread_mapping: "new_conversation_each_message",
              starts_work: "owner_only",
              bot_loop_protection: "bot_messages_ignored",
              reply_path: "kept_in_raiker",
            },
            receipts: [
              {
                receipt_id: "chn_1",
                direction: "inbound",
                kind: "message",
                sender_role: "owner",
                conversation_scope: "group",
                routing_mode: "new_turn",
                session_id: "sess_1",
                received_at: "2026-10-03T10:00:00Z",
                accepted_at: "2026-10-03T10:00:00Z",
                queued_at: "2026-10-03T10:00:01Z",
                processed_at: "2026-10-03T10:00:05Z",
                reply_queued_at: null,
                delivered_at: null,
                failed_at: null,
                reason_code: null,
                created_at: "2026-10-03T10:00:00Z",
              },
            ],
          },
        ],
      }),
    });
    render(MessagingView);
    await screen.findByText(/Direct messages and groups alike/);
    expect(screen.getByText(/Messages from bots are ignored/)).toBeInTheDocument();
    expect(screen.getByText(/nothing is sent back over this channel/)).toBeInTheDocument();
    const activity = screen.getByRole("region", { name: "Telegram recent activity" });
    expect(within(activity).getByText("You in a group")).toBeInTheDocument();
    expect(within(activity).getByText("processed")).toBeInTheDocument();
    expect(within(activity).queryByText("delivered")).toBeNull();
    expect(within(activity).getByText(/Processed — no reply sent over the channel/)).toBeInTheDocument();
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
            ...channelsView().profiles[0],
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
