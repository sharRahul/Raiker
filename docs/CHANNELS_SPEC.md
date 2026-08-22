# Channels Specification

Channels allow external interfaces to send messages into Raiker sessions and receive replies, events, approvals, notifications, and task updates.

A channel is not just a UI. It is an untrusted input surface and must be treated as a security boundary. A channel can still be an equal-status primary interface when it is linked, enabled, trusted, and policy-permitted.

Implementation can be phased, but every channel type must already have a documented connector profile, setup flow, permission model, event model, action parity rule, and disabled-by-default behaviour before code is written.

---

## Channel Goals

Raiker channels must support:

1. equal-status primary clients when implemented and enabled;
2. secure session binding;
3. sender identity validation;
4. inbound message normalisation;
5. reply routing;
6. approval relay;
7. attachment handling;
8. background task notifications;
9. task controls where policy permits;
10. rate limits;
11. audit logging;
12. connector manifests;
13. enable, disable, link, and unlink flow;
14. per-channel capability policies;
15. action parity with other primary interfaces through the same gateway contracts.

---

## Channel Type Matrix

No channel is undefined future work. A later-phase channel is a fully specified connector profile that is disabled by default until the user or managed policy links it. Phase placement is implementation order only, not interface priority.

| Channel | Build phase | Default state | Connector availability | Notes |
|---|---:|---|---|---|
| CLI | Phase 1 | enabled | built-in client | Local terminal client through `raiker`. Equal primary interface. |
| Rich TUI | Phase 1-to-2 | enabled when installed | built-in client | Interactive terminal app with side questions. Equal primary interface. |
| REST API | Phase 2 | disabled | built-in connector profile | Local API server behind auth and policy. Equal primary programmatic interface. |
| Web UI | Phase 3 | disabled | built-in connector profile | Browser client using same gateway/event stream. Equal primary interface. |
| Desktop | Phase 3 | disabled | built-in connector profile | Native shell/webview/tray client. Equal primary interface. |
| Dashboard | Phase 3 | disabled | built-in connector profile | Operational overview and control surface. Equal primary interface. |
| IDE | Phase 3 | disabled | connector profile | Editor extension, gateway-only. Equal primary interface. |
| Apple Mobile | Phase 3 | disabled | connector profile | iOS/iPadOS app with prompts, approvals, tasks, checkpoints, models, channels, memory, graph, diagnostics. Equal primary interface. |
| Android Mobile | Phase 3 | disabled | connector profile | Android app with prompts, approvals, tasks, checkpoints, models, channels, memory, graph, diagnostics. Equal primary interface. |
| Webhooks | Phase 3 | disabled | connector profile | Inbound automation with signed messages. Equal primary automation interface when scoped. |
| Email | Phase 4 | disabled | connector profile | High injection risk; mailbox pairing required. Equal primary interface when trusted. |
| Slack | Phase 4 | disabled | connector profile | Workspace authorization and sender allowlist. Equal primary interface when trusted. |
| Teams | Phase 4 | disabled | connector profile | Tenant authorization and sender policy. Equal primary interface when trusted. |
| Discord | Phase 4 | disabled | connector profile | Server/channel allowlist and app policy. Equal primary interface when trusted. |
| Signal | Phase 4 | disabled | connector profile | Personal assistant mode with device pairing. Equal primary interface when trusted. |
| Voice | Phase 4 | disabled | connector profile | Speech input/output pipeline with confirmation gates. Equal primary interface when enabled. |
| Hotkeys | Phase 4 | disabled | connector profile | Local OS event source with scoped commands. Equal primary interface when enabled. |
| MCP Channel | Phase 4 | disabled | connector profile | MCP server can push messages/events into Raiker. Equal primary interface when trusted. |
| Browser Extension | Phase 4 | disabled | connector profile | Local browser context and selected-page handoff. Equal primary interface when paired. |
| Mobile Companion | Phase 3 | disabled | connector profile | Shared mobile capability model for Apple and Android apps. Equal primary interface. |

---

