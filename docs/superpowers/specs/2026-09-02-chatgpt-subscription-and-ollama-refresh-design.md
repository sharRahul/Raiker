# ChatGPT subscription provider and Ollama refresh

## Goal

Let an owner connect a ChatGPT subscription-backed Codex model from both the
first-run model step and Models, and select it for Chat or Build. After an
Ollama pull completes, refresh all connected provider catalogues so a newly
available model is immediately selectable. Let installed, signed releases check
for, apply, and restart into a verified GitHub Release update from Settings.

## Scope and decisions

The product will add a provider distinct from the existing `openai-hosted`
API-key provider. Its name in the interface is **ChatGPT subscription (Codex)**.
It is not an API-key shortcut and it does not claim that a ChatGPT subscription
can call the OpenAI API directly.

The integration will use the local Codex App Server over stdio and its
documented account protocol. The app server owns the ChatGPT OAuth flow,
persistent credentials, and token refresh. Raiker must never receive, store,
or expose OAuth access or refresh tokens. Raiker persists only connection state
that is safe to display: connected/disconnected, model availability, plan class
when reported, and a non-secret error code.

The provider is available to both Chat and Build. The backend bridges Codex
threads and streamed events into Raiker's model-provider contract. Codex
approval requests are surfaced through Raiker, which applies its existing human
gate and records the decision. A Codex capability that cannot be presented to
and governed by that boundary is refused; the bridge must not silently cause an
action outside Raiker's policies.

## Connection experience

Both first-run and Models show a ChatGPT subscription (Codex) provider row or
card in the hosted-provider group. It has a **Sign in with ChatGPT** action,
separate from **Connect OpenAI API**.

The action starts a local Codex App Server session and begins the documented
ChatGPT login flow. Raiker opens the official authorization URL when the
browser flow is available and shows the official device-code URL and one-time
code when that is the selected fallback. The UI polls connection state until
Codex reports successful completion, cancellation, expiration, or failure. It
never renders tokens, callback secrets, or account credentials.

Once connected, the model picker displays only models reported by the current
Codex session. A selected model is included in the global model picker and
therefore can be selected by Chat and Build. The UI names the current plan only
when Codex reports one, and names sign-in, missing-Codex, session-expired, and
subscription-limit failures with actionable remediation. Disconnect asks for
confirmation, calls Codex logout, clears the Raiker connection metadata, and
leaves the API-key provider unchanged.

## Runtime and safety

`CodexAppServerClient` is an owner-scoped, lifecycle-managed JSONL/stdio client.
It serializes request IDs, demultiplexes server notifications, bounds startup
and turn timeouts, terminates its child when Raiker stops, and redacts all
protocol data that can contain credentials before logging.

`CodexSubscriptionProvider` implements the existing asynchronous model-provider
interface. It maps a Raiker request to a Codex thread and turn, forwards
incremental text and terminal errors as model stream events, and maps Codex
approvals to Raiker's existing approval boundary. It does not implement
embeddings; selecting it for an embedding-only operation fails closed with a
specific unsupported-capability result. Model listings and readiness checks come
from the live Codex session rather than a fixed catalogue.

The provider profile is remote, egress-gated, and not an implicit fallback. It
is enabled only when the configured Codex executable meets the supported
protocol version. A missing or incompatible executable is a visible unavailable
state, never a background install or a fallback to OpenAI API.

## Connected-provider catalogue refresh

The pull worker already completes the operation and invalidates the Ollama
profile readiness. The client currently only announces that the job was queued,
and no mounted model picker learns that it completed.

Model catalogue refresh is a provider-wide capability, not an Ollama special
case. Models and first-run expose **Refresh connected model lists**, an explicit
owner action that re-queries every connected provider, replaces each cached
catalogue, and refreshes the shared model store used by the Chat and Build
selectors. The action never invents model names and does not poll providers in
the background.

`ProvidersPanel` retains an Ollama pull operation ID and observes it until a
terminal state. On successful completion it invokes this same refresh pathway;
the status says that the pull is complete and the model is ready to choose.
The shared refresh pathway also runs after a local deployment and after a
connection is changed. Failed and cancelled jobs keep their existing Activity
outcome and do not claim a refresh. A provider changed outside Raiker remains
owner-refreshable through the explicit action.

Ollama's account portal currently shows session and weekly Cloud Usage for a
signed-in account, but its supported local API supplies only per-response token
metrics. Raiker will not scrape browser cookies or the private account page to
imitate that portal. Until Ollama publishes an account-usage API, Raiker shows
only its own recorded provider activity and, where useful, an action opening the
official usage portal.

## Software updates

The update source is a pinned, signed release channel published with the
project's GitHub Releases. It is distinct from source-control synchronization:
Raiker never runs `git pull`, writes a source checkout, or accepts a release URL
or signing key from the Settings page.

Settings gains a **Software updates** system section. It shows the installed
version and provenance, signed-channel state, last successful check, offered
version, and retained recovery version. **Check for updates** invokes the
existing owner-triggered signed-channel check; opening the section itself makes
no network request. A source checkout, unsigned build, or installation without
a pinned channel is explicitly unavailable and directs the owner to its normal
development update workflow.

For an available signed release, **Update and restart** first presents a
confirmation naming the offered version and the interruption risk. It creates a
short-lived, local update handoff for an external launcher helper; the serving
web host never replaces files from its own request handler. After the host exits,
the helper fetches the channel index, signature, release bundle, manifest, and
signature through the existing bounded updater; it re-verifies every signature
and digest, makes a recovery copy, and atomically swaps the installation. It
then restarts Raiker through the installed launcher or registered service.

An active turn or operation is disclosed before confirmation. If the supported
lifecycle cannot guarantee a restart, the update is not applied and Settings
says why. Download, signature, migration, swap, or restart failure retains the
current installation and its recovery point. Source builds and unsigned
installations are never eligible for this flow.

## Verification

- Unit-test the app-server JSONL client: initialization, browser and device-code
  login, account updates, cancellation, timeout, malformed events, and secret
  redaction.
- Test provider listing, streaming, model selection, unsupported embeddings,
  subscription-limit errors, and approval relay with a mocked app server.
- Test authorized API routes and reject a caller that is not the owner or gate
  manager.
- Test first-run and Models UI states for connect, pending login, connected,
  expired, missing executable, and disconnect; confirm both Chat and Build
  include a selected subscription model.
- Test an Ollama pull that transitions queued -> complete, verifying the picker
  refresh includes the new model and failed/cancelled pulls do not advertise it.
- Test the explicit all-provider refresh, including refresh propagation into
  mounted pickers and the Chat and Build selector store without background
  provider polling.
- Test Settings update status, check, confirmed external-handoff apply, restart,
  and recovery state. Prove source checkouts, unsigned builds, unpinned
  channels, signature failures, download failures, and unsupported restart
  lifecycles cannot mutate an installation.
- Keep live Codex and Ollama verification opt-in and environment-gated; no test
  may require a personal subscription or a locally running Ollama daemon.
