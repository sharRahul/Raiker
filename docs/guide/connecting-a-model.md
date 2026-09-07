# Connecting a model

Connecting a provider is one step: paste your API key. That act is your
authorization — Raiker does not then ask you to satisfy a separate switch, a
separate allowlist, and a separate key before it will use what you just
configured.

This follows the project's [security posture](../architecture/HANDOFF.md#security-posture-read-before-adding-any-restriction):
Raiker is **owner-authoritative and monitored, not
prevention-by-restriction**. Every turn is still policy-checked, audited, and
stoppable; what changed is that you are not made to prove a choice you already
made.

> **Local models (llama.cpp, Ollama, LM Studio)**: start the local server, press
> **Choose model…**, then **Select**. Nothing leaves your machine.

## Configured is not ready

Raiker binds readiness to the owner, profile, exact model, and endpoint. Local
providers must answer their health/catalogue check and list that exact model.
Hosted providers must also complete a deliberately tiny one-token execution
preflight; this can incur a negligible provider charge, and catches credentials
that can list models but cannot execute because of access or billing. Evidence
expires after five minutes and is invalidated when credentials, endpoints,
catalogues, selections, or managed runtimes change. There is no silent fallback.

**Expired is not un-configured.** An expiry means nobody has looked recently, so
Raiker looks: send with an expired check and the check is re-taken as the turn is
admitted, and the turn runs on the fresh result. You are never asked to set up a
model you already set up — not after a restart, and not after an idle afternoon.
An *invalidation* is different: something changed under the model, so that one is
re-checked explicitly rather than in passing.

The same gate protects Chat, Build, Tasks, and Schedule. With no ready model —
one that has never been checked, or whose check **failed** — the primary action
is disabled and **Set up model** opens the readiness dialog, whose **Check
again** runs the exact-model check, or says there is no model to check yet when
that is the truth. (The Workbench is not in that list because it has no
composer to gate: it is the board over work that is already running.)

A successful profile carries a green **Ready** label, and the Models header says
`1 model ready` (or the corresponding count). Labels such as **Not checked**,
**Check expired**, **Runtime stopped**, **Model missing**, **Key rejected**, or
**No credit** name what still needs attention.

One of them is not about the model at all. **Choice unreadable** means Raiker
could not read back which model you chose — a workspace database that is locked,
damaged, or on a full disk. Your choice is still saved; nothing has been changed
or forgotten. The turn is refused rather than run on some other model, and you
are deliberately not asked to pick again, because picking again would not fix a
disk. Repair the workspace and the label clears on its own.

**The first-run screen can do all of this on its own.** Stage 02 of setup shows one
row per provider. The three local runtimes are *asked* what they are serving and
offer the answer in a dropdown; a runtime that is not running says so. Every
API-key provider takes its key inline and then lists **that provider's own**
catalogue, so a model can be connected and chosen without leaving the wizard.
Choosing happens in the model picker, which has a search: there is no dropdown
to scroll. A local runtime that is not installed offers to open the vendor's own
download instead of a control that could not work.

## What a fresh install claims, and what it does not

Nothing. Raiker ships profiles for every backend it speaks to, but a profile only
*names* a model once that model can exist here — the runtime was found on this
machine, you connected the provider, or you deployed a file into a slot. Until
then the profile is offered for setup and names nothing, so the setup meter, the
Global model control and both composers stay honest rather than pointing at
software you have not installed.

A local provider card says **"Not installed on this machine"** when Raiker looked
and did not find it, and says nothing when it has not looked. Detection is a
lookup of your `PATH` — never a connection to anything — and the answer is
remembered, so opening Models does not re-scan.

The card offers the fix rather than leaving you to find it: **Set up
&lt;Provider&gt;** opens that vendor's own download page. Raiker does not install
anything, bundle an installer, or accept anyone's terms for you — it opens the
page, you decide. When you have installed it, **Look again** re-runs the lookup
and the card stops saying it is missing. A runtime Raiker has no reviewed source
for offers no button rather than one that cannot work.

## Local discovery and acquisition

- **Ollama:** open the official installer from Models and pull a model by exact
  name. Raiker tracks progress and rechecks the catalogue when the pull ends.
- **LM Studio:** Raiker opens LM Studio's official download; Raiker does not
  redistribute it. Start the local server, then select an exact catalogue model.
- **Existing GGUF files:** add an explicit folder under **Local library**.
  **Browse** opens a folder picker served by the Raiker host — a browser cannot
  produce an absolute path on its own — or type one if you prefer. It lists
  directory *names* only and grants nothing; approving the folder is still the
  separate act. Raiker scans only approved roots, does not follow escaping
  symlinks, reads a bounded GGUF header, groups shards, and leaves original
  files in place. **Deploy** starts managed loopback llama.cpp for a complete
  model.