## Connector Profile Contract

Every channel connector must define this profile before implementation:

```json
{
  "schema_version": "1.0",
  "connector_id": "channel.slack",
  "channel_type": "slack",
  "display_name": "Slack",
  "build_phase": "phase_4",
  "default_state": "disabled",
  "transport": "provider_event_api",
  "auth_method": "provider_authorization",
  "supports_inbound_messages": true,
  "supports_replies": true,
  "supports_attachments": true,
  "supports_approvals": false,
  "supports_side_questions": true,
  "supports_interrupts": true,
  "supports_task_controls": true,
  "supports_checkpoints": true,
  "supports_model_controls": true,
  "supports_channel_management": true,
  "supports_memory": true,
  "supports_graph": true,
  "supports_diagnostics": true,
  "interface_status": "equal_primary_when_enabled",
  "requires_pairing": true,
  "requires_sender_allowlist": true,
  "requires_network": true,
  "setup_ui": "channel_link_wizard",
  "capability_policy_template": "channel.slack.default.json"
}
```

Required fields:

- `connector_id`;
- `channel_type`;
- `display_name`;
- `build_phase`;
- `default_state`;
- `transport`;
- `auth_method`;
- `supports_*` capabilities;
- `interface_status`;
- `requires_pairing`;
- `requires_sender_allowlist`;
- `setup_ui`;
- `capability_policy_template`.

---

## Connector Lifecycle

```text
connector_profile_available
  -> user opens Channels UI from any enabled primary interface
  -> user selects connector
  -> link wizard starts
  -> authorization and pairing completed
  -> sender/session policy configured
  -> test message sent or received
  -> connector linked
  -> connector enabled/disabled state stored
  -> channel_linked event emitted
```

Unlink lifecycle:

```text
unlink requested
  -> revoke local authorization reference
  -> stop background listeners
  -> disable approval relay
  -> keep audit history
  -> channel_unlinked event emitted
```

---

## Channel Link Wizard

Desktop, Web, Mobile, TUI, and any admin-capable interface must provide a link wizard for every connector profile, even if the connector implementation package is not installed yet.

If implementation is missing, the UI shows:

```text
Connector profile available.
Implementation package not installed.
Install or enable package: raiker-channel-slack
Required permissions: network, inbound messages, replies, attachments
Default approval relay: disabled
```

Wizard steps:

1. Select connector.
2. Show capabilities and risks.
3. Confirm required permissions.
4. Configure provider authorization or local pairing.
5. Configure sender allowlist.
6. Configure session/project binding.
7. Configure approval relay, default disabled.
8. Send or receive test message.
9. Save connector config.
10. Emit link event.

---

## What A Channel Message *Is* In A Turn

**Status: accepted 2026-08-22 (BUG-225 step 1). This section is the contract every
delivery path below has to satisfy, and no channel code may ship without it.**

A channel is the one place where **content Raiker did not ask for enters a turn**.
Every other input path already has an answer for that, and the answer is what
decides how the content is framed to the model:

| Input | What it is | How the turn frames it |
|---|---|---|
| A prompt | The owner speaking | Instructions. Authoritative. |
| A tool result | Data the runtime fetched on the model's behalf | Data the model is told to distrust. |
| A subagent digest | Another agent's report | Quoted as untrusted. |
| A skill | Instruction text the owner installed and activated | Instructions, at the owner's standing consent. |
| **A channel message** | **Content someone else sent** | **Untrusted content with a named sender who is not the owner.** |

Five rules follow, and each is enforceable rather than advisory:

1. **A channel message is never a prompt.** It is delivered into the turn inside
   an untrusted-content envelope carrying the connector id, the sender identity,
   and the sender's trust level — the same framing a tool result gets, never the
   framing the owner's own words get. A channel message that says "ignore your
   instructions" is a *quoted string in a data block*, not an instruction, and
   the envelope is what makes that structurally true rather than a matter of the
   model's judgement.
