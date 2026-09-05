# Messaging

**Messaging** is where Raiker meets you somewhere other than this browser.

It used to be a tab inside Extensions, next to connectors, MCP servers, skills,
hooks and plugins. Those are all things the agent *uses*. A channel is the
opposite direction: a place a person writes to Raiker from. That is a different
kind of thing, and it is the one place where content Raiker did not ask for
enters a turn — so it has its own destination and its own contract.

A channel is the one place where content Raiker did not ask for enters a turn.
That content is defined: **untrusted content with a named sender who is not you.**
Never a prompt. Never able to enable a capability, widen an approval mode, or
approve anything. Trust comes from the pairing record, never from anything inside
the message.

The page lists every connector profile and lets you **pair** one. Pairing does not
switch it on and does not trust anyone — linked, enabled and trusted are three
separate facts, and the page shows them separately:

- **Pair** stores the link, switched off, with whatever sender allowlist you gave
  it. A profile that accepts inbound messages cannot be paired without one.
- **Turn on** is a second decision.
- **Send a test delivery** runs the *same governed path* a real delivery takes —
  the capability gate, the decision mode, the egress allowlist and the audit
  event all apply. It is not a shortcut that proves nothing.
- **Unpair** deletes the link. Both the outbound executor and the inbound
  receiver read that record, so unpairing is what actually stops the channel.
- **Routing** chooses `record_only`, a normal owner turn, a tool-free side
  question, or an interrupt/steer bound to one conversation. The pairing stores
  this choice; message content cannot choose it.

Four things are fail-closed or off by default, and each has its own remedy, so
the page reports them one by one rather than as a single "ready":

| Gate | What it is | Where you change it |
|---|---|---|
| Capability | `external_channel_runtime` | Permissions |
| Egress | `RAIKER_CHANNEL_EGRESS_ALLOWLIST` — empty means deny | Your environment |
| Signing | `RAIKER_CHANNEL_OUTBOUND_SECRET` — unset means unsigned, not refused | Your environment |
| Inbound secret | `RAIKER_CHANNEL_INBOUND_SECRET` — unset means refuse | Your environment |

A fifth row states the **inbound budget**: 60 messages per sender per minute by
default, `RAIKER_CHANNEL_INBOUND_RATE` to change it. Allowlisting says *who* may
speak; the budget says how often, and they are different questions — a sender
that goes over is refused and the refusal is recorded, so a channel that goes
quiet is answerable from Observability rather than a mystery.

`record_only` is the default and keeps the message quarantined. A routed message
is still structurally untrusted data: it never occupies the owner's instruction
slot and cannot raise authority. New turns and interrupts require the exact
owner identity stored on the pairing; side questions have no tool budget.
Accepted, routed, and rejected messages appear in Observability → Activity.

Approval response is separately off. When enabled it accepts only the bound
owner and one exact pending relay/action pair, once. Critical and connector-write
approvals remain local-only.
Full contract: [`docs/architecture/CHANNELS_SPEC.md`](../architecture/CHANNELS_SPEC.md).

## Telegram

Telegram is the first adapter for a transport that is not Raiker's own shape,
and being a name you recognise buys it nothing. It lands on the same path as the
reference webhook — pairing, sender allowlist, per-sender budget, redacted
preview, audit event, stored routing decision — and refuses in the same places.

Two pieces of setup, both in your environment, because Raiker takes the *name*
of a variable it will read and never the value:

| Variable | What it is |
|---|---|
| `RAIKER_TELEGRAM_BOT_TOKEN` | Your bot's token, from BotFather. Read at delivery, never stored in the workspace, never logged, never returned by the API. |
| `RAIKER_CHANNEL_INBOUND_SECRET` | The secret you give Telegram at `setWebhook`. Telegram echoes it back in `X-Telegram-Bot-Api-Secret-Token` on every update, and an update without it is refused. |

You must also allowlist the host. `RAIKER_CHANNEL_EGRESS_ALLOWLIST` has to
contain `api.telegram.org` or nothing leaves the machine — **a bot token is not
authorisation to reach the network**, and the two decisions are deliberately
separate.

Point Telegram's webhook at
`https://<your-host>/api/channels/channel.telegram/telegram`. Raiker translates
the update at the edge and everything after that is the ordinary channel path.
An update that is not a message — a reaction, a poll answer, someone joining —
is acknowledged and dropped rather than refused, because Telegram retries
anything it does not get a `2xx` for and retrying a join forever helps nobody.

**The sender allowlist is Telegram user ids**, as strings: the numeric `id` on
`message.from`, not a @username. A username can be changed by its owner; an id
cannot.

Outbound messages carry no Raiker signature, unlike the webhook transport. That
is not an omission — the receiver is Telegram, which authenticates the token in
the request URL rather than an HMAC over the body. It is also why the token
never appears in a reason code: the token sits in the URL *path*, so `post_url`
reports only scheme and host when a URL is rejected, and the delivery record
carries byte counts and a status rather than the target.