- **Hugging Face:** the tab opens on the most-downloaded GGUF repositories, so
  you have somewhere to start without knowing a repository id; search the Hub
  for anything else. Raiker shows immutable revision, files, size, format,
  licence and gated status; GGUF variants are preferred. Confirming a download
  writes a collision-safe snapshot beneath an approved library. It runs as a
  durable background job, so a multi-gigabyte pull keeps going if you navigate
  away — the panel shows its progress and a **Cancel download**, and
  **Models → Runtime & routing** is the same job under a different heading. Gated
  repositories require your own Hub token and accepted upstream terms. On a
  machine with no route to `huggingface.co` the tab says so where the results
  would be, with a **Try again** — rather than showing an empty list you would
  otherwise only understand after a search timed out. Everything already in your
  local library keeps working.
- **Conversion:** Safetensors conversion is optional and never automatic. It
  runs in a digest-pinned llama.cpp container with no network, a read-only
  source, a separate writable output, and resource limits. Pick GGUF when one
  exists.

### Downloads, conversions and other long jobs

**Models → Runtime & routing** is where every durable model job lives:
downloads, conversions, runtime installs, Ollama pulls, and local deployments.
They survive navigation and an interrupted app session, and none of them is ever
silently retried.

The list is ordered by what still wants attention: running work first, then what
failed, then history. Each job carries one action — **Cancel** while it runs,
**Retry** once it has failed in a way that can be started again — and the rest,
including **Clear record**, sit in its overflow. There is no permanent refresh:
the panel re-reads itself every two seconds while anything is running, and a
**Retry status** appears only if one of those reads fails.

- **Cancel** asks a running job to stop at its next safe point. A job that had
  not started yet stops immediately. Once you have asked, nothing the worker
  does afterwards can put the job back to *running* or report it *complete* —
  your decision is the one that stands.
- **Retry** appears on a job that **failed or was cancelled**, and only when
  Raiker recorded enough to reconstruct it. It re-runs the same job from the
  parameters saved when it started, re-reading any credential from the vault
  rather than remembering it. A job that is still running is not offered a
  retry, and pressing Retry twice starts one worker, not two.
- **Delete partial files** removes what that job left on disk, and nothing else.
  It names every exact path and the total size before you confirm — a
  conversion writes into the model-library folder *you* chose, which holds the
  models earlier conversions succeeded at, so the folder itself is never
  offered as something to delete. The button appears only when Raiker recorded
  which files the job created.
- **Clear record** removes the row and never touches a byte on disk.

---

## What is running your work

**Models → Overview** is the first thing the page says, and it answers four
questions in order:

1. **Needs attention** — only what a person has to do something about, with the
   one action that resolves each. When there is nothing, the section is absent;
   that absence is the report.
2. **What powers your work** — the model Chat, Build and Design each start on,
   where that choice came from, and whether it is ready.
3. **Effective now** — if a model cannot serve, the one that will answer instead
   is named beside it. Your choice is never quietly replaced by the fallback:
   they are two different facts and the page states both.
4. **Other models you can use** — what else is set up and not already in use.

Tasks and Schedule are not on that list because they do not hold a live default.
They capture the model chosen when the work is created, so a run that fires next
week uses the model it was scheduled with rather than whatever you have selected
by then.

**Models → Runtime & routing** holds the same facts as a table, with **Default**
and **Effective now** as separate columns, above the fallback sequence that
produces the difference between them.

---

## Connect a hosted provider

**Models → Add model** → the provider's card → **Connect** → paste the key →
**Connect**. Then give it a model: **Select models…** on the card, or the same
item in its **⋯** menu once it has one.

The Models page has five tabs, named for the questions you arrive with rather
than for where a row is stored:

| Tab | What it answers |
|---|---|
| **Overview** | What is powering Chat, Build and Design, and what needs you |
| **My models** | Every model you have set up, wherever it runs |
| **Add model** | Connect an account, install a runtime, or fetch from the Hub |
| **Runtime & routing** | What is serving, what a turn falls back to, and long jobs |
| **Usage** | What you have spent, and the rates that produced it |

The off-machine gate status reads at the top of **Add model**, before you
connect anything, because "the hosted gate is off" is what you need to know
*before* a provider refuses rather than after.

That is the whole flow. Behind it:

| What used to be required | What happens now |
|---|---|
| Turn on the **Hosted models** capability gate first | A saved connection is the authorization. The gate remains, and turning it **off** still revokes access. |
| Add the host to `RAIKER_MODEL_EGRESS_ALLOWLIST` and restart | The endpoint on the profile you configured is authorised — that host and no other. The environment variable still works for pre-authorising hosts before you configure them. |
| Generate a vault key in Settings first | The key is generated on first use at `0600`. Settings still owns viewing, rotating, and clearing it. |