2. **The sender is not the owner, unless the sender *is* the owner and paired.**
   `sender.trust_level` is resolved from the pairing record, never from anything
   in the message. The default for an unrecognised sender is `untrusted`, and an
   unpaired channel resolves every sender that way — which is why
   `requires_pairing` is enforcement and not metadata.
3. **A channel message can never raise the turn's authority.** It cannot enable a
   capability, widen an approval mode, change a decision mode, install anything,
   or approve anything. The routing modes that *look* like authority
   (`approval_response`, `task_control`, `channel_admin`, `model_control`) are
   refused on any channel whose sender is not the paired owner, and
   `approval_response` is refused outright until the anti-phishing story in step
   4 below exists.
4. **Outbound is a capability; inbound is a boundary.** Delivering a result the
   owner asked for is governed by the ordinary capability gate, decision mode and
   audit event. Accepting a message is governed by pairing, the sender allowlist,
   and the rate limit — a different set of controls, because the risks are not
   the same one seen twice.
5. **Nothing is implicit.** A channel that is linked is not enabled; a channel
   that is enabled is not trusted; a sender that is allowlisted is not the owner.
   Each is a separate stored fact and each is shown separately on
   Extensions → Channels.

### Implementation order, and why

The order is the order in which the authority story can actually be written, and
each step is refused until the one before it is done:

| Step | What | State |
|---|---|---|
| 1 | **This section**, in the spec and the threat model | **Done.** Nothing below has a contract to satisfy without it. |
| 2 | **Outbound delivery** — connector profile, capability gate, egress allowlist, audit event | **Done.** `ExternalChannelExecutor` under `external_channel_runtime`. Deliveries carry `X-Raiker-Signature` (HMAC-SHA256 over the exact bytes, keyed by `RAIKER_CHANNEL_OUTBOUND_SECRET`) so `signed_http_callback` describes the wire and not just the profile. Unset means **unsigned, not refused** — the owner controls both ends of a webhook they configured — and the state is reported on the tab and in the delivery artifacts. |
| 3 | **Inbound, paired and allowlisted** | **Done.** The receiver enforces `requires_pairing` and `requires_sender_allowlist`, and marks every accepted message untrusted, quarantined and instructions-inert. |
| 4 | **An owner surface for all of it** | **Done (FIXED-265).** Steps 2 and 3 were built and had no way in: with no pairing the executors refuse and the receiver 404s, so the transport was unreachable and the tab reported that channels did not exist. |
| 5 | **Rate limits** — a per-sender inbound budget | **Done.** Fixed window per `(connector, sender)`, default 60/min, `RAIKER_CHANNEL_INBOUND_RATE` overrides; a refusal is a recorded `channel_message_rejected` event with `reason: rate_limited`. Allowlisting says *who*, this says *how often*. |
| 6 | **Routing modes** — `new_turn`, `side_question`, `interrupt`, … | **Open.** An inbound message is recorded and quarantined; none of the modes below is implemented, so a channel message never becomes work on its own. |
| 7 | **Permission relay** | **Open, and last.** A channel that can raise an approval is a channel that can be used to *ask for one*. The relay queue exists and is deliberately pending-only; nothing on a channel resolves an approval. |

Extensions → **Channels** states the contract above, offers pairing, enable and a
governed test delivery, and reports each of the three fail-closed gates — the
capability, `RAIKER_CHANNEL_EGRESS_ALLOWLIST` and `RAIKER_CHANNEL_INBOUND_SECRET`
— separately, because each has a different remedy.

**The Routing Modes table below is a target, not a description.** Only recording
and quarantining are implemented; a mode named there does not run today.

---

## Channel Message Envelope

```json
{
  "schema_version": "1.0",
  "channel_message_id": "chanmsg_01H...",
  "connector_id": "channel.apple_mobile",
  "channel_type": "apple_mobile",
  "channel_name": "raiker-ios",
  "session_id": "sess_01H...",
  "thread_id": null,
  "sender": {
    "id": "local_user",
    "display_name": "Rahul",
    "trust_level": "owner",
    "is_bot": false
  },
  "message": {
    "text": "How is the current task going?",
    "attachments": [],
    "mentions": [],
    "reply_to": null
  },
  "routing": {
    "mode": "side_question",
    "target_task_id": "task_01H...",
    "requires_interrupt": false
  },
  "received_at": "2026-06-17T12:00:00Z"
}
```

