# Raiker live manual test plan

**This document is the procedure. It never says what happened.** Every step
states what to do and what **must** be true; a step that reads "on 2026-08-08
this returned Ready" has stopped being a test and become a memory. The record of
what actually happened on a given day is
[`LIVE_TEST_ROUNDS.md`](LIVE_TEST_ROUNDS.md).

Run it against a **running** Raiker in a real browser. Nothing here is proven by
reading code.

**Never commit an API key.** Keys go into the Connect dialog or the server
process environment, for the duration of the round only.

---

## 0. The two tiers

Pick one before you start, and record which one you ran.

| Tier | When | Time | Obligation |
|---|---|---|---|
| **Smoke** | After any change; before asking anyone to look at a branch | ~30 min | Every step marked **[S]**. One provider is enough |
| **Full sweep** | Before a release, and at least once a month | Several hours | **Every step in this document**, plus every manually re-verifiable item in [§20](#20-regression--what-a-run-re-proves). At least two providers, one local and one hosted |

A round that ran Smoke says so. **A Smoke round is not evidence that the product
works** — it is evidence that it is not obviously broken. Only a Full sweep
closes the coverage question, and the last one is named at the top of
[`LIVE_TEST_ROUNDS.md`](LIVE_TEST_ROUNDS.md).

### How to read a step

- **[S]** — in the Smoke tier as well as the Full sweep.
- **MUST** — a failure here is a defect. File it in
  [`TO_BE_FIXED.md`](TO_BE_FIXED.md) with a screenshot under
  [`screenshots/not-working/`](screenshots/not-working).
- **Automated** — an e2e spec already asserts this. Named so you know it is
  covered, and so you do not spend a manual round re-proving it. Do not skip it
  in a Full sweep if the step also has a manual half.
- A step never assumes the one before it left state behind unless it says so.

### The rule that keeps this document honest

**No step may record an observation.** If you learn something while running it —
a control moved, a label changed, a check now takes longer — the fix is to change
what the step *expects*, not to append what you saw. Observations go in
[`LIVE_TEST_ROUNDS.md`](LIVE_TEST_ROUNDS.md).

---

## 1. Environment setup

```bash
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
npm --prefix apps/web ci
npm --prefix apps/web run build

# Model egress is process configuration by design — it is the last boundary
# before bytes leave the machine and is deliberately NOT editable from a browser
# session. Web egress is different: it needs no variable, and what you control
# there is a blocklist inside the app.
export RAIKER_MODEL_EGRESS_ALLOWLIST='api.anthropic.com,api.openai.com,generativelanguage.googleapis.com,openrouter.ai'

rm -rf /tmp/raiker-manual-test && mkdir -p /tmp/raiker-manual-test
.venv/bin/raiker-web --workspace /tmp/raiker-manual-test --port 8765 --no-browser
```

**A Full sweep starts on an empty workspace.** A round run against an instance
that already has history proves the product works for someone who has used it,
which is not the question a sweep asks. Smoke may reuse a workspace.

Open `http://127.0.0.1:8765` in Chromium. Keep the developer console open for the
whole round: **MUST** end with zero uncaught console errors, and any that appear
belong in the round record with the step that produced them.

Prepare these before you start, so no step stalls waiting for them:

| Fixture | Why |
|---|---|
| One hosted provider key | §3, and every model-backed step |
| A local runtime (Ollama or LM Studio) with one small model pulled | §3.4, and the local half of §4 |
| A small git repository inside the workspace | §6 Build |
| A `.png`, a `.pdf`, a `.docx` and a `.csv` under 5 MB | §5.6 attachments |
| A folder on this machine with three or four text files | §9 Knowledge Map, §8 Projects |

---

## 2. Coverage ledger

**This table is the definition of "everything".** It is derived from
`apps/web/src/lib/nav.ts` — `NAV_GROUPS` for routes, `HUB_TABS` for tabs — so a
route or tab added to the product without a row here is a gap you can see rather
than one you have to remember.

Check the ledger before you start and after you finish. **A row with no section
is untested**, whatever the rest of this document says.

| Route | Tabs | Covered by |
|---|---|---|
| `home` — Workbench | — | [§4.1](#41-workbench-s) |
| `new-chat` — Chat | — | [§5](#5-chat) |
| `build` — Build | — | [§6](#6-build) |
| `search-chat` — Search Chat | — | [§5.8](#58-search-across-every-conversation-s) |
| `tasks` — Tasks | — | [§7](#7-tasks--every-work-type) |
| `projects` — Projects | — | [§8](#8-projects-folders-and-files) |
| `memory` — Memory | — | [§10](#10-memory--every-kind) |
| `brain` — Knowledge Map | — | [§9](#9-knowledge-map) |
| `approvals` — Approvals | — | [§11](#11-approvals) |
| `capabilities` — Permissions | — | [§12](#12-permissions) |
| `models` — Models | `local`, `hosted`, `huggingface`, `activity`, `routing`, `pricing`, `posture` | [§3](#3-models--all-seven-tabs) |
| `extensions` — Extensions | `connectors`, `mcp`, `skills`, `hooks`, `plugins`, `channels` | [§13](#13-extensions--all-six-tabs) |
| `observe` — Observability | `overview`, `sessions`, `activity`, `checkpoints`, `diagnostics`, `work`, `notifications` | [§14](#14-observability--all-seven-tabs) |
| `guide` — Guide | — | [§15](#15-guide) |
| `settings` — Settings | `general`, `notification`, `personalisation`, `security`, `privacy`, `account`, `web-access`, `git-credential`, `runtime` | [§16](#16-settings--all-nine-sections) |

**15 routes, 29 tabs.** Global chrome that belongs to no route — the sidebar, the
top bar, the Host control, notifications, the shortcut sheet — is
[§17](#17-global-chrome).

### Deep links and aliases

`ROUTE_ALIASES` in `nav.ts` keeps eight pre-hub URLs working:
`#/connections`, `#/mcp`, `#/activity`, `#/checkpoints`, `#/diagnostics`,
`#/work`, `#/notifications`, `#/sessions`.

**[S]** Paste each into the address bar. Each **MUST** open its hub with the
matching tab already selected, never the hub's first tab and never the Workbench.
*Automated: `apps/web/src/lib/nav.test.ts`.*

---
## 3. Models — all seven tabs

Nothing else in this plan works until a model is ready, so this comes first.

### 3.1 First run [S]

1. **[S]** A fresh workspace **MUST** open owner bootstrap. Create the owner.
2. **[S]** Setup **MUST** open on its own. Walk all five stages — account,
   model, privacy posture, backup, finish — and confirm the progress control
   (`aria-label="Setup progress"`) names the stage you are on.
3. **[S]** Choose **Local-first** on one run and **Balanced** on another; the
   posture you pick **MUST** be the one Settings → Privacy shows afterwards.
4. **[S]** Skip setup. Every model-backed primary action — Workbench, Chat,
   Build, Tasks — **MUST** be disabled and link to Models. Typed draft text
   **MUST** survive the trip to Models and back.
5. Sign out and back in. The lock screen **MUST** name the instance, and a wrong
   password **MUST** fail without saying which half was wrong.

### 3.2 `hosted` tab [S]

1. **[S]** **Connect** on a provider, paste a key, save. The card **MUST** read
   Connected and the key **MUST NOT** be rendered back into the DOM — check the
   element inspector, not just the screen.
2. **[S]** The catalogue **MUST** be the provider's live list, not a bundled one.
3. **[S]** **Test** **MUST** run an exact-model readiness check, not a catalogue
   listing. A ready model reports Ready; a model the account cannot execute
   reports *why* — credit, quota, authentication — and links the remedy.
4. Open **Available models** and select every model in the list in turn. Each
   **MUST** either become ready or state its own reason. None may fail silently.
5. **Disconnect**. The vault credential **MUST** be removed and the card **MUST**
   return to its unconfigured state.
6. Connect a provider that is not running (a wrong port on a local endpoint).
   The failure **MUST** name the endpoint and **MUST NOT** surface a raw
   provider reason code as an assistant reply.

### 3.3 `local` tab

1. Add an absolute model folder under **Local library**
   (`aria-label="Absolute model folder"`) and rescan. A discovered GGUF **MUST**
   show its name, architecture, quantization and a Deploy action.
2. Deploy it. **Activity** (§3.6) **MUST** show the operation reaching a terminal
   state.
3. Pull an Ollama model from the provider matrix
   (`aria-label="Ollama model to pull"`). The pull **MUST** be cancellable and
   **MUST** resume rather than restart after a cancel.
4. Serve a GGUF through managed llama.cpp
   (`aria-label="GGUF model to serve"`). Confirm the served name and port.

### 3.4 `huggingface` tab

1. Search (`aria-label="Search Hugging Face models"`). Results **MUST** open on
   the most-downloaded GGUF repositories before you type anything.
2. Open one. Before any download is confirmed, the dialog **MUST** show the
   immutable revision, the licence, gated status, size and format.
3. Download a small permissive GGUF into an approved root, then deploy it.
4. Cancel a download mid-flight. The partial file **MUST** be removed only after
   a separate confirmation, and only inside an approved root.

### 3.5 `routing` tab

1. Add a fallback backend (`aria-label="Add a fallback backend"`). Reorder with
   **Move up** / **Move down**; **Remove** one.
2. The chain **MUST** be judged as one — readiness is a property of the chain,
   not of its first entry.
3. Set the advisor model (`aria-label="Advisor model profile"`) and run **Check
   advisor**. It **MUST** carry its own readiness under its own exact key.
4. **MUST**: with only a local provider configured, no hosted provider is ever
   used as a silent fallback.

### 3.6 `activity`, `pricing`, `posture` tabs

1. **Activity** **MUST** list every model operation with a terminal state.
2. **Pricing** **MUST** name the source of each figure, and an unpriced model
   **MUST** report its cost as unknown rather than as zero. Run **Provider
   synchronisation** where the provider supports it.
3. **Posture** **MUST** state the off-machine position for each configured
   provider.
4. Set a **Global model** and confirm it is what a new Chat opens with.

### 3.7 Per-surface defaults

Set a different model on Chat, Build, Tasks and Schedule. Each surface **MUST**
remember its own; changing one **MUST NOT** change another.

---

## 4. Navigation and the Workbench

### 4.1 Workbench [S]

1. **[S]** `#/` **MUST** open the Workbench, and it **MUST** be a board over work
   rather than a second composer.
2. **[S]** **Start work** opens the surface it names. **Refresh Workbench**
   re-reads. **Needs your attention** lists only items that really need one.
3. With a parked approval, a running task and a scheduled agent in flight, each
   **MUST** appear in its own region, and each **MUST** link to the surface that
   resolves it.

### 4.2 Every route [S]

**[S]** Visit all fifteen routes in the [ledger](#2-coverage-ledger) from the
sidebar. Each **MUST** render its own content — not an empty state, not a
spinner that never settles, not another route's panel. Then visit all
twenty-nine tabs.

### 4.3 Responsive [S]

Resize to **375 px**, **768 px**, **1024 px** and **1440 px**. At each width:

- **[S]** Below 640 px: a bottom bar plus drawer. To 1023 px: a menu trigger plus
  drawer. At 1024 px and above: the full sidebar.
- **MUST**: the selected tab is on the screen it was selected on — no tab strip
  scrolls its own selection out of view.
- **MUST**: no composer floats mid-page; both stay anchored to the bottom.
- **MUST**: the page body never scrolls horizontally.

---

## 5. Chat

### 5.1 Every composer control [S]

Click each, and confirm each does what its label says:

| Control | `aria-label` | Must |
|---|---|---|
| Attach | `Add attachment` | Opens the panel with **Upload image**, **Upload document** and **Attachment path** |
| Model | `Models` | Lists only *configured* profiles. No free-text model id |
| Effort | `Effort` | Appears only where the model publishes thinking levels, and offers only those |
| Context | `Context window` | Opens a read-only popover. **MUST NOT** compact anything |
| Approval mode | `Approval mode` | Four options — Manually approve, Automatically approve, Skip all approvals, Decline don't ask — each with a detail line |
| Project | `Project for this chat` | Lists projects; assigning supplies bounded context and **MUST NOT** grant filesystem access |
| Background work | `Background work` | Hands the turn to the queue instead of waiting |
| Dictate | `Dictate` | §5.11 |
| Conversation actions | `Conversation actions` | **Export conversation…** and **Print / Save as PDF** |

**[S]** `/` at the start of the prompt **MUST** open a filtered menu, and **every
entry MUST run a control that exists** — there is no "coming soon" row. Chat
carries `/export`, `/schedule`, `/tasks`, `/shortcuts`, `/stop`.
*Automated: `apps/web/src/lib/composerCommands.test.ts`.*

`/shortcuts` **MUST** list only bindings the handlers implement.

### 5.2 A real streamed turn [S]

1. **[S]** Send a prompt. The answer **MUST** stream, and Markdown **MUST** be
   rendered — not shown as raw text.
2. **[S]** Every tool call **MUST** get one row above the answer, in the order
   the model asked, with an icon, the tool in plain words and what it acted on.
3. **MUST**: a running call says so; one waiting on a decision says so beside the
   card that resolves it; a refused one says why and links the page that would
   let it through.
4. **MUST**: a URL is narrowed to its host and a command to its program — a row
   never says more than the audit log does.
5. Turn **Thinking** on where the model supports it. Reasoning **MUST** fill a
   collapsed block that closes when the answer starts, and a turn that produced
   none **MUST** show no block at all.

### 5.3 Multi-turn conversation [S]

**[S]** Send at least **six** messages in one conversation, referring back to
earlier ones. The model **MUST** have the earlier context. Reload the page
mid-conversation: the transcript **MUST** rehydrate.

Open a second conversation and confirm **MUST**: nothing from the first leaks
into it.

### 5.4 Message actions

On your own message: **Copy this message**, **Edit this message and send it
again**, **Send this message again**, **Branch a second conversation from this
point**.

- **MUST**: an edit **adds a new turn**. The original stays. The transcript is a
  record.
- **MUST**: a branch opens a *second* conversation, the first keeps every turn it
  had, and the branch shows a lineage band naming its source.
- **MUST**: branching a turn with no checkpoint is refused with the reason
  stated, not offered and then failed.
- Per-code-block copy **MUST** be present on code in the answer.

### 5.5 Stop and steer

Start a long turn. **Stop** **MUST** end it at a safe boundary and say so.
**Steer** **MUST** put your words into the running turn as a user message.

### 5.6 Attachments — add and read

1. **[S]** Upload an image. It **MUST** appear as a chip before sending, and the
   turn **MUST** be able to describe it (vision-capable model).
2. Upload a `.pdf`, a `.docx` and a `.csv`. Text **MUST** be extracted
   server-side, and the model **MUST** be able to quote from each.
3. Drag and drop a file onto the composer. Same result as the button.
4. Attach by workspace path (`aria-label="Attachment path"`).
5. Open the file inspector on an attachment. **Close file preview** **MUST**
   return you to the transcript with the draft intact.
6. In the image viewport: **Zoom in**, **Zoom out**, **Fit to pane**, **Reset the
   view** — and their `F`, `+`, `-`, `0` keys.
7. **MUST**: an attachment renders outside the message bubble, not inside it.

### 5.7 Generated documents

Ask for a Markdown file, then a DOCX, an XLSX and a PDF. Each **MUST** appear
under **Generated documents**, **MUST** be previewable, and **MUST** download.

### 5.8 Search across every conversation [S]

1. **[S]** `#/search-chat`. Search a phrase from an earlier conversation. The
   result **MUST** show the exchange it matched, not just the title.
2. **MUST**: results rank by relevance, not recency — a matching exchange from
   the oldest conversation outranks a weak match in the newest.
3. Recent-chat list: per-row **delete** and **move to project** **MUST** work,
   and a deleted conversation **MUST** take its dependents with it.

### 5.9 Recall and citations

1. Ask about something discussed in another conversation. The turn **MUST** be
   able to reach it, and the answer **MUST** cite the conversation, timestamp
   and turn id.
2. **Sources this answer used** **MUST** list the sources, and opening one
   **MUST** land on the cited passage.
3. Turn on **Incognito session**. Recall **MUST** be off for that session.
4. **MUST**: a citation whose file has been deleted is reported as missing, not
   dropped.

### 5.10 Context and compaction

1. **Context window** **MUST** show used, capacity, the source of the capacity,
   and the cost with each figure's source named. It **MUST NOT** show `NaN`.
2. Drive one conversation past **90%** of a known capacity. Older completed
   exchanges **MUST** compact automatically, and the transcript **MUST** stay
   unchanged.

### 5.11 Voice

1. **Dictate** **MUST** write into the ordinary editable draft.
2. **Done dictating** **MUST NOT** send. **Cancel dictation** **MUST** restore
   the exact draft from before dictation began.
3. Navigate away while listening. The microphone **MUST** stop, and the words
   already dictated **MUST** be kept.
4. **Read aloud** on a completed reply **MUST** be manual, never automatic, and
   **MUST** exclude code bodies and raw URLs.
5. **MUST**: only Send creates a turn.

### 5.12 Export

Export a conversation to **HTML**, **Markdown** and **PDF**, and use **Print /
Save as PDF**. Each **MUST** contain the transcript and **MUST NOT** contain
retained reasoning.

---

## 6. Build

### 6.1 Repositories

1. **Repositories** (`aria-label="Repositories"`) → add a local folder inside the
   workspace. A folder outside it **MUST** be refused.
2. Add a GitHub `owner/repo` coordinate. It **MUST** be recorded with **no**
   network call.
3. Remove a repository. The folder and the remote **MUST** be untouched.

### 6.2 The three modes [S]

1. **[S]** Build **MUST** open in **Auto** — the mode that sends no override.
2. **[S]** `Shift+Tab` **MUST** cycle Plan → Edit → Auto without leaving the
   prompt. The mode menu **MUST** offer the same three with a detail line each.
3. **Plan**: ask for a file write. It **MUST** be refused by the runtime with
   `denied_by_turn_posture` — not talked out of by the model.
4. **Edit**: the same request **MUST** become a decision you accept or reject.
5. **Auto**: the composer **MUST** state what your standing permissions actually
   allow rather than implying unprompted execution.
6. **MUST**: none of the three writes to your standing capability modes. Check
   Permissions before and after.

### 6.3 Build a small proof of concept [S]

This is the end-to-end coding exercise, and it is the point of the surface.

1. **[S]** Ask Build to create a small working program — say a three-file
   Python CLI with a test — in the connected repository.
2. **[S]** Approve the patch. It **MUST** apply as **one** change set, and the
   files **MUST** exist on disk afterwards.
3. Ask it to run the test through the governed terminal. Approve. The command
   **MUST** run inside the workspace under a timeout, and the output **MUST**
   appear.
4. Ask for a change that fails one hunk. **MUST**: the whole proposal fails —
   there is no partial application.
5. Ask it to create a file that already exists, and to edit one that does not.
   Both **MUST** be refused before anything is written.
6. **MUST**: nothing writes into `.raiker/` or `.git/`, by any path.

### 6.4 Code map

1. Turn on **Code map**. Index the repository.
2. `@` in the composer **MUST** complete paths **from the map**, not the working
   tree, and **MUST** return paths only — no symbols, no line numbers, no
   content.
3. With the map unbuilt, `@` **MUST** say `code_map_not_built` and offer the
   control that builds it. With the gate off, `code_map_gate_disabled` and a
   Permissions link. The two **MUST** be different messages.
4. Ask where a symbol is defined, then for its references. A partial scan **MUST**
   report `partial` and name the bound it hit.

### 6.5 Git

1. Ask for a branch and a commit. Approve each. **MUST**: the commit stages
   exactly the paths you reviewed — never `--all`.
2. Store a token in **Settings → Git credential**. Ask for a push.
   - **MUST**: it does nothing until the remote's host is on
     `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`.
   - **MUST**: the credential never appears in a log, an error or the command's
     output.
   - Grant **once**, then **for this session**. Withdraw the session grant and
     confirm the next push asks again.

### 6.6 Execution environment

1. Open the environment badge (`aria-label="Execution environment"`). Select each
   available profile.
2. On **Native OS sandbox**: **Re-measure boundary** **MUST** report six
   observations, each with a control arm, and an unmatched control arm **MUST**
   read `indeterminate` rather than passing.
3. **MUST**: a capability the boundary has not been measured to have is absent
   from the card, not shown disabled.
4. On a container profile: **Reset environment** and **Reset and clear cache**
   **MUST** both be offered, and **MUST** be refused on a profile that rebuilds
   itself around every command.

### 6.7 Background work

1. Start a long command with background execution. **Background work**
   (`aria-label="Background work"`) **MUST** list it.
2. Poll, page the log, and stop it. Reload the browser mid-run: durable output
   **MUST** come back without replaying the command.
3. Schedule a background agent with a **Cadence**. Each cycle **MUST** be one
   governed turn.

### 6.8 The operating protocol

Run the same prompt in Chat and in Build. **MUST**: the Build turn's audit record
names its surface, and the protocol is a working method only — every gate,
decision mode, approval and tool is identical on both.

---

## 7. Tasks — every work type

### 7.1 Create one of each [S]

For each of the four, create it, watch it run, and confirm it appears in the list
with the right shape:

| Type | Control | Must |
|---|---|---|
| **[S]** Task | `Task` | Runs now |
| Schedule once | `Schedule once` | Requires a **Start time**; runs at it |
| Daily routine | `Daily routine` | Requires a **Start time**; re-arms after each cycle |
| Background agent | `Background agent` | Runs asynchronously until complete or stopped |

### 7.2 Every field

- **Task title**, **Instructions** — an empty Instructions **MUST** block
  creation with a named error.
- **Parent work** — create a child task. It **MUST** appear nested.
- **Priority** — low, normal, high. All three.
- **Start time** — appears only for *Schedule once* and *Daily routine*.
- Attachments on a task **MUST** reach the run.
- A per-run model **MUST** be selectable and re-checked at run time.

### 7.3 Lifecycle

1. Stop a running task. It **MUST** stop at a safe boundary and record the
   reason.
2. Let a task hit an approval. It **MUST** read **blocked** with the reason and a
   link to the decision — never *failed*.
3. Resolve the approval. The run **MUST** continue.
4. Remove a task. Remove a routine. Remove a background agent. Each **MUST**
   disappear from the list and stop scheduling.
5. **MUST**: a model-proposed task is parked until you press **Run now**.

### 7.4 Routines

Create a daily routine and let it fire twice. **MUST**: the second cycle is a
fresh governed turn, and a missed slot is skipped rather than owed as a backlog.

---

## 8. Projects, folders and files

1. **[S]** Create a project (`aria-label="New project name"`).
2. Add **Project instructions**. **MUST**: the next turn in that project has
   them, and a turn outside it does not.
3. Set **Project memory setting** to each of *inherit*, *enabled*, *disabled*
   and confirm the behaviour changes.
4. Assign a conversation to the project from the composer, and from the
   recent-chat row. Both **MUST** work.
5. Add files to the project. **MUST**: they reach a turn as bounded context and
   **MUST NOT** grant filesystem access.
6. Switch the **Active project** in the top bar. The Workbench and Chat **MUST**
   scope to it.
7. Delete the project. **MUST**: it says what will happen to its conversations
   before you confirm.

---

## 9. Knowledge Map

1. **[S]** `#/brain` **MUST** render a force-directed graph, not an empty canvas.
2. **Add workspace source** → the picker **MUST** open on **named places** — your
   projects' files, generated files, approved memory, the encrypted database —
   not a file browser.
3. **Folder to grant**: grant a folder from this machine. **MUST**: it is read
   where it is, and **MUST NOT** be copied.
4. **File to copy into Raiker**: add a single file. **MUST**: it asks first,
   because this one copies.
5. **MUST**: the granted folder's files appear as nodes in the graph.
6. Revoke the folder. **MUST**: every source indexed under it is removed with it.
7. **Graph scope** — change it and confirm the graph changes.
8. **Graph settings**, **Fit graph**, **Enter fullscreen**, **Record inspector**
   — each **MUST** work and **Close** **MUST** return you to the graph.
9. **MUST**: a citation whose file is gone is drawn as a hollow node.

---

## 10. Memory — every kind

### 10.1 The gate [S]

**[S]** With `memory_write` off, the Memory page **MUST** say so rather than
promising proposals it cannot produce.

### 10.2 Write, review, forget

1. Turn the gate on. Ask Chat to remember something. **MUST**: you are shown the
   **exact sentence** and decide.
2. Approve. **MUST**: it is really stored, and recall can reach it.
3. Do the same from Build, and from the terminal client. All three **MUST**
   propose.
4. Ask it to remember something that looks like a credential. **MUST**: refused
   *before* you are asked.
5. **Edit memory** and **Edit proposed memory**. **Forget memory** — the record
   **MUST** go.

### 10.3 Every filter and every kind

Exercise each dropdown across its whole option set:

| Control | Options |
|---|---|
| `Memory status` | all, approved, expired |
| `Memory scope` | all, and every scope present |
| `Memory sensitivity` | all, and every sensitivity present |
| `Sort memories` | recently-approved, review-date |
| `Observation kind` | all, skipped, gist, source |
| `Recall backend` | auto, and every embedding space offered |

**MUST**: `Filter memories` narrows the list, and **Memory history** shows what
changed and when.

### 10.4 Observations

**Observations** **MUST** list what the runtime captured, with kind, retention,
expiry, sensitivity and checksum — and a **refused** observation **MUST** be a
row with its reason, so an empty list is distinguishable from a disabled feature.

### 10.5 Recall

1. Ask a question whose answer is in an approved memory, using **the same
   words**. It **MUST** be recalled.
2. Ask the same question **paraphrased**. Record the result honestly — the
   default embedding space is lexical, and this is the measurement that keeps
   [`../KNOWN_LIMITS.md`](../KNOWN_LIMITS.md) true.
3. **MUST**: each hit names the legs that found it, and the reply names the
   embedding space in force.

### 10.6 Export and import

Export memories, then import them into a fresh workspace. **MUST**: the count
matches and nothing is silently dropped.

---

## 11. Approvals

1. **[S]** Raise one approval of each kind you can: a file write, a patch, a
   shell command, a git commit, a push, a memory write, a task row.
2. **[S]** Each detail **MUST** say what will happen **before** you decide, and
   **MUST** distinguish *this will execute* from *this records a decision*.
3. Approve a file write. **MUST**: the file changes, and a checkpoint holds the
   previous contents.
4. Approve a `process` or `network` action. **MUST**: it records the decision and
   **executes nothing** — and said so before you approved.
5. Deny one. **MUST**: the turn continues rather than ending in an error.
6. **Approval status filter** and **Sort approvals** (risk, newest) — both.
7. Resolve an approval in a second browser tab. **MUST**: the first tab's turn
   continues.
8. Reload with an approval parked. **MUST**: it survives.
9. Turn off `approval_execution_relay`. **MUST**: file approvals return to
   record-only, and the surface says which gate did it *before* you decide.

---

## 12. Permissions

1. **[S]** All **67** gates **MUST** be listed, grouped, and searchable.
2. Expand a row. It **MUST** give a description, the current decision mode in
   plain words, and the control that changes it.
3. Set a capability to each of **Ask**, **Allow**, **Auto**, **Deny** and confirm
   the runtime honours each.
4. **Turn on** a higher-risk gate. The step-up **MUST** require a
   `runtime_gate_manager`, a reason, a typed phrase and a threat-model
   acknowledgement — and **MUST** explain that the phrase is not a credential.
5. **Bulk capability actions** — exercise it.
6. **Deferred domains** — finance, medical, CCTV, home security, hardware
   **MUST** offer **no enable path at all**, not a disabled switch.
7. Stop the agent runtime from Settings → Runtime. **MUST**: every surface says
   so, and no new execution starts.

---

## 13. Extensions — all six tabs

### 13.1 `connectors`

Filter by category. Install one. **MUST**: its readiness reads as separate facts
with separate remedies, not one enable switch.

### 13.2 `mcp`

1. Create a server from a template. **MUST**: the command is workspace-relative
   and the interpreter is from the allowlist.
2. **Test**. **MUST**: it connects and lists its tools.
3. **MUST**: with the connector decision mode at `ask`, the tab states that
   connected tools are withheld from every turn, and names the control.
4. Add a **remote** server by URL. Pause, resume, rename, kill it.
5. **MUST**: a tool result reaches the model but its content never enters the
   audit record.

### 13.3 `skills`

1. **[S]** Six built-ins **MUST** install on first visit.
2. Upload a `SKILL.md`, and a `*.skill` bundle. Import one from a verified GitHub
   link. Build one in place.
3. Activate and deactivate one. **MUST**: a deactivated skill is withheld from
   turns.
4. Download one; delete one.
5. **MUST**: a skill grants no capability and opens no gate, and Raiker runs no
   code it ships.

### 13.4 `hooks`

1. **[S]** The tab **MUST** report what the runtime **actually loaded**.
2. Write a `PreToolUse` rule that denies a tool. **MUST**: the tool call is
   denied.
3. Write a rule on an event this build does not dispatch. **MUST**: it reads
   *configured but never fires*.
4. Write a rule that cannot change an outcome. **MUST**: it reads **Observes
   only**, not enforcing.
5. Name a builtin this build does not ship. **MUST**: reported unavailable, not
   counted as a guard.
6. Break the JSON. **MUST**: the file is named with the position the parse
   stopped at, the other sources still load, and **every prompt still works**.
7. **Turn every hook off**. **MUST**: rules stay listed and marked off.
8. **MUST**: nothing a hook returns can allow what the runtime refused.

### 13.5 `plugins`

1. Install a plugin that contributes hook rules, a skill and an MCP server.
2. **MUST**: the permission diff is shown **before** installing, and none of
   `event:hook`, `skill:contribute`, `mcp:server` is auto-approved.
3. **MUST**: the contributed skill arrives **switched off** and is marked *from
   plugin*.
4. **MUST**: the MCP server is an **offer** — nothing is stored as a server until
   you press **Add server**.
5. **MUST**: an offer carrying a credential in its URL is refused.
6. Revoke the plugin. **MUST**: everything it contributed is **deleted**, not
   flagged.
7. **MUST**: the tab states the signature level each plugin earned and what would
   raise it.

### 13.6 `channels`

1. Pair a connector. **MUST**: *linked*, *enabled*, *trusted* and *reachable* are
   **four rows with four remedies**, not one switch.
2. Send an outbound delivery. **MUST**: it is signed when a secret is set, and
   the page says **unsigned** when one is not.
3. Send inbound messages past the 60-per-minute bound. **MUST**: the refusal is a
   recorded event, not a silent drop.
4. **MUST**: an inbound message is recorded and quarantined and **never becomes
   work on its own**.

---

## 14. Observability — all seven tabs

| Tab | Must |
|---|---|
| **[S]** `overview` | Readiness reads true, and every blocker names its remedy |
| `sessions` | Filter by tag, show archived, select all, bulk actions, pin, rename, archive, delete |
| **[S]** `activity` | The audit log carries your conversations **and** the governed steps outside them — connecting a provider, pinning a model. **Refresh events** works |
| **[S]** `activity` → **Export** | The export states its scope before producing anything, downloads a redacted JSONL, and lists it with a readable manifest hash — never `[REDACTED_SECRET]`. **The export itself appears in the log it exported.** Open the file and confirm no `sk-`-shaped string survived |
| **[S]** `checkpoints` | Each checkpoint lists its files and states whether state and files can be restored. **The preflight performs nothing** — confirm it says so, then acknowledge and press **Request this restore**: it must answer *"Nothing has changed yet"* with an approval id, and the file on disk must be unchanged. Approving that approval must really put the file back, and the restore must appear as a new checkpoint |
| `diagnostics` | Every deferred domain is listed as fail-closed. **Refresh diagnostics** works |
| `work` | A running turn and a background run both appear while they are running |
| `notifications` | A notification is raised, read and cleared |

Produce a **Redacted support bundle** and confirm it contains no credential.

**The rewind's trap, which cost a round to find:** a file write approved from the
**Approvals inbox** executes under a different session than the conversation that
proposed it. Approve one *from the inbox* — not inline in Chat — and confirm the
preflight for that conversation's checkpoint reports the file. A preflight that
says **0 to rewrite** after a write you just approved is
[FIXED-275](FIXED_ITEMS.md) regressing, not an empty workspace.

---

## 15. Guide

**[S]** Utilities → **Guide** **MUST** serve all **eight** sections from the
install, deep-link to each, and be reachable from the pages that explain
themselves — Models to *Connecting a model*, Permissions to *Permissions and the
runtime*, Build to *Working in Build*.

---

## 16. Settings — all nine sections

| Section | Exercise |
|---|---|
| **[S]** `general` | **Speech language** across several options |
| `notification` | Every toggle |
| `personalisation` | **Theme** (system → light → dark → system, with `data-theme` following), **Density**, **Font** (sans, system, mono) |
| `security` | Contained subjects listed with their reason and cleared in one press. Grant scope, action type and risk ceiling (low, medium, high) |
| **[S]** `privacy` | Reasoning retention **off** by default; turn it on and confirm a re-opened turn shows the working, and that it stays out of search and export |
| `account` | Display name; password change; recovery |
| `web-access` | Add a domain, a wildcard, an IP, a CIDR range and a `/regex/` to the blocklist. The reachability check **MUST** answer without contacting anything. **MUST**: loopback and private addresses are refused **whatever** the blocklist says, and emptying it opens none of that |
| `git-credential` | Store, use, withdraw |
| `runtime` | Readiness window (1–120 minutes); stop and start the agent runtime; filtered network status |

**MUST**: unsaved changes are announced, and leaving with them pending warns.

---

## 17. Global chrome

- **[S]** Sidebar: primary navigation, **More navigation**, **Recent chats**,
  open and close on mobile.
- **[S]** Top bar: **Active project**, **Notification panel**, **Host control**.
- **Host control**: state, what a quit would interrupt, Pause, Restart, Quit, and
  **Install and updates**. **MUST**: opening it makes **no outbound request**.
- **Keyboard shortcuts** sheet opens and closes.
- **MUST**: zero uncaught console errors for the whole round.

---
## 18. What this plan does not cover

Stated so a green round is not read as more than it is.

| Not covered | Why, and what does cover it |
|---|---|
| The terminal client (`raiker`) | This is a browser plan. `tests/test_cli_*.py` and the command surface in [`../RAIKER_TOOL_AND_PLUGIN_CATALOG.md`](../RAIKER_TOOL_AND_PLUGIN_CATALOG.md) |
| The desktop payload, tray and installer | Needs a built release. [`../DESKTOP_DISTRIBUTION_DESIGN.md`](../DESKTOP_DISTRIBUTION_DESIGN.md) |
| Windows-only execution paths | PTY and restart reattachment are POSIX-only by build. [`../KNOWN_LIMITS.md`](../KNOWN_LIMITS.md) |
| Anything needing a container daemon | Filtered egress and credential delivery stay unproven without one — BUG-194 |
| Multi-user and hosted operation | Not built |

---

## 19. Model backends

Exercising the web app against **each** model backend in turn — rather than one —
is its own procedure, because the matrix is per provider rather than per screen:
[`../WEB_APP_LIVE_TEST.md`](../WEB_APP_LIVE_TEST.md). A Full sweep **MUST** run
at least two backends, one local and one hosted; the matrix says what to check
for the rest.

---

## 20. Regression — what a run re-proves

**The obligation.** A Full sweep re-verifies every closed item that is manually
re-verifiable. This section is how you know which those are, and it is the answer
to *"if I run §1–§17, what have I re-verified?"*.

[`FIXED_ITEMS.md`](FIXED_ITEMS.md) holds **258** closed entries. Most are
re-verified by a step that describes the **behaviour** rather than quoting the
defect number — which is why the plan used to look far thinner than it is. The
map below makes that explicit.

**Keeping it true is part of closing a defect.** When you add a `FIXED-*` entry,
add it to one of the three tables below in the same change: covered by a step,
covered by automation, or needing a new step. An entry in none of them is an
untested fix, and that is the state this section exists to prevent.

### 20.1 Already exercised by an existing section

| Section | Closed items it re-verifies |
|---|---|
| §2 First run and the lock screen | first-run bootstrap and guided setup, the lock-screen heading, the first-run model sheet, the "Workbench"-titled first screen |
| §4 Connect a hosted model | credential persistence across restart, provider test attribution, readiness against the fallback chain, deep-linkable Models tabs, billing exhaustion reported as itself, throttled reads, in-app credential removal, the model-profile copies staying in step |
| §5 Chat | transcript export in three formats and print, generated DOCX/XLSX/PDF/Markdown artifacts, the file preview and download surfaces, code-block controls, attachment presentation outside the bubble, source citations and their coordinates, multi-call answer separation, one transcript implementation, deleting a conversation and its dependents, automatic 90% compaction |
| §6 Permissions | the step-up dialog's confirmation-token explanation, capability gate states, the composer permission control |
| §7 Approvals | approval resolution in another tab continuing Chat, a parked approval surviving reload, atomic multi-file patch approval, refused proposals not raised as decisions, withheld-call disclosure |
| §8 Tasks | scheduled work resuming after approval, an approved run continuing immediately, task creation not implying execution, schedule attachments |
| §9 Build | patch application forms, repository sub-folder resolution, the code map and its cold start, plans and delegated subagents, repository state after a Permissions visit, stopping and correcting a running turn |
| §10 Extensions | MCP server usability disclosure, plugin signature levels, skills |
| §13 Observability | the audit log showing recorded events, its turn-identity column, machine-identity presentation, containment entries |
| §14 Settings | preferences versus governed work, settings chosen while loading, runtime configuration |
| §16 Projects and adaptive navigation | the responsive breakpoints, Workbench activity awareness |

### 20.2 Automated-only — a manual step would add nothing

These closed items are properties of the build, the test runtime, or a platform
probe. They are verified by CI on every push and cannot be observed by clicking:
CI runtime and quality gates, web development dependency advisories, Python test
dependency warnings, Playwright browser launch, jsdom navigation noise, offline
gateway determinism, `compileall` and shipped-skill checks, Windows process and
memory-locking probes, Linux CI store memory-locking, release artifact pinning,
SQLCipher connection caching and key derivation, concurrent event-writer
integrity, and project-export ordering within one second.

**If one of these regresses, CI fails — do not add a manual step for it.**

### 20.3 Steps added because nothing covered them

Run these after §16, in this order.

| # | Step | Expected |
|---|---|---|
| 22.1 | Open **Knowledge Map**, add a source from each named place the picker offers, then reload | The picker opens on named places, not a file browser; the count pill and the empty state agree; a granted folder is read where it is and adding a single file asks first; sources persist |
| 22.2 | Switch the OS to dark while Knowledge Map is open | The graph follows the shared theme; the simulation does not rebuild on every tick (no visible jitter) |
| 22.3 | Open a generated image in the file inspector | Zoom, pan and rotate are available and keyboard-reachable |
| 22.4 | Open **Memory** with the store off, then on | The page states which posture you are in rather than promising proposals a disabled gate cannot produce; the filter row, search box and sort control are one visual family |
| 22.5 | Export a project, then re-import it into a fresh workspace | Counts, checksums, and event order match; the export carries its citation ledger |
| 22.6 | Trigger a backup from Settings and restore it into an isolated workspace | The manifest records key ID, retention and restore verification; restored memory and audit rows match the source |
| 22.7 | Open **Host → Install & updates** | The build is named honestly (signed release, unsigned build, or source checkout); opening it makes no outbound request |
| 22.8 | Run `raiker-app service install`, `status`, `uninstall` | Each reports what it did using the platform's own service manager |
| 22.9 | With the desktop payload, check the system tray | The tray icon is the shipped Raiker mark, not a drawn placeholder; Open, Pause/Resume, Restart and Quit act through the governed host routes *(FIXED-192)* |
| 22.10 | Compare a `<select>`, a text input and a button on Memory, Settings → General, Models and Projects | One height, border, radius and focus ring across all four; every dropdown carries the same chevron; repeat in dark and in Compact/Spacious density *(FIXED-193)* |
| 22.11 | Open Models → Activity while a pull or download is running | Background state refreshes without a manual reload; a managed llama.cpp process does not outlive a graceful quit |
| 22.12 | Read the README's "Known limits" and the user guide's, against the app | Every line describes current behaviour; nothing shipped is described as missing |

**Result 2026-08-11:** 22.4, 22.9 and 22.10 were run this round and passed —
`r0811b-15-memory-filters.png`, `r0811b-16-settings-dropdowns.png`,
`r0811b-17-settings-dropdowns-dark.png`, and `tests/test_tray_icon.py` for the
tray in a headless environment where no system tray exists. 22.1–22.3, 22.5–22.8,
22.11 and 22.12 are written for the next full round.

---

### 20.4 Items closed since this map was last rebuilt

The map above was built on 2026-08-11 against 189 closed entries. Sixty-nine have
closed since — FIXED-190 through FIXED-269 — covering deep-path-safe I/O, the
memory entity graph, the native sandbox, background execution and the POSIX
terminal, restart reattachment, persistent environments, governed voice, the
Build modes and operating protocol, the hooks surface and its lifecycle events,
plugin contributions, channels, and the fourth approval mode.

**Every one of them has a step in §3–§17 of this plan**, because those sections
were written against the current product rather than grown from the old ones.
What is *not* yet done is the per-entry attribution: mapping each of the
sixty-nine to the step that proves it, in the shape of §20.1. That is the next
piece of work on this document, and until it is finished a Full sweep should
treat §3–§17 as the obligation and this note as the honest caveat.

---

## 21. Recording a round

Do not write results here. Add a section to
[`LIVE_TEST_ROUNDS.md`](LIVE_TEST_ROUNDS.md), newest first, with the date, the
tier you ran, the build, the providers, what it proved and what it found — then
put screenshots under [`screenshots/working/`](screenshots/working) with a fresh
prefix and add that prefix to [`screenshots/README.md`](screenshots/README.md).

Defects go to [`TO_BE_FIXED.md`](TO_BE_FIXED.md) with a reproduction and a
screenshot under [`screenshots/not-working/`](screenshots/not-working).

**If a step here was wrong, fix the step.** That is the one edit this document
wants from a round — not a note about what you saw.