Then press **Choose model…** — Raiker asks the provider for its current live
catalogue — pick a model, and **Use model**. Switching model takes effect on the
next turn; the composer chip and provider card both name the chosen model. A card
that has not got one says nothing on that line — **Select models…** is the offer,
and the card's connection and readiness lines already say where it stands.

### What is still refused

Consent by configuration is scoped, not a blanket opening:

- A provider you have **not** configured still fails closed.
- Configuring Anthropic authorises `api.anthropic.com`. It does not authorise
  any other host.
- A capability gate you **explicitly** turn off wins over a saved connection.
  Revocation is absolute, or the control would be theatre.
- Deferred dangerous domains — finance, medical, pregnancy, CCTV, home
  security, and hardware — have no governed executor and stay unavailable
  regardless. SSH and Daytona execution are separate, explicit owner-profile
  features with approval, credential-reference, host-key, timeout/output, and
  cost-ceiling controls.
- Critical actions still stop for approval, and the STOP switch still halts work
  at a safe boundary.

### Signing in with Google

**OpenAI** and **Gemini** cards offer a sign-in link. It opens the provider's own
console — where Google, Microsoft, and Apple sign-in all work — so you can create
an API key, which you then paste into Raiker.

**A ChatGPT subscription does not include API access.** ChatGPT Plus and Pro are
billed separately from the OpenAI API, and no subscription grants a third-party
application API access on your behalf. If you have Plus or Pro and no API
credit, calls will fail with a quota error however you signed in. The dialog says
this up front so it is not discovered through a 401.

Anthropic issues API keys only — there is no account sign-in to connect.

### An identity-linked key needs its workspace

Some Anthropic keys are **identity-linked**: they authenticate perfectly well and
act inside one workspace, so the provider refuses any request that does not name
which. Raiker says so and offers the field rather than telling you to go and find
a different key:

> *This key is identity-linked, so it acts inside one workspace. Add the
> workspace ID to this connection — it is beside the key in the provider's
> console — then connect again. The key you pasted is fine.*

**Advanced → Workspace ID**, in the same dialog. A refusal opens that section for
you. Most keys need nothing there, which is why it is not on the front of the
dialog. You can add one to a connection you already saved without re-pasting the
key: fill in only the workspace and press **Connect**.

If the provider then says it does not recognise the workspace, that is a
different message with a different fix — check the id against the one in the
console. Raiker never repeats the "add a workspace" ask for a value you have
already given.

### Using a ChatGPT subscription instead of a key

The **ChatGPT subscription** card is a different path from the OpenAI card, and
it is not an API key. It talks to a compatible **Codex** client installed on
this machine, over that client's local process interface. Codex opens the
browser sign-in, holds the tokens, and knows what your plan includes; Raiker
receives the signed-in state, the plan name, and the model identifiers — nothing
else. No token, refresh token, device code or sign-in URL is ever stored by
Raiker.

* **Sign in with ChatGPT** starts the flow in Codex. If Codex is not installed,
  the card says so; Raiker does not download or install it for you.
* **If Codex is already signed in, Raiker does not use that account until you
  say so.** The card says an account is signed in on this device and offers
  **Use this subscription** beside **Use a different account**. Reading the
  status never connects anything — on a shared machine the account Codex holds
  may not be yours.
* Once connected the card names the plan — "ChatGPT Plus connected" — and keeps
  **Switch account** and **Sign out** available, so an owner with more than one
  plan can move between them.
* **Choose a model** opens the picker: a search over the whole catalogue, a
  switch per model for what stays offered everywhere, and **Use** to make one
  this provider's default. The current default is marked rather than offered
  again.
* Raiker shows how much of your plan's window is left **when the provider says
  so as part of a turn** — ChatGPT reports a five-hour and a weekly window. It
  is never polled from a portal and never estimated, so a provider that reports
  nothing shows nothing. The figures appear on the provider card and in
  **Observability → Activity**.

---

## What each provider has cost you

Every provider card carries its own usage line: how many of its models you have
used, how many turns, and what they cost. A bar underneath shows that provider's
share of your total API spend, so it means something without you configuring a
budget. The page header totals it: *"1 of 10 providers set up · $0.0030 total
API cost"*.

Local providers show *"No API cost — runs on this machine"* instead of a bar.
A provider you have not used yet says *"Not used yet"*.

The header separates configured providers from exact models that are ready. A
shipped preference is never counted as ready merely because it exists in the
profile registry.

Prices come from the provider where one publishes them, from the list prices
shipped in `raiker/config/model-profiles.json` otherwise, and from your own override
above both. A model with no resolvable price reports its cost as unknown rather
than as zero. To set your own rate:

