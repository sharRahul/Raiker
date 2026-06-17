# Channels Specification

Channels allow external interfaces to send messages into Raiker sessions and receive replies, events, approvals, notifications, and task updates.

A channel is not just a UI. It is an untrusted input surface and must be treated as a security boundary.

---

## Channel Goals

Raiker channels must support:

1. equal-status clients;
2. secure session binding;
3. sender identity validation;
4. inbound message normalisation;
5. reply routing;
6. approval relay;
7. attachment handling;
8. background task notifications;
9. rate limits;
10. audit logging.

---

## Channel Types

| Channel | Phase | Notes |
|---|---:|---|
| CLI | Phase 1 | First client |
| Rich TUI | Phase 2 | Interactive terminal app |
| REST API | Phase 2 | Local API server |
| Web UI | Phase 3 | Browser client |
| Desktop | Phase 3 | Native shell or webview |
| IDE | Phase 3 | Editor extension |
| Webhooks | Phase 3 | Inbound automation |
| Email | Future | High injection risk |
| Slack | Future | Requires workspace auth and sender policy |
| Teams | Future | Requires tenant policy |
| Discord | Future | Community/server risk controls |
| Signal | Future | Personal assistant mode |
| Voice | Future | Speech input/output pipeline |
| Hotkeys | Future | Local OS event source |

---

## Channel Message Envelope

```json
{
  "schema_version": "1.0",
  "channel_message_id": "chanmsg_01H...",
  "channel_type": "tui",
  "channel_name": "raiker-tui",
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
| `notification_ack` | Acknowledges notification. |
| `channel_admin` | Pairing/configuration/admin action. |

---

## Side Questions Without Stopping Work

Raiker must support side questions in rich TUI and channels.

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
  "channel_name": "slack-personal",
  "allowed_senders": ["U123"],
  "allowed_sessions": ["sess_01H..."],
  "capabilities": {
    "send_prompt": true,
    "ask_side_question": true,
    "approve_tools": false,
    "attach_files": true,
    "receive_events": true,
    "interrupt_tasks": true
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
- approval response must be signed or authenticated;
- action must not have changed since approval request;
- event log must record channel approval source.

---

## Channel Security Requirements

Channels must defend against:

- prompt injection;
- spoofed senders;
- replayed approvals;
- malicious attachments;
- channel bot compromise;
- over-permissive approval relay;
- data exfiltration through replies;
- channel-to-channel leakage;
- rate-limit abuse;
- accidental session cross-talk.

---

## Channel Events

Required events:

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
- `side_question_received`
- `side_question_answered`

---

## Channel Testing Requirements

Tests must prove:

- unpaired channel cannot start task;
- unknown sender rejected;
- side question does not stop background task;
- approval relay blocked by default;
- replayed approval rejected;
- attachment over size limit rejected;
- channel replies only to bound session/thread;
- rate limit works.