---

## Routing Modes

| Mode | Behaviour |
|---|---|
| `new_turn` | Starts a normal user turn. |
| `side_question` | Asks a question while current work continues. |
| `interrupt` | Requests active task pause/cancel/change. |
| `approval_response` | Responds to an approval request. |
| `task_note` | Adds context to an active background task. |
| `task_control` | Applies pause, cancel, steer, fork, rewind, or summarise action. |
| `model_control` | Launches, switches, or checks model profile. |
| `channel_admin` | Pairing/configuration/admin action. |
| `memory_action` | Searches, corrects, forgets, or proposes memory. |
| `graph_query` | Runs graph/codemap query through policy. |
| `diagnostic_action` | Runs diagnostics. |
| `notification_ack` | Acknowledges notification. |

---

## Side Questions Without Stopping Work

Raiker must support side questions in Rich TUI and all linked channels whose connector profile has `supports_side_questions=true`.

Rules:

1. A side question is attached to a running `task_id` or `turn_id`.
2. The active task continues unless the user explicitly sends an interrupt.
3. The runtime creates a lightweight `SideQuestionContext`.
4. The side answer can use current task state, event log, and safe read-only context.
5. The side answer must not mutate the active task plan unless the user escalates to interrupt/steer.
6. The side question and answer are event-logged.
7. If the side question reveals important new constraints, Raiker asks whether to apply them to the active task.

Events:

- `side_question_received`
- `side_question_context_created`
- `side_question_answered`
- `side_question_escalated_to_interrupt`
- `side_question_applied_to_task`

---

## Built-In Connector Profiles

Each connector profile must exist in code or configuration before the connector implementation is wired.

| Connector ID | Phase | Default | Side questions | Approvals | Notes |
|---|---:|---|---:|---:|---|
| `channel.cli` | 1 | enabled | interactive only | yes | Local terminal client. Equal primary. |
| `channel.tui` | 1-to-2 | enabled when installed | yes | yes | Rich interactive terminal. Equal primary. |
| `channel.rest` | 2 | disabled | yes | disabled by default | Local API server. Equal primary when enabled. |
| `channel.web_ui` | 3 | disabled | yes | authenticated only | Browser client. Equal primary. |
| `channel.desktop` | 3 | disabled | yes | yes | Desktop app. Equal primary. |
| `channel.dashboard` | 3 | disabled | yes | yes | Dashboard client/surface. Equal primary. |
| `channel.ide` | 3 | disabled | yes | yes | Editor extension. Equal primary. |
| `channel.apple_mobile` | 3 | disabled | yes | yes | iOS/iPadOS app. Equal primary. |
| `channel.android_mobile` | 3 | disabled | yes | yes | Android app. Equal primary. |
| `channel.webhooks` | 3 | disabled | no by default | no by default | Signed inbound automation. Equal primary when scoped. |
| `channel.email` | 4 | disabled | trusted senders only | disabled by default | High injection risk. Equal primary when trusted. |
| `channel.slack` | 4 | disabled | yes | disabled by default | Workspace connector. Equal primary when trusted. |
| `channel.teams` | 4 | disabled | yes | disabled by default | Tenant connector. Equal primary when trusted. |
| `channel.discord` | 4 | disabled | trusted channels only | disabled by default | Community/server connector. Equal primary when trusted. |
| `channel.signal` | 4 | disabled | yes | disabled by default | Personal assistant connector. Equal primary when trusted. |
| `channel.voice` | 4 | disabled | yes | visual handoff for high risk | Local-first STT/TTS. Equal primary when enabled. |
| `channel.hotkeys` | 4 | disabled | quick status only | no | Local OS shortcuts. Equal primary when enabled. |
| `channel.mcp` | 4 | disabled | trusted server only | disabled by default | MCP inbound channel. Equal primary when trusted. |
| `channel.browser_extension` | 4 | disabled | yes | disabled by default | Selected browser context only. Equal primary when paired. |
| `channel.mobile` | 3 | disabled | yes | yes | Shared mobile companion capability for Apple/Android. Equal primary. |