```
PUT /api/models/{profile_id}/price
{"model": "claude-opus-5", "input_per_mtok": "15", "output_per_mtok": "75"}
```

Send both rates as `null` to clear the override and fall back to the published
or shipped price.

### Rolling seven-day usage

Models → **Usage** shows one row for every connected provider and no row for
an unconnected one. **Raiker observed** is the rolling seven-day total from the
local ledger: input/output/cache tokens, owner turns, all model requests,
automatic compactions, and cost where the exact recorded models have known
prices. Local Ollama usage appears here too and is correctly labelled as having
no API cost.

**Provider reported** is a separate receipt, never blended into Raiker's count:

- OpenRouter's ordinary API key supplies its genuine key-level weekly spend and
  any limit/remaining values the provider returns.
- OpenAI and Anthropic organization usage require their separate administrator
  keys. The optional admin key is entered in the same Models connection dialog,
  encrypted separately, and never used for model calls.
- Ollama has no account-quota service, so its provider side says unsupported
  while Raiker's observed local usage remains available.

Provider responses are reduced immediately to bounded numeric metrics and cached
for five minutes; raw account payloads and identifiers are not stored. **Refresh
provider data** makes the external checks explicit. An optional owner weekly
token budget is advisory Raiker control, not a provider subscription limit and
not a promise about billing or reset dates.

## One instance, one default

Each connection belongs only to this Raiker instance: a key entered here is
encrypted in this instance's vault and is not shared with another install, a
another workspace, or the terminal client running elsewhere. **One ready
provider is enough to work** — nothing requires you to connect more than one.

**Default model** is what serves any surface that does not choose its own,
including every scheduled run at the moment it begins. Chat and Build can pick
per prompt; Tasks and Schedule cannot, so the default is what they use.

**Which models are offered is a separate choice.** **Select models…** on a
provider card opens a list of everything that provider publishes, with a switch
against each. The ones you switch on stay in every picker, grouped under that
provider; the default is one of them. A provider you have not connected offers
nothing, and a model Raiker has measured as unavailable is not offered until it
answers again.

---

## Fallback sequence

Below the provider grid, **Model fallback sequence** orders the backends Raiker
tries when the selected one is unavailable. Listing a hosted provider there
grants nothing on its own — each candidate is still gated by the same policy.
Point it at your local runtimes so a turn never dead-ends when a hosted API is
down.

"Unavailable" is four specific things: no network, a timeout, a host that does
not respond, or a policy denial. Raiker tries the next candidate in your order
for each of them, and with no fallback configured the turn fails closed rather
than silently choosing a backend you did not pick.

---

## Advisor model

When you run a local model, it can consult one advisor — typically a hosted
model — through the governed `consult_advisor` tool. It is the way to keep a
small local model as your default and still reach for a larger one on the
questions that need it.

**Picking an advisor grants nothing on its own.** Every consult is gated at call
time by all of:

- the `advisor_model_runtime` capability;
- its decision mode, which is **ask** by default and withholds the consult until
  you allow it;
- the advisor provider's own policy — its hosted gate, the egress allowlist and
  its API key.

Miss any one and the consult is refused with its own named reason, exactly as
any other governed action is.

The advisor's answer is **always treated as untrusted data**, never as
instructions: it reaches the local model as material to consider, and it cannot
propose an action, widen an approval, or change what the turn is allowed to do.
Neither the question nor the answer enters the audit log — only their lengths
do, so the record shows that a consult happened and how large it was without
keeping either side of it.

## Off-machine provider posture

**Models → Add model** opens with four read-only facts about everything that
would leave this machine: the hosted model gate, the private-network gate, whether an
egress allowlist is configured, and how many off-machine profiles exist. It is
status, not a control — allowlist values and API keys are never displayed
anywhere in the product, including here.

The two gates report **what they answer**, not what is stored against them.
Connecting a provider is itself consent to use it, so a gate nobody has touched
reads **On (by connection)** once any provider is connected; before that it
reads **Off until connected**, which is both the verdict and the thing that
changes it. A gate you deliberately turned off in **Permissions** reads **Off**
whatever is connected — an explicit decision outranks a connection, always.

A hosted provider fails closed unless **all** of the following are present: the
runtime gate, the threat-model acknowledgement, the confirmation token, the
egress allowlist, and the provider key. There is no silent fallback to a hosted
model: if the model you chose cannot run, the turn fails with the reason rather
than quietly reaching for one that costs money and leaves the machine.

---

## If it still refuses

Every refusal is a named reason code with a specific fix. The sign-in dialog now
states the fix and links to the control that applies it. The full table is in
[Troubleshooting](troubleshooting.md).
