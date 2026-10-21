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
> **Choose a model**, then **Use** the one you want. Nothing leaves your machine.
> A running Ollama is found on its own; see [Ollama: found running, chosen
> once, kept checked](#ollama-found-running-chosen-once-kept-checked).

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
one that has never been checked, or whose check **failed** — **Set up model**
opens the readiness dialog, whose **Check again** runs the exact-model check, or
says there is no model to check yet when that is the truth. In Chat, **Send**
stays pressable: it opens the same dialog and keeps your message, which is sent
once a model is ready unless you choose **Don't send**. Home's composer hands
its message to Chat, so Chat's gate applies to it too.

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

**The first-run screen can do all of this on its own.** Setup's **Model** stage
leads with the easiest working path — a runtime installed on this machine that
already names a model needs no account and no key (a llama.cpp slot does not
name one until a GGUF is deployed into it) — and keeps the full provider matrix
behind **Other options**. Choosing a model there checks it straight away, so the
first message you send in Chat is not refused as unchecked. That matrix shows one row per provider. The three local runtimes are *asked* what they are serving and
offer the answer in a dropdown; a runtime that is not running says so. Every
API-key provider takes its key inline and then lists **that provider's own**
catalogue, so a model can be connected and chosen without leaving the wizard.
**Advanced setup** opens this page when you want deeper configuration; you do not
need it to finish setup.
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

## Ollama: found running, chosen once, kept checked

Raiker ships no Ollama model as a default. When Ollama is running on this
machine — the desktop app included, even when `ollama` is not on your PATH —
Models and first-run setup say **Running on this device** and offer **Choose a
model**, listing exactly the models your Ollama is serving. Nothing is chosen
for you.

The model you choose is remembered, and it is checked as you choose it, so it
reads **Ready** straight away. From then on Raiker checks it again on its own
every fifteen seconds: stop Ollama and the row says it is not running and
Overview offers **Start the runtime**; remove the model and it says the model is
missing; start Ollama again and **Ready** comes back. An open Models page
follows those changes without a reload, and you never have to press **Check**
to keep a local model ready.

The check is a read of Ollama's own model list on this machine. It never leaves
the machine, never goes through a proxy, and changes nothing — your choice is
still only ever made by you.

**Ollama running here is not the same as a model running here.** Ollama also
serves cloud models (names ending `-cloud` or `:cloud`, such as
`gpt-oss:20b-cloud`), and a prompt to one of those is processed at ollama.com.
Raiker reads where each model runs from Ollama's own list, so setup, Models and
the comparison say **runs on this device** only for a model that does, and name
ollama.com for one that does not. A model Ollama does not describe is treated as
leaving the device.

Ollama also says which models can use tools. A model listed without that ability
(`gemma3:1b`, for example) still answers in Chat, but its turns are sent without
tools, so it cannot read files, search or act; choose a tool-capable model for
that.

## Local discovery and acquisition

- **Ollama:** open the official installer from Models and pull a model by exact
  name — the box starts empty, so nothing is pulled that you did not type.
  Raiker tracks progress and rechecks the catalogue when the pull ends.
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

**A row that is not ready says which step stops it.** Under the model, four
steps in the order you meet them — **Provider connected → Model found → Model
chosen → Runs** — with a tick for each one passed, a warning on the one that
needs you, and the ones after it simply waiting. Beside them is one button: the
single thing that moves the stopped step forward — **Connect a provider**,
**Choose a model**, **Start the runtime**, **Update the credential**. **Check it
now** runs the exact-model check on the spot, for a model you have chosen and
never run: *not checked yet* is a different fact from *broken*, and the line
never ticks a step nothing has checked. A ready row says **Ready** and nothing
else.

Tasks and Schedule are not on that list because they do not hold a live default.
They capture the model chosen when the work is created, so a run that fires next
week uses the model it was scheduled with rather than whatever you have selected
by then.

**Models → Runtime & routing** holds the same facts as a table, with **Default**
and **Effective now** as separate columns. The fallback sequence that produces
the difference between them is one section further down, under **Advanced
routing** — folded, because most of the time the question is which model is
serving rather than what happens when it cannot. What is *never* folded away is
the substitution itself: a fallback that displaced your selection is named in
that table, above the disclosure, because it changes which provider your words
reach.

**A model you have not chosen is never described as selected.** On a workspace
where you have set no default, the picker says **Not selected** and means it.
Raiker ships with profiles it can offer, and none of them is a choice you made.

---

## Comparing models

**My models → Compare** puts every model you have set up in one table:
**Runs** (on this device, a private server, or a hosted service — and so whether
your prompts leave this device), **Context**, **Tools**, **Vision**, **Estimated
cost** and **Availability**. Choosing still happens in the list; the table is
for deciding.

**Unknown means no source states it.** A profile that declares nothing about
vision reads *Unknown*, not *No*; a hosted model with no published rate reads
*Unknown*, not *$0*. A model that runs on this machine has no API bill and says
so. Rates are list prices per million tokens in and out — what you have actually
spent is on **Usage**.

A model you have not set up — a hosted provider you never connected, a local
slot with nothing deployed — is not in the table, because it is not something
you could pick. One that is set up and currently failing stays in, with the
reason in **Availability**.

Provider and profile identifiers are not labels. Where a stable id is useful —
correlating a usage card with a log or an export — it is under **Details** at
the foot of the card.

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
| Add the host to `RAIKER_MODEL_EGRESS_ALLOWLIST` and restart | Nothing. Saving the connection authorises that connection's own address — its scheme, host and port — and no other. The variable is retired: if it is still set, Raiker says so once in its log and otherwise ignores it. You can remove it. |
| Generate a vault key in Settings first | The key is generated on first use at `0600`. Settings still owns viewing, rotating, and clearing it. |

Then press **Choose model…** — Raiker asks the provider for its current live
catalogue — pick a model, and **Use model**. Switching model takes effect on the
next turn; the composer chip and provider card both name the chosen model. A card
that has not got one says nothing on that line — **Select models…** is the offer,
and the card's connection and readiness lines already say where it stands.

### Which hosted providers there are

Anthropic, OpenAI, Gemini and a ChatGPT subscription lead the **Hosted** section.
Beside them are eight more OpenAI-compatible APIs, each its own card with its own
key: **DeepSeek**, **Groq**, **Mistral**, **xAI**, **Together AI**,
**Fireworks**, **NVIDIA NIM** and **Cerebras**. Each card says where its key is
issued; each key is sent only to that provider's own API host, as a bearer
token. **OpenRouter**, **Hugging Face** and **Ollama Cloud** route to many
models through one key and sit under **Advanced**, with **OpenAI-compatible** for
a server of your own (vLLM, SGLang, a home-lab host).

A provider can accept your key and still decline one of its models for Raiker:
OpenRouter offers some free models only to apps on its own list. Raiker says so
— *the provider will not run this model for Raiker; your key is fine* — and the
repair is another model, not another key. OpenRouter requests name Raiker as the
calling app.

### Is your own server set up for agent work?

A model you run yourself — Ollama, LM Studio, llama.cpp, MLX or an
OpenAI-compatible server — can answer questions and still be unable to act.
**Details → Check this server** sends it one request with one harmless tool and
reads the context it is serving, and says which it is:

| Tool calling | What it means | What fixes it |
|---|---|---|
| **Works** | The model calls tools natively. | — |
| **Returned as text** | The server sends the call back as plain text. | Turn on its tool-call parser (vLLM or SGLang `--tool-call-parser`, llama.cpp `--jinja`); for Ollama, choose a model it lists with native tool support. Raiker can still read a JSON call from text. |
| **Refused** | The server would not accept tools. | vLLM `--enable-auto-tool-choice --tool-call-parser <family>`; llama.cpp `--jinja`; for Ollama, a model it lists with tools. |
| **Not called** | The model answered without using the tool. | A larger model, or one trained for tool use. |

**Serving context** is what the server says it is serving now, read only from a
server on this machine. Under 32,768 tokens the check says which setting raises
it (`OLLAMA_CONTEXT_LENGTH`, llama.cpp `-c`, vLLM `--max-model-len`). Nothing on
the server is changed.

### Context window override

When a provider does not say how much context a model has, or says something
wrong, **Details → Context window override** sets it exactly, with the reason you
give; turns and compaction then use that window, and the override history keeps
every change. **Clear override** goes back to what the provider reports.

### Backup keys

Any provider that takes a key also takes up to three **backup keys**, under
**Advanced** in its connect dialog. When a key is rate limited or its account is
out of quota, the same request moves to the next key and the refused one sits
out — a minute for a rate limit, an hour for an empty balance. The card says how
many backups are saved and, while one is resting, which key is in use and why.
Raiker never shows a key back; re-pasting the main key keeps the backups, and
**Remove the saved backup keys** clears them. Another kind of refusal — a key
the provider rejects outright — is not rotated past: it is reported, because
that key needs your attention.

### Servers of your own, by name

**OpenAI-compatible** is any server that speaks the OpenAI API — vLLM, SGLang,
llama.cpp's server, LM Studio on another machine, Ollama's `/v1`, a home-lab
host. Its dialog asks for a **Name** (yours to choose: *Home GPU*, *Work vLLM*),
the **Endpoint**, and a key only if the server wants one. **+ Add another
endpoint** under the Advanced cards adds a second, third and fourth, each its own
card with its own address, key, models and readiness, and each shown under its
name in every model picker. Where the address points decides what it needs:
this machine needs nothing, a private-network address the **Home-lab models**
gate, an internet address the **Hosted models** gate.

A server can serve a model that cannot use tools. When it refuses a request for
carrying tools, Raiker asks again without them and remembers that model, so the
answer still comes — and that model can read, search and act on nothing.

Once OpenRouter is connected its card carries **OpenRouter routing**, two choices
that travel with every request: **Only providers that do not store prompts**
(OpenRouter's `data_collection: deny`) and **Prefer** — OpenRouter's default,
lowest price, highest throughput or lowest latency. Nothing is denied until you
tick it: with it ticked, some free models may have no provider left to serve
them. Re-pasting the key keeps both choices.

### Already have the key in your environment?

If Raiker runs with the provider's own variable set (`OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, …), the connect dialog offers **Use the key from
`<VARIABLE>`**. Tick it and press **Connect**: the connection is saved, the key
stays where it is, and the page never sees it. Until you do that, a key in the
environment is not a connection — it authorises nothing off this machine on its
own, so an agent cannot reach a provider merely because a key happens to be set.

This is also the upgrade path from an installation that used
`RAIKER_MODEL_EGRESS_ALLOWLIST` with environment keys: connect each provider
once, then remove the variable.

### What is still refused

Consent by configuration is scoped, not a blanket opening:

- A provider you have **not** configured still fails closed
  (`model_connection_required`), whatever is in your environment.
- Configuring Anthropic authorises `https://api.anthropic.com` on port 443. It
  does not authorise any other host, port or scheme — and an environment
  override cannot move a saved connection somewhere else
  (`model_connection_origin_mismatch`).
- A connection authorises a *name*, and Raiker also checks where that name
  leads, every time it opens a connection. A hosted provider must resolve to
  public addresses only; a home-lab endpoint to addresses on your network; a
  local one to this machine. Anything else is refused before a byte is sent
  (`model_dial_refused:<reason>` — a policy answer, not a network fault), and
  the address that passed is the one dialled, so a name cannot be re-pointed
  between the check and the connection. Cloud metadata services
  (`169.254.169.254`, `metadata.google.internal`, …) are never a destination.
  A link-local server you own on a direct cable needs **Allow a link-local
  address** ticked on its connection.
- A request that goes through your proxy is resolved by the proxy, so this
  address check does not apply to it. Home-lab and local endpoints never use a
  proxy, and a key is never sent over plain HTTP through one.
- A connection for one provider never authorises another, and a fallback model
  needs its own connection.
- Nothing an agent does can create or change a connection. Only you, signed in,
  on the Models page (or the ChatGPT sign-in) can.
- A capability gate you **explicitly** turn off wins over a saved connection.
  Revocation is absolute, or the control would be theatre. **Permissions →
  Hosted models** (and **Home-lab models**) reads **On by connection** while a
  connection is what keeps it on, and offers **Turn off**; afterwards a
  connected provider's card reads **Policy blocked**, and your connections stay
  saved for when you turn it back on.
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

Some Anthropic keys are **identity-linked** — a *personal* or *service account*
key created without being scoped to one workspace (Anthropic's
authentication guide
explains the key types). They authenticate perfectly well, but each request must
name the workspace it acts in, so the provider refuses any request that does not.
The workspace ID starts `wrkspc_` and is in the **ID** column of **Settings →
Workspaces** in the the Anthropic assistant Console. Raiker says so and offers the field rather than telling you to go and find
a different key:

> *This key is identity-linked, so it acts inside one workspace. Add the
> workspace ID to this connection — it is beside the key in the provider's
> console — then connect again. The key you pasted is fine.*

**Advanced → Workspace ID**, in the same dialog. A refusal opens that section for
you. Most keys need nothing there, which is why it is not on the front of the
dialog. You can add one to a connection you already saved without re-pasting the
key: fill in only the workspace and press **Connect**.

First-run setup asks the provider before it recommends it: a stored key that
lists nothing is never called *connected*. With an identity-linked key the
recommendation reads **Anthropic needs its workspace ID**, and **Add the
workspace ID** puts the cursor in that field; once it is added the provider's
models are listed and you choose your default from them. The setup step itself
appears at once; the providers fill in as they answer.

If the provider then says it does not recognise the workspace, that is a
different message with a different fix — check the id against the one in the
console. That covers both a malformed id and a well-formed one your key has no
access to (Anthropic answers the second with *Workspace not found*). Raiker never
repeats the "add a workspace" ask for a value you have already given.

Raiker sends every Anthropic key the way that guide does, as a bearer token, with
the workspace header only when you have named one.

### Using a ChatGPT subscription instead of a key

The **ChatGPT subscription** card is a different path from the OpenAI card, and
it is not an API key. It talks to a compatible **local subscription client** client installed on
this machine, over that client's local process interface. local subscription client opens the
browser sign-in, holds the tokens, and knows what your plan includes; Raiker
receives the signed-in state, the plan name, and the model identifiers — nothing
else. No token, refresh token, device code or sign-in URL is ever stored by
Raiker.

* **Sign in with ChatGPT** starts the flow in local subscription client. If local subscription client is not installed,
  the card says so; Raiker does not download or install it for you.
* **If local subscription client is already signed in, Raiker does not use that account until you
  say so.** The card says an account is signed in on this device and offers
  **Use this subscription** beside **Use a different account**. Reading the
  status never connects anything — on a shared machine the account local subscription client holds
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

### Spending limit

The one limit Raiker **enforces** is at the top of Usage: a dollar amount for
the last 24 hours, across every model and everything that uses one — Chat,
Build, Design, routines and the work they delegate. **Set a limit** (from $0.01
to $10,000); leave it empty for none.

It is checked before every model call. When the window's spend reaches it, a
running turn stops at its next safe boundary with *your spending limit … is
reached*, and new work stops before its first model call, until the window has
room again or you raise or clear the limit. A response already in flight when
the limit was crossed still finishes, so the overrun is at most what was in
flight.

A turn you stop part-way through is still billed for what the provider had
counted, and is recorded that way: Anthropic says what the input cost as soon as
the answer starts. OpenAI-compatible providers (OpenAI, OpenRouter, Ollama)
report usage only when the answer ends, so a turn stopped on one of those is
recorded as an **estimate** — the request and the text already shown, at about
four characters a token. It counts against every limit, because the provider
billed it, and Usage says *Includes n stopped requests estimated by Raiker* so it
is never read as the provider's own figure.

Spend is the providers' own token counts priced with the rates Models shows.
A model with no known price is not counted and is named under the limit, so you
know the limit is not protecting you there; set its price on Models to include
it. A routine can also carry its own per-run limit on **Will it run?**.

## One instance, one default

Each connection belongs only to this Raiker instance: a key entered here is
encrypted in this instance's vault and is not shared with another install, a
another workspace, or the terminal client running elsewhere. **One ready
provider is enough to work** — nothing requires you to connect more than one.

**Default model** is what serves any surface that does not choose its own,
including every scheduled run at the moment it begins and every turn a messaging
channel routes in. Chat, Build and Tasks can pick their own; each composer's
model menu then says both — **Default model *X*** and **This work uses *Y*** — with
**Reset to default** beside the second. A surface remembers its own pick across
reloads, and **Reset to default** forgets it, so the surface follows the default
again after a reload too. Choose the default on **My models** with **Use**.

**Every model a connected provider serves is reachable.** Connect once, discover
once, use everywhere: the listing that follows a connection is recorded, so the
catalogue survives a provider that is briefly unreachable rather than vanishing
with the response that carried it.

**Select models…** on a provider card opens that catalogue with a switch against
each. Those switches are the **quick list** — the handful a picker shows at rest,
kept short because scrolling four hundred names is hunting rather than choosing.
They are an ordering, never a gate: a model absent from the quick list is still
selectable, and the picker's search reaches every model your providers have
published.

Three things still remove a model from a picker, and all three are measurements
rather than preferences: a provider you have not connected offers nothing, a
model Raiker has measured as unavailable is not offered until it answers again,
and **disconnecting a provider takes its models with it** — a remembered
catalogue is for an outage, not for an account Raiker may no longer reach.

---

## Fallback sequence

Under **Advanced routing** on **Runtime & routing**, **Model fallback sequence**
orders the backends Raiker tries when the selected one is unavailable. Listing a
hosted provider there grants nothing on its own — each candidate is still gated
by the same policy.
Point it at your local runtimes so a turn never dead-ends when a hosted API is
down.

"Unavailable" is four specific things: no network, a timeout, a host that does
not respond, or a policy denial. Raiker tries the next candidate in your order
for each of them, and with no fallback configured the turn fails closed rather
than silently choosing a backend you did not pick. A turn a fallback answered
says so in its timeline — *Switched to … because … was unavailable* — with the
reason the earlier one gave.

---

## Side-task models

**Runtime & routing → Side-task models** gives two kinds of side work their own
model, each an ordered list of up to three you have set up:

- **Summarising** compacts a long conversation. A cheaper or faster model is
  often the better choice. Raiker tries the list in order and then the turn's own
  model, so a long conversation can always be compacted.
- **Vision** describes an attached image when the model answering cannot see.
  Only models that accept images can be added — for Ollama, that is decided per
  model from Ollama's own list (for example *Gemma 4:31B Cloud*). The
  description reaches the turn as text, marked as a description and as untrusted
  content, and the turn's **Evidence** records which model described it. With no
  vision model the image is not sent, as before.

Choosing a side model grants nothing: every call still goes through the same
gates, connections and keys as a turn.

## Advisor model

Under the same **Advanced routing** disclosure: when you run a local model, it
can consult one advisor — typically a hosted model — through the governed
`consult_advisor` tool. It is the way to keep a small local model as your
default and still reach for a larger one on the questions that need it.

**Picking an advisor grants nothing on its own.** Every consult is gated at call
time by all of:

- the `advisor_model_runtime` capability;
- its decision mode, which is **ask** by default and withholds the consult until
  you allow it;
- the advisor provider's own policy — its hosted gate, your saved connection for
  it, and its API key.

Miss any one and the consult is refused with its own named reason, exactly as
any other governed action is.

The advisor's answer is **always treated as untrusted data**, never as
instructions: it reaches the local model as material to consider, and it cannot
propose an action, widen an approval, or change what the turn is allowed to do.
Neither the question nor the answer enters the audit log — only their lengths
do, so the record shows that a consult happened and how large it was without
keeping either side of it.

## Off-machine provider posture

**Models → Add model** opens with five read-only facts about everything that
would leave this machine: the hosted model gate, the private-network gate, how
many off-machine providers you have connected, how many off-machine profiles
exist, and **Through your proxy** — whether hosted requests go through the
proxy set in Raiker's environment (`HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY`,
minus `NO_PROXY`), and which one. Each off-machine card's posture line ends
**Direct connection** or **Through your proxy (host:port)**. It is status, not
a control — endpoints, API keys and proxy passwords are never displayed here.

The two gates report **what they answer**, not what is stored against them.
Connecting a provider is itself consent to use it, so a gate nobody has touched
reads **On (by connection)** once any provider is connected; before that it
reads **Off until connected**, which is both the verdict and the thing that
changes it. A gate you deliberately turned off in **Permissions** reads **Off**
whatever is connected — an explicit decision outranks a connection, always.

A hosted provider fails closed unless **all** of the following are present: a
gate you have not turned off, your saved connection for it, and the provider
key. There is no silent fallback to a hosted
model: if the model you chose cannot run, the turn fails with the reason rather
than quietly reaching for one that costs money and leaves the machine.

---

## If it still refuses

Every refusal is a named reason code with a specific fix. The sign-in dialog now
states the fix and links to the control that applies it. The full table is in
[Troubleshooting](troubleshooting.md).
