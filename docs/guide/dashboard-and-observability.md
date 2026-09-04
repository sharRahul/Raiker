# Dashboard and observability

The dashboard groups everyday work separately from permissions and evidence.
Its layout becomes a bottom bar and drawer on phones, a menu and drawer on
tablets, and a full sidebar on wider screens.

## Main destinations

| Group | Destination | What it is for |
|---|---|---|
| Home | **Workbench** | Live view of running work, agents, schedules, and decisions that need you |
| Work | **Chat** | Conversations, attachments, sources, memory, and approvals |
| Work | **Build** | Repository-aware planning, edits, commands, commits, and pushes |
| Work | **Threads** | Everything you have going — chats and routines — and a full-text search across it |
| Work | **Tasks** and **Projects** | One-off, scheduled, repeating, and organized work |
| Knowledge | **Memory** | Review durable facts Raiker may recall, and approve additions or removals |
| Knowledge | **Knowledge Map** | Explore indexed sources and the citations connecting them |
| Control | **Approvals** | Inspect proposed actions and decide whether they may proceed |
| Control | **Permissions** | Capability gates and per-capability decision modes |
| Control | **Models** | Providers, model readiness, routing, fallback, and pricing |
| Control | **Extensions** | Connectors, MCP servers, skills, hooks, plugins, and channels |
| Observe | **Observability** | Readiness, sessions, audit activity, checkpoints, live work, and notifications |
| Utilities | **Guide** and **Settings** | This manual, runtime configuration, privacy, web access, and credentials |

## Understand a turn

A turn shows one status row for each proposed tool call, in proposal order.
Rows distinguish running, waiting, failed, and refused work. The server creates
the human-readable description under the same redaction rules as the audit log,
so the interface does not reveal more than the evidence record.

Model reasoning, when the provider supplies it, is placed in a collapsed block.
Whether Raiker retains that working is controlled under **Settings → Privacy**.
If it was not retained, the turn says so rather than displaying an empty block
as though nothing happened.

Sources in answers link back to the text that contributed to the response.
Conversation search returns the conversation, timestamp, and turn so a recalled
answer can cite the original exchange. Incognito conversations disable ambient
recall and durable transcript use for that conversation.

## Observe and recover work

Use **Observability** when you need evidence rather than a summary:

- **Overview** reports runtime and model readiness.
- **Sessions** contains conversations and task runs. Opening a turn offers
  **Open in the conversation**, which lands on that exchange.
- **Activity / Audit log** records governed steps and can be filtered and
  exported when the audit-export capability is enabled.

  It holds **every governed step in this account, in full detail**: your own
  conversations, and the runtime steps taken outside them — connecting a
  provider, pinning a model, changing a permission. Other people's conversations
  are never shown here. It is deliberately the deep-dive view; day-to-day work
  lives in Chat, Approvals, and Tasks.
- **Checkpoints** lists recoverable pre-change state and offers governed rewind.
  Each snapshot's **Turn** links back to the exchange it was taken at, and
  *Preview rewind* opens the same preflight **Rewind to before this** opens from
  a message in Chat or Build.
- **Work** shows live background activity.
- **Notifications** collects events that need attention.

**Overview** answers the whole of "is this instance in a state I can work in".
Three tiles at the top give the runtime's readiness, how many capability gates
are closed, and what configuration is missing — each linking to the page where
you change it. Underneath, **Is the runtime itself healthy?** carries what only
the runtime knows about itself: the health transitions its own monitors
recorded, the memory integrity report and the one repair it offers, and any
readiness check that actually failed, with its reason code and remediation.

There used to be a separate **Diagnostics** tab. It read the same runtime status
this page reads and restated most of it — a tick list saying "ready" beside a
tile saying "Ready", the same missing-configuration list twice, an expansion of
the closed-gate count that Permissions already lists with controls, and a
provider table thinner than the one on Models. Its unique half is the section
above; `#/diagnostics` and `#/observe?tab=diagnostics` still open it.

