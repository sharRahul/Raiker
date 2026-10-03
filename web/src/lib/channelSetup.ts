/**
 * What a channel needs before it can be trusted with work, and what it does
 * once it can — release-readiness review §3.10, DEC-14.
 *
 * Messaging offered **Turn on**, **Send a test delivery**, **Routing** and
 * **Unpair** as four equal buttons and one line naming the next of them. The
 * order is the contract (UX-MSG-03): *connected → owner verified → allowed
 * senders → routing → test → on*, and each step is a separate fact the server
 * already reports. This module reads those facts; it decides nothing the server
 * did not say.
 *
 * Kept out of the view so the wording is one table with tests, the same way
 * `permissionLanguage.ts` is for Permissions.
 */
import type { ChannelProfile } from "./apiTypes";

export type ChannelStepId = "connected" | "owner" | "senders" | "routing" | "test" | "enabled";
export type ChannelStepState = "done" | "current" | "todo" | "not_needed";

export interface ChannelStep {
  id: ChannelStepId;
  label: string;
  state: ChannelStepState;
  detail: string;
}

type Receipt = ChannelProfile["receipts"][number];
type RouteScope = ChannelProfile["route_scope"];

export const ROUTE_LABELS: Record<ChannelProfile["routing_mode"], string> = {
  record_only: "Record only",
  new_turn: "New turn",
  side_question: "Side question",
  interrupt: "Interrupt or steer",
};

/** The reason codes a test or a message comes back with, in the owner's words. */
export function testReason(code: string | null | undefined): string {
  const value = code ?? "";
  if (value === "disabled_by_capability_gate")
    return "the channel capability is off in Permissions";
  if (value === "channel_destination_missing") return "no delivery URL is set";
  if (value === "telegram_bot_token_missing") return "RAIKER_TELEGRAM_BOT_TOKEN is not set";
  if (value === "telegram_chat_id_missing") return "no owner sender is chosen to deliver to";
  if (value.startsWith("egress_denied")) return "the host is not on the channel egress allowlist";
  if (value.startsWith("http_error")) return `the destination answered ${value.split(":")[1] ?? "an error"}`;
  if (value.startsWith("fetch_failed")) return "the destination could not be reached";
  if (value === "sender_not_allowlisted") return "the sender is not on the allowlist";
  if (value === "rate_limited") return "the sender went over the rate limit";
  if (value === "channel_owner_sender_required") return "only you can start work on this route";
  if (value === "channel_target_session_required") return "the route has no conversation";
  if (value.startsWith("turn_"))
    return `the turn ${value === "turn_stopped" ? "was stopped" : "did not complete"} — its conversation says why`;
  if (value.startsWith("channel_transport_unsupported"))
    return "this build has no way to deliver over this channel";
  return value || "it failed";
}

/**
 * The six steps, each with its state. Exactly one step is `current` until the
 * channel is on — the first one not done — and the rest are `todo`, so the page
 * can open the right control and say nothing about the others.
 */
export function channelSteps(profile: ChannelProfile): ChannelStep[] {
  const needsSenders = profile.requires_sender_allowlist;
  const routedToConversation =
    profile.routing_mode === "side_question" || profile.routing_mode === "interrupt";
  const destination = profile.destination;
  const raw: Omit<ChannelStep, "state">[] = [];
  const done: Record<ChannelStepId, boolean | null> = {
    connected: profile.linked,
    owner: needsSenders ? Boolean(profile.owner_sender_id) : null,
    senders: needsSenders
      ? profile.sender_count > 0 && (!routedToConversation || Boolean(profile.target_session_id))
      : null,
    routing: profile.linked,
    test: destination.kind === "none" ? null : profile.last_test?.ok === true,
    enabled: profile.enabled,
  };
  raw.push({
    id: "connected",
    label: "Connected",
    detail: profile.linked
      ? "Paired with Raiker."
      : needsSenders
        ? "Pair it, naming the senders it may accept messages from."
        : "Pair it to connect the account.",
  });
  raw.push({
    id: "owner",
    label: "Owner verified",
    detail: profile.owner_sender_id
      ? `You are ${profile.owner_sender_id} on this channel.`
      : "Choose which allowed sender is you. Only you can start work or answer approvals from here.",
  });
  raw.push({
    id: "senders",
    label: "Allowed senders",
    detail:
      profile.sender_count === 0
        ? "Nobody is allowed yet, so every inbound message is refused."
        : routedToConversation && !profile.target_session_id
          ? "This route needs the conversation its messages go to."
          : `${profile.sender_count} sender${profile.sender_count === 1 ? "" : "s"} may write to Raiker here.` +
            (profile.target_session_title ? ` Messages go to “${profile.target_session_title}”.` : ""),
  });
  raw.push({
    id: "routing",
    label: "Routing",
    detail:
      profile.routing_mode === "record_only"
        ? "Record only — messages are kept and start nothing. Change it when you want them to."
        : `${ROUTE_LABELS[profile.routing_mode]}.`,
  });
  raw.push({
    id: "test",
    label: "Test delivery",
    detail:
      destination.kind === "none"
        ? "This build cannot deliver over this channel, so there is nothing to test."
        : destination.kind === "url" && !destination.configured
          ? "Set where it delivers, then send a test."
          : profile.last_test === null || profile.last_test === undefined
            ? "Send a test through the same path a real delivery takes."
            : profile.last_test.ok
              ? "The last test was delivered."
              : `The last test was not delivered: ${testReason(profile.last_test.reason_code)}.`,
  });
  raw.push({
    id: "enabled",
    label: "Turned on",
    detail: profile.enabled ? "On." : "Off — nothing is accepted or delivered until you turn it on.",
  });

  let currentTaken = false;
  return raw.map((step) => {
    const value = done[step.id];
    if (value === null) return { ...step, state: "not_needed" as const };
    if (value) return { ...step, state: "done" as const };
    if (!currentTaken) {
      currentTaken = true;
      return { ...step, state: "current" as const };
    }
    return { ...step, state: "todo" as const };
  });
}