---

## Channel Pairing And Trust

External channels must be paired before use.

Pairing requirements:

- generate one-time pairing code;
- bind channel identity to user/project/session scope;
- store channel trust record;
- allow revocation;
- log pairing event;
- require re-approval for permission expansion.

Trust levels:

- `owner`
- `trusted_user`
- `project_member`
- `external_user`
- `bot`
- `unknown`
- `blocked`

Unknown senders must not start tool-using tasks.

---

## Channel Permissions

Channel permissions define what a channel can do:

```json
{
  "schema_version": "1.0",
  "connector_id": "channel.slack",
  "channel_name": "slack-personal",
  "allowed_senders": ["U123"],
  "allowed_sessions": ["sess_01H..."],
  "capabilities": {
    "send_prompt": true,
    "ask_side_question": true,
    "approve_tools": false,
    "attach_files": true,
    "receive_events": true,
    "interrupt_tasks": true,
    "control_tasks": true,
    "manage_checkpoints": true,
    "launch_models": true,
    "manage_channels": true,
    "inspect_memory": true,
    "query_graph": true,
    "run_diagnostics": true
  },
  "rate_limits": {
    "messages_per_minute": 20,
    "attachments_per_hour": 10
  }
}
```

---

## Attachments

Attachments are untrusted.

Required handling:

- file type detection;
- size limits;
- malware scanning hook point;
- content extraction policy;
- prompt-injection warning;
- provenance record;
- retention policy;
- redaction before memory storage.

---

## Approval Relay

Some channels may relay approvals.

Approval relay is disabled by default. To enable it:

- sender must be trusted;
- channel must be paired;
- approval must show exact action ID and arguments;
- approval response must be authenticated by the linked channel;
- action must not have changed since approval request;
- event log must record channel approval source;
- stale mobile or channel state must refresh before approval can be accepted.

---

## Channel Security Requirements

Channels must defend against:

- prompt injection;
- spoofed senders;
- replayed approvals;
- stale approval state;
- malicious attachments;
- connector account compromise;
- over-permissive approval relay;
- data exfiltration through replies;
- channel-to-channel leakage;
- rate-limit abuse;
- accidental session cross-talk.

---

## Channel Events

Required events:

- `connector_profile_available`
- `channel_link_started`
- `channel_link_failed`
- `channel_linked`
- `channel_unlink_requested`
- `channel_unlinked`
- `channel_registered`
- `channel_pairing_started`
- `channel_paired`
- `channel_revoked`
- `channel_message_received`
- `channel_message_rejected`
- `channel_attachment_received`
- `channel_attachment_rejected`
- `channel_reply_sent`
- `channel_approval_received`
- `channel_rate_limited`
- `channel_task_control_received`
- `channel_model_control_received`
- `channel_checkpoint_action_received`
- `channel_memory_action_received`
- `channel_graph_query_received`
- `channel_diagnostic_action_received`
- `mobile_push_sent`
- `mobile_approval_received`
- `mobile_stale_state_rejected`
- `side_question_received`
- `side_question_answered`

---

## Channel Testing Requirements

Tests must prove:

- every channel type has a connector profile;
- Apple and Android mobile app connector profiles exist;
- disabled connector cannot receive messages;
- connector link wizard validates required fields;
- unpaired channel cannot start task;
- unknown sender rejected;
- side question does not stop background task;
- approval relay blocked by default;
- replayed approval rejected;
- stale mobile approval rejected;
- attachment over size limit rejected;
- channel replies only to bound session/thread;
- rate limit works;
- unlink revokes local capability but preserves audit history;
- enabled interfaces use equal gateway contracts and do not bypass policy.
