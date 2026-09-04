# Security and privacy

Raiker is **owner-authoritative and monitored**. Its controls are designed to
keep an AI-proposed action inside authority you deliberately granted, preserve
evidence of what happened, and fail closed when a required executor or secret
is unavailable. It does not try to prevent the machine's owner from using their
own machine.

## The local owner

First run creates an owner principal with a username and password stored by the
local instance. There is no Raiker cloud account. Each request resolves an
acting principal, and agentic work uses a short-lived machine identity so the
audit record can distinguish you from the agent acting for you.

The browser session rides in an `HttpOnly`, `SameSite=Strict` cookie scoped to
this host, so reloading the page keeps you signed in. Nothing on the page can
read it — that is what `HttpOnly` means — and it is never written to
`localStorage`. Because a browser attaches a cookie automatically, every
state-changing request must also echo a CSRF token from a second, readable
cookie, and a request stating an origin that is not this host is refused before
that token is even compared. A caller using an `Authorization: Bearer` header
instead — the CLI and the tray — is exempt, because a header the browser never
attaches on its own cannot be forged by another site. Changing the owner
password signs out other devices. Individual sessions can also be revoked under
**Settings → Security & sign-in**.

## How authority is decided

| Control | Where | What it decides |
|---|---|---|
| Agent runtime | **Settings → Runtime configuration** | Whether Raiker accepts new executions at all |
| Capability gate | **Permissions** | Whether a category of action is available to the owner and agent |
| Decision mode | **Permissions** | Whether an eligible action asks, is allowed, runs automatically, or is denied |
| Turn posture | Chat or Build composer | Additional restrictions for this conversation, such as Build Plan/Edit/Auto and approval policy |
| Approval | **Approvals** | Whether one specific proposed action may proceed |

A turn may tighten authority but cannot widen it. The agent cannot turn on its
own capability gate, change its standing decision mode, or bypass a disabled
runtime.

Higher-risk gate changes require a human runtime-gate manager, a reason, a
typed phrase recording intent, and acknowledgement of the capability's threat
model. The phrase is not a password. Every capability with a working executor
has a threat model in the [threat-model index](../threat-models/README.md).

## Configuration is scoped consent

Saving a provider credential authorizes use of that provider and its configured
endpoint. It does not authorize arbitrary network hosts, and it does not defeat
an explicit capability revocation. For example, connecting Anthropic authorizes
the selected Anthropic endpoint; a different provider remains unavailable until
you configure it.

This removes duplicate setup switches without removing runtime checks. Every
turn still crosses policy, capability, approval, execution, redaction, and audit
boundaries.

## What approval performs

The approval detail states the effect before you decide. Supported action types
such as bounded file writes and patches, checkpoint restore, task/project
changes, memory changes, Git branches/commits/pushes, selected connector writes,
and configured remote execution may execute once through the governed relay.
They are re-checked at execution time.

An approval for a capability without a registered executor is record-only and
does not perform an action. Network and process proposals that are not attached
to a supported executor remain decision records. Never assume the word
“approved” means a side effect occurred; read the `executes_action` statement
and result in the approval detail.

Critical actions always retain a human-only, step-up-verified lifecycle.
Composer options that skip ordinary prompts do not bypass path confinement,
sandbox policy, command restrictions, threat-model holds, or critical approval.

## Credentials and network data

Provider and connector credentials are encrypted in the instance vault. A
missing or invalid vault key causes affected connectors to fail closed; Raiker
does not fall back to plaintext storage. Git credentials are issued to one
command at a time and are removed from logs, errors, command displays, and
output.

Hosted model prompts and connector data necessarily leave the machine for the
endpoint you configured. Local-first describes Raiker's control plane and data
ownership, not a promise that a hosted model runs locally. Use local or
home-lab models when prompts must remain on infrastructure you control.

Web fetches require HTTPS, disallow credentials in URLs, reject private or
otherwise unsafe resolved addresses, and repeat the address check after every
redirect. Content reaches the model as sanitized text.

## Records and privacy choices

The append-only audit log records conversations and governed steps, scoped to
the owner account. Monitoring records lifecycle status and redacted findings,
not unbounded copies of all traffic. Local scans inspect only configured
workspace paths.

Under **Settings → Privacy**, choose whether model reasoning is retained.
Incognito conversations switch off ambient recall for that conversation.
Voice dictation stores prompt provenance but not microphone audio.

Dictation is transcribed on this machine when you have set a speech runtime up
under **Models → Local**, and by your browser's own service — which on some
browsers processes the audio externally — when you have not. There is no setting
to change: adding the runtime is the whole decision, the note under the
microphone says which one is in use, and nothing is contacted until you dictate.
Raiker refuses a runtime address that is not on this machine, and never writes
the recording to disk on either path.

Read aloud goes the same way, without a runtime to install. Some browsers ship
remote voices alongside the operating system's own and pick one without saying
so, so Raiker chooses only from voices the browser reports as local and refuses
to speak rather than use one it cannot vouch for. What crosses the boundary
there would be the *answer text* rather than a recording of you — smaller than
dictation, and still yours.

Back up or export the instance deliberately: local ownership also means you are
responsible for preserving its conversations, audit records, configuration, and
vault material. Run `raiker-app --print-paths` before backup or uninstall.

## Deliberately unavailable domains

Finance, medical, CCTV, home-security, pregnancy/baby, and direct hardware
actions have no governed executor or enable path. They fail closed and are
listed under **Observability → Diagnostics**. Raiker's ordinary assistant output
is not a substitute for professional advice or authorization in those domains.

For implementation-level boundaries, see
[Security architecture](../architecture/SECURITY_ARCHITECTURE.md) and
[Security and policy](../architecture/SECURITY_AND_POLICY.md).