/** UX-MSG-05 — the stored route as what the receiver actually does. */
export function routeScopeFacts(scope: RouteScope): { label: string; value: string }[] {
  return [
    {
      label: "Where",
      value:
        scope.conversation_scope === "direct_and_group"
          ? "Direct messages and groups alike — an allowed sender is heard in either."
          : "One caller posting to Raiker; there are no chats or groups.",
    },
    {
      label: "Mention",
      value: scope.mention_required
        ? "A message must mention Raiker."
        : "Not needed — Raiker does not look for an @mention.",
    },
    {
      label: "Threads",
      value:
        scope.thread_mapping === "none"
          ? "None — messages are recorded, not put in a conversation."
          : scope.thread_mapping === "one_conversation"
            ? "Every message goes to the one conversation you chose."
            : "Each message starts a new conversation.",
    },
    {
      label: "Who starts work",
      value:
        scope.starts_work === "nobody"
          ? "Nobody — this route starts nothing."
          : scope.starts_work === "owner_only"
            ? "Only you. Other allowed senders are recorded."
            : "Any allowed sender may ask a side question; it has no tools.",
    },
    {
      label: "Bots",
      value:
        scope.bot_loop_protection === "bot_messages_ignored"
          ? "Messages from bots are ignored, so two bots cannot answer each other."
          : "Only the per-sender rate limit stops an automated caller.",
    },
    {
      label: "Replies",
      value:
        scope.reply_path === "returned_to_caller"
          ? "Returned in the response to the caller's request."
          : scope.reply_path === "kept_in_raiker"
            ? "Kept in Raiker — nothing is sent back over this channel."
            : "None.",
    },
  ];
}

export type ReceiptStage =
  | "received"
  | "accepted"
  | "queued"
  | "processed"
  | "reply queued"
  | "delivered"
  | "failed";

/**
 * UX-MSG-06 — the stages a receipt has reached, in order, each a separate fact.
 * A turn that finished and a reply that arrived are two of them.
 */
export function receiptStages(receipt: Receipt): ReceiptStage[] {
  const stages: [ReceiptStage, string | null][] = [
    ["received", receipt.received_at],
    ["accepted", receipt.accepted_at],
    ["queued", receipt.queued_at],
    ["processed", receipt.processed_at],
    ["reply queued", receipt.reply_queued_at],
    ["delivered", receipt.delivered_at],
    ["failed", receipt.failed_at],
  ];
  return stages.filter(([, at]) => Boolean(at)).map(([stage]) => stage);
}

/** One line naming what a receipt is, without a sender id (it has none). */
export function receiptTitle(receipt: Receipt): string {
  if (receipt.kind === "test_delivery") return "Test delivery";
  const who =
    receipt.sender_role === "owner"
      ? "You"
      : receipt.sender_role === "allowed"
        ? "An allowed sender"
        : "A sender who is not allowed";
  const where =
    receipt.conversation_scope === "group"
      ? " in a group"
      : receipt.conversation_scope === "direct"
        ? " directly"
        : "";
  return `${who}${where}`;
}

/** The conversation a routed message became, to open from its receipt. */
export function receiptConversationHref(receipt: Receipt): string | null {
  return receipt.session_id ? `#/new-chat?session=${encodeURIComponent(receipt.session_id)}` : null;
}

/** Where a receipt stopped, when it stopped short. */
export function receiptOutcome(receipt: Receipt): string {
  if (receipt.failed_at) return `Failed: ${testReason(receipt.reason_code)}`;
  if (receipt.kind === "test_delivery") return receipt.delivered_at ? "Delivered" : "Sent";
  if (receipt.delivered_at) return "Answered and returned to the caller";
  if (receipt.processed_at) return "Processed — no reply sent over the channel";
  if (receipt.queued_at) return "Waiting — queued for work";
  return "Recorded — the route starts nothing";
}
