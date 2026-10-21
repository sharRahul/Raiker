# 02 Permissions and approvals

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.

This document changes how permissions are **presented**. The authority model,
the policy store and the runtime's decisions do not change. A label never
authorises an action.

## How the reference products do it

### Hermes (from source)

* **Approval mode** per profile, in the status bar: *Manual* (ask before actions
  that need approval), *Smart* (assess automatically, ask when needed), *Off*
  (no prompts).
* **Approval card in the transcript**, owned by one host per session so tool rows
  never move it: the exact command, *Run*, *Reject*, and a menu with *Allow this
  session* and *Always allow…*. Always allow opens a confirmation that adds a
  pattern to a permanent allowlist. When Smart mode refused an action, only
  *Once* and *Deny* are offered.
* **Timeout**: an unanswered approval expires, the command does not run, and the
  transcript says so with a link to the setting.
* **Capabilities page**: Skills, Plugins, Connectors, Toolsets tabs, each a list
  beside a detail pane, with a profile selector.
* **Connector detail**: named accounts ("work", "home"), and "What Hermes may do
  with Gmail": tools grouped by type with switches and three presets (*Read
  only*, *Turn off destructive*, *Everything on*). Each tool says whether it only
  reads or is destructive.
* **Settings › Safety**: approval mode, timeout, command allowlist, secret
  redaction, private URLs, checkpoints.

### Muse (from Meta's posts and reviews)

* Connectors in Settings: a list of apps, Connect beside each, *read-only* or
  *full actions* per app, disconnect any time.
* **Sentinel**, a separate component, decides *allow*, *deny* or *ask* for every
  connector action and outgoing request, using the app, the action type, what it
  touches and the user's request.
* **Ask only when it matters**: designed against approval fatigue. Ordinary
  browsing proceeds; writing an email, buying, or anything hard to undo stops.
* **The prompt is app UI, not chat text**, so a hijacked agent cannot fake
  consent. Reported scopes: once, task, site, time span, always (secondary
  sources; not confirmed by Meta's own pages).
* An activity log lists what the agent did and which permissions were approved.
* Device access on Mac is opt-in and skippable. A public dispute over Messages
  access shows why every grant must be visible and revocable.

## Raiker: one record, several places

Each permission is stored once. These surfaces read and write the same record,
so there is no second copy to drift.

### QUI-P01 — Layers

| Layer | Purpose | Changeable in normal UI |
|---|---|---|
| Hard safety boundary | Reading raw passwords, bypassing multi-factor sign-in, account recovery, unapproved payments, broad access requested by injected content | No |
| Execution profile | Overall task authority | Yes |
| Connected-service access | What may be done with Gmail, GitHub, the browser… | Yes |
| Runtime approval | The exact consequential action | Per action |

### QUI-P02 — Profile chip in the composer

How much Raiker does without asking, for this conversation or task: **Careful ·
Standard · Within limits**. There is no "Off". The chip shows the consequence in
its menu ("Standard: researches and prepares; asks before sending, deleting,
paying or sharing"). A posture or profile can only narrow the owner's settings,
never widen them.

### QUI-P03 — Permissions page

The same settings grouped by activity across every service. Layout and
categories: [01, QUI-L06](01_LAYOUT_SYSTEM_AND_PAGES.md#qui-l06--permissions).

Each permission's detail pane shows: the activity in plain words, current policy,
what it means, scope, recent use, and Change. Choosing **Allow with limits**
requires the limits: account, recipients or domains, attachments, maximum volume,
whether sensitive data still asks, one task / one project / future work, and an
expiry where it makes sense.

No raw technical labels (MCP, shell execution, provider grant, environment
variables) as everyday categories; they live under Advanced.

### QUI-P04 — Connection detail

"What Raiker may do with Gmail", with three presets:

* **Read only** (the default for every new connection)
* **Ask before changes**
* **Custom**, which opens Permissions filtered to that service

Each activity is labelled *Reads*, *Changes* or *Can't be undone*, in words.
Several accounts per service, named by the owner ("Work Gmail", "Personal
Gmail"). Recent activity under the list. Reconnect and Disconnect.

Raiker asks for a connection only when a task needs it, never as a setup
checklist.

### QUI-P05 — The approval card ("Raiker Safety")

Drawn by the app, never by a model's message, and styled unlike any message. It
appears inline in the conversation, in the top-bar count and in the Approvals
queue; answering in one place clears all three.

Content, in this order:

1. What will happen
2. Why it is needed
3. Which account, service or recipient is affected
4. What data is involved
5. Cost, or whether it can be undone
6. The safer alternative, when there is one

Buttons: **Decline**, **Change**, **Allow once**, **Allow for this task** (where
policy allows; requires limits). There is no "Always allow".

While waiting, the status line reads "Waiting for your decision".

### QUI-P06 — Approval time limit

An unanswered approval expires (default 30 minutes, set in Settings ›
Security). The task does not proceed; it is marked "Not done: no decision" with
**Ask again**. It never proceeds on its own.

### QUI-P07 — Approvals page

Layout B: queue (300 px) with Pending, History and filters; the selected
decision (600–720 px) with sticky actions; evidence (300 px: source task, plan,
technical detail, audit evidence), closed below 1,600 px. Queue rows 68 px:
action, target, source task, risk label, time.

### QUI-P08 — Activity and approvals you've given

What happened and which approval allowed it appears inside each task and in
Approvals › History. Memory › Controls lists "Approvals you've given" with Undo,
alongside "What Raiker has learned to do" ([06, QUI-F09](06_FEATURES_AND_IMPROVEMENTS.md)).

### QUI-P09 — Approval fatigue

Following Muse's design write-up: ordinary, reversible reads proceed under the
profile; Raiker stops for sending, posting, deleting, paying, sharing and
anything it cannot undo. If owners approve the same narrow action repeatedly,
Raiker may suggest an **Allow with limits** rule. It never creates one silently.

## Acceptance

* No surface offers an unrestricted "Always allow".
* A model's text cannot render anything that looks like an approval card.
* Changing a permission in one place is reflected in every other place without
  reload.
* Every approval in History links to the task it allowed.
