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
  event all apply. It is not a shortcut that proves nothing. It asks for no
  address: it goes where the channel delivers (below), and it runs on a paired
  channel that is still off, because you test before you turn it on.
- **Delivery address** (the webhook channel) is where every delivery on it goes,
  tests included — set once on the channel, never typed into a test, and never
  named by anything else. Use `https://`, or `http://` only to this machine or
  your own network, with no username or password in it; the page shows its host
  and whether that host is on the egress allowlist. Changing it forgets the last
  test. Telegram has no address to set: it delivers to your own chat.
- **Senders** edits the allowlist after pairing.
- **Pause** (on a channel that is on) contains it without losing anything: a
  message from an allowed sender is still received and recorded — its receipt
  reads *Kept while paused — nothing started* — but it starts no work, and
  nothing is delivered to or relayed through the channel, tests included, until
  **Resume**. **Turn off** refuses messages instead.
- Every change on this page applies only to the channel as the page shows it.
  If another tab changed it since this page loaded — removed a sender, say —
  nothing is changed, the page says so and shows the current settings, so a
  stale page cannot put an old allowlist back.
- **Unpair** deletes the link. Both the outbound executor and the inbound
  receiver read that record, so unpairing is what actually stops the channel.
- **Routing** chooses `record_only`, a normal owner turn, a tool-free side
  question, or an interrupt/steer bound to one conversation — chosen by its
  title from your recent chats. **You on this channel** names which allowed
  sender is you. The pairing stores this choice; message content cannot choose
  it.

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

## Setting a channel up, in order

**Channels** leads the page. A channel that is not paired says how to pair it.
A paired channel shows its setup as six steps, each one a fact Raiker already
holds, and the first unfinished one is marked **Next** and carries its own
button:

1. **Connected** — paired with Raiker.
2. **Owner verified** — which allowed sender is you. Only you can start work or
   answer an approval from the channel.
3. **Allowed senders** — anyone not listed is refused and recorded; a side
   question or interrupt route also needs its conversation.
4. **Routing** — *Record only* until you change it.
5. **Test delivery** — set where it delivers, then send a test. A refusal says
   why (*the channel capability is off in Permissions*, *the host is not on the
   channel egress allowlist*).
6. **Turned on** — nothing is accepted or delivered until it is.

**What this route does** states the stored route as what the receiver does with
it: whether direct messages and groups are both heard (Telegram) or there is one
caller (the webhook), that no @mention is needed, whether messages share one
conversation or each starts a new one, who may start work, what stops a bot
loop — Telegram updates written by a bot are ignored; on the webhook, which has
no such flag, a message that repeats one of Raiker's own recent replies, or the
same message a third time in ten minutes, is refused before it reaches a model
and its receipt says so — and where an answer goes.
A Telegram answer stays in Raiker; nothing is sent back over the channel yet.

**Recent activity** lists each message and test with its stages as separate
facts — *received, accepted, queued, processed, reply queued, delivered,
failed* — so a finished turn is never read as a delivered reply. It names the
sender by role (you, an allowed sender, a sender who is not allowed), never by
id, holds no message text, and links to the conversation a routed message
became. The last 200 per channel are kept, and unpairing keeps them.

## What a channel needs from your environment

Each channel declares the environment variables it needs, and the page shows
them on the channel itself: the variable's name, what it is for, where to get
it, and **whether it is set** — never what it is set to. Raiker takes the name
of a variable and reads it at the moment it is used; that holds on this surface
too, so a card can tell you a token is missing without ever having seen one.

**Delivery environment**, at the foot of the page, is the host process's own
configuration read back: the outbound capability, the egress allowlist, HMAC
signing, the inbound secret and the per-sender rate limit. All five are set
outside the app and all five are real — they are below the channels because
connecting a messaging account should not begin with a briefing on them.

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


## Adding another platform

A channel type is one entry in `raiker/channels/adapters.py`, and it answers two
questions: what URL and body does a message become, and what did an inbound
payload actually say. Everything that decides whether a message is *allowed* —
the capability gate, the egress allowlist, the pairing, the sender allowlist, the
per-sender budget, the redaction, the audit event, your stored routing choice —
lives outside the adapter and applies identically to every one of them. An
adapter cannot widen any of it, which is what makes adding one small.

An adapter stays that small on purpose. Streaming message edits, typing
indicators, media caches and inline keyboards belong to a chat client; a channel
is a governed relay carrying untrusted content, and each of those would need its
own governance answer before it could ship.
