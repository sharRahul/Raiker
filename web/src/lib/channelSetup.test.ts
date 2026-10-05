// UX-MSG-03, -05 and -06 — the setup order, the route stated as what the
// receiver does, and a message's stages as separate facts.
import { describe, expect, it } from "vitest";
import type { ChannelProfile } from "./apiTypes";
import {
  channelSteps,
  receiptConversationHref,
  receiptOutcome,
  receiptStages,
  receiptTitle,
  routeScopeFacts,
  testReason,
} from "./channelSetup";

function profile(overrides: Partial<ChannelProfile> = {}): ChannelProfile {
  return {
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
    pairing_id: "chn_1",
    display_label: "Webhooks",
    sender_count: 1,
    senders: ["ops"],
    routing_mode: "record_only",
    target_session_id: null,
    target_session_title: null,
    owner_sender_id: null,
    approval_relay_enabled: false,
    supports_side_questions: true,
    supports_interrupts: true,
    supports_approvals: true,
    env_requirements: [],
    destination: { kind: "url", configured: true, host: "hooks.example.com", allowlisted: true },
    last_test: null,
    route_scope: {
      conversation_scope: "endpoint",
      mention_required: false,
      thread_mapping: "none",
      starts_work: "nobody",
      bot_loop_protection: "echo_and_repeat_refused",
      reply_path: "none",
    },
    receipts: [],
    ...overrides,
  };
}

const states = (p: ChannelProfile) =>
  Object.fromEntries(channelSteps(p).map((step) => [step.id, step.state]));

describe("channelSteps", () => {
  it("marks exactly the first unfinished step as next", () => {
    expect(states(profile())).toEqual({
      connected: "done",
      owner: "current",
      senders: "done",
      routing: "done",
      test: "todo",
      enabled: "todo",
    });
  });

  it("puts the test before turning on, and a failed test says why", () => {
    const p = profile({
      owner_sender_id: "ops",
      last_test: { at: "2026-10-03T10:00:00Z", ok: false, reason_code: "egress_denied:host" },
    });
    expect(states(p).test).toBe("current");
    expect(states(p).enabled).toBe("todo");
    expect(channelSteps(p).find((step) => step.id === "test")?.detail).toMatch(
      /not on the channel egress allowlist/,
    );
  });

  it("asks for the conversation a side question goes to", () => {
    const p = profile({ owner_sender_id: "ops", routing_mode: "side_question" });
    expect(states(p).senders).toBe("current");
  });

  it("calls nothing to test on a transport this build cannot deliver over", () => {
    const p = profile({
      owner_sender_id: "ops",
      destination: { kind: "none", configured: false, host: null, allowlisted: null },
    });
    expect(states(p).test).toBe("not_needed");
    expect(states(p).enabled).toBe("current");
  });

  it("is all done for a tested channel that is on", () => {
    const p = profile({
      owner_sender_id: "ops",
      enabled: true,
      last_test: { at: "2026-10-03T10:00:00Z", ok: true, reason_code: null },
    });
    expect(Object.values(states(p)).every((state) => state === "done")).toBe(true);
  });
});

describe("routeScopeFacts", () => {
  it("states every fact the review asks for", () => {
    const labels = routeScopeFacts(profile().route_scope).map((fact) => fact.label);
    expect(labels).toEqual(["Where", "Mention", "Threads", "Who starts work", "Bots", "Replies"]);
  });
});

describe("receipts", () => {
  const base = {
    receipt_id: "r",
    direction: "inbound" as const,
    kind: "message" as const,
    sender_role: "allowed",
    conversation_scope: "direct",
    routing_mode: "side_question",
    session_id: null,
    received_at: "t",
    accepted_at: "t",
    queued_at: null,
    processed_at: null,
    reply_queued_at: null,
    delivered_at: null,
    failed_at: null,
    reason_code: null,
    created_at: "t",
  };

  it("never reads a processed turn as a delivered reply", () => {
    const receipt = { ...base, queued_at: "t", processed_at: "t" };
    expect(receiptStages(receipt)).toEqual(["received", "accepted", "queued", "processed"]);
    expect(receiptOutcome(receipt)).toMatch(/no reply sent/);
  });

  it("names the sender by role and a refusal by its reason", () => {
    const refused = {
      ...base,
      sender_role: "not_allowed",
      accepted_at: null,
      failed_at: "t",
      reason_code: "sender_not_allowlisted",
    };
    expect(receiptTitle(refused)).toBe("A sender who is not allowed directly");
    expect(receiptOutcome(refused)).toBe("Failed: the sender is not on the allowlist");
  });

  it("says a routed turn that failed did not complete, and links to it", () => {
    const failed = { ...base, queued_at: "t", failed_at: "t", reason_code: "turn_failed", session_id: "sess_9" };
    expect(receiptOutcome(failed)).toBe(
      "Failed: the turn did not complete — its conversation says why",
    );
    expect(receiptConversationHref(failed)).toBe("#/new-chat?session=sess_9");
    expect(receiptConversationHref(base)).toBeNull();
  });

  it("words the codes a test comes back with", () => {
    expect(testReason("disabled_by_capability_gate")).toMatch(/Permissions/);
    expect(testReason("http_error:502")).toBe("the destination answered 502");
  });
});

describe("the loop guard's refusals", () => {
  it("are said in the owner's words", async () => {
    const { testReason } = await import("./channelSetup");
    expect(testReason("loop_echo")).toMatch(/one of Raiker's own replies/);
    expect(testReason("loop_repeated")).toMatch(/third time in ten minutes/);
  });
});