Its *"Disabled / deferred capabilities"* chip list went with it, and unlike the
rest it was not a duplicate — it was wrong. It listed the shipped registry's
phase gates, so it named `web_ui` and `dashboard` as disabled to somebody reading
it in the dashboard. Both facts it was reaching for are now written down where
they are true: see
[Capabilities with no enable path](permissions-and-runtime-modes.md#capabilities-with-no-enable-path).

Checkpoint capture is size-bounded. A file over 8 MiB may still be changed, but
Raiker warns before approval that the particular change cannot be rewound. Git
commits and pushes are recovered with Git or the remote host, not with Raiker's
file checkpoint mechanism.

### Sending the record to your own tools

**Overview → Can I see this outside Raiker?** sends governed events to an
OpenTelemetry collector you name — the same record you read on this page, on a
wire your existing dashboards already watch.

Add a collector with its OTLP endpoint (`http://127.0.0.1:4318`). By default a
record carries identifiers and an event type and nothing else; **Send redacted
event payloads too** adds the payload, redacted exactly as this screen is. If
your collector needs an `Authorization` header, give the **name** of an
environment variable holding it — never the value, which Raiker will not accept
or store.

**Deliver now** sends everything that collector has not had yet. The cadence
select beside it sends the same thing on a schedule — every 20 minutes, hourly,
daily or weekly — and **On demand only** is the default. A card always says which
it is on, and names its next run when it has one, so it can never let you believe
events are flowing while nothing has run since you last pressed the button.

A scheduled delivery is the same governed action the button is, so it answers to
the same capability gate and appears in the log it exported. Pausing the host
stops it, like every other kind of background work. A run that fails re-sends
next time rather than skipping what it could not deliver, and you are told once
when a collector starts failing and once when it recovers — not once per cycle.

Turning the payload option off stops future payloads. It cannot reach into a
collector and remove what already went.

## Memory and knowledge

Durable memory changes are proposed from Chat or Build. You see the exact text
before deciding, and approved storage or deletion happens once through the
governed relay. Credential-shaped text is refused before it reaches approval.

The Knowledge Map represents what the instance currently holds. Named sources
are selected explicitly; it is not a general-purpose file browser. Citations
are bidirectional, and a missing source remains visible as a hollow node rather
than silently disappearing from the record.

Current semantic recall is limited unless you build a meaning-based index: the
default vector representation is a feature-hashed bag of tokens, not a
meaning-aware embedding model, so paraphrases without shared terms can be missed.
See [Known limits](known-limits.md).

**Overview → Is the runtime itself healthy?** compares every index and projection memory
depends on — including the conversation index behind Threads — against the
table that owns the content. It reports `clean` or names the drift, **Rescan**
runs it again on request, and the one repair it offers appears only beside the
finding it repairs. See [Memory](memory.md#checking-the-indexes).

## Web access and Git credentials

Web reads use HTTPS and reject credentials embedded in URLs. Resolved addresses
must be public and are checked again on redirects. The fetched page is converted
to sanitized text, with removed content reported. You control a blocklist; the
address-safety guard cannot be disabled.

The Git credential used for pushes is encrypted at rest and loaned to one
command at a time under a grant you make once or for a session. It is redacted
from commands, logs, errors, and output. Publishing is a separate permission
from changing a local repository.

## Voice

Voice dictation fills the normal editable composer. **Done** stops dictation
without sending; **Cancel** restores the exact previous draft; only **Send**
creates a turn. Replies can be read aloud on request. Raiker stores prompt
provenance, not microphone audio. Voice is turn-based, not continuous or
full-duplex.

Dictation can run entirely on this machine: set a speech runtime up under
**Models → Local** and it is used in place of the browser's service, with no
setting to change. The note under the microphone says which one is in use. Read
aloud stays on this machine too — it uses only a voice the browser reports as
on-device, and names the language when there is none rather than speaking with a
voice that may synthesise elsewhere. See
[Security and privacy](security-and-privacy.md#records-and-privacy-choices) for
what each does with the audio.

For the controls that determine whether an observed action may execute, read
[Permissions and the runtime](permissions-and-runtime-modes.md).
