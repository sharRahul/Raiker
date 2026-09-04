# Known limits

**Canonical.** This is the one place that answers *what can this build not do*.
`README.md` links here rather than repeating it, and it is the honest half of
[`REFERENCE_PLATFORM_COMPATIBILITY.md`](REFERENCE_PLATFORM_COMPATIBILITY.md):
that document compares Raiker with other products, this one states what Raiker
itself falls short of, whether or not anyone else does it.

Raiker's documentation does not run ahead of its code. Every item below was
measured on the shipped build as of **2026-08-23**, after a full reconciliation
of every document against the source.

Two kinds of item live here and are kept apart:

| Section | What it holds |
|---|---|
| [Boundaries Raiker chose](#boundaries-raiker-chose) | Deliberate limits — the reason is a design decision, not a backlog item |
| [Where Raiker is behind](#where-raiker-is-behind-the-general-standard-for-agent-products) | Places it is simply behind the general standard, stated where they stop being theoretical |

Where an item is tracked as work rather than a boundary, it is written up with a
reproduction and a proposed fix in [`plans/TO_BE_FIXED.md`](../plans/TO_BE_FIXED.md);
what it would take to close it, and whether closing it is worth doing, is in
[`REFERENCE_PLATFORM_COMPATIBILITY.md` §5](REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog).

---


## Boundaries Raiker chose

These are deliberate. Each says what the product will not do and why the
alternative would be worse.

- **Voice is governed and turn-based, not full duplex.** Chat and Build support
  editable dictation and manual response playback. Continuous listening,
  speaking, interruption and hands-free task control remain future work; spoken
  consequential controls will not ship without visible confirmation and the
  same policy/audit route as typed controls.

- **Hooks cover part of the reference lifecycle; plugins are two kinds short;
  channels stop below routing.** Of the three extension surfaces Claude Code
  ships:

  **Hooks** are complete against *Raiker's own* event list and partly covered
  against the reference. All twenty events Raiker's format accepts are emitted,
  `PreToolUse`, `PreCompact` and `ConfigChange` decisions are honoured, and
  `builtin`, `command` and bounded tool-free `prompt` handlers execute with
  explicit limits; command programs remain resolved
  inside the workspace. **Turn every hook off** on the Hooks tab stops all of them
  at once and is your setting rather than a fourth config file, so a
  `config/hooks.json` that arrived with a repository cannot re-enable itself. Of
  the five handler types in the reference format, `command` and `prompt` are built
  and three are not: `http`, `mcp_tool` and `agent` need network, broker and
  subagent surfaces that are still gated. Claude Code
  [documents all five](https://code.claude.com/docs/en/hooks), so this is a real
  gap rather than a gap against Raiker's own document. (Raiker's second handler
  type, `builtin`, is its own in-process code and is not one of the five.)

  **Plugins** contribute three of the four kinds the Plugins tab names: hook
  rules, skills, and MCP-server *offers*. A plugin is validated, supply-chain
  checked, signature-levelled and recorded first, and each kind needs its own
  declared permission — `event:hook`, `skill:contribute`, `mcp:server` — none of
  which is auto-approved, so you read it in the permission diff before installing.
  **Panels** are the one kind still unavailable: there is no route, permission or
  accessibility contract for a page a plugin drew — and that is a gap against
  Raiker's own `PLUGIN_SYSTEM_SPEC.md`, not against a reference platform, because
  [no compared platform ships plugin UI panels](https://code.claude.com/docs/en/plugins-reference).
  **LSP servers** are named in the manifest schema and have no surface at all to
  contribute to.

  Claude Code plugins additionally contribute subagents, background monitors,
  `bin/` executables on the Bash tool's `PATH`, themes and output styles. Raiker
  contributes none of those, and the last three
  [it will not](REFERENCE_PLATFORM_COMPATIBILITY.md#4-deliberately-refused):
  a plugin-authored binary on a command's `PATH` is plugin code execution with an
  extra step, and a monitor is a long-running command whose output enters the
  turn. No plugin code executes, in the runtime or in your browser.

  **Channels** deliver, and you can now reach that. A channel message is
  **untrusted content with a named sender who is not you** — never a prompt, never
  able to raise a turn's authority, trust from the pairing record rather than from
  the message. Outbound delivery runs through a capability gate and an egress
  allowlist; inbound is recorded, quarantined and its instructions inert. All of
  it existed and was unreachable until the tab gained pairing, so *linked*,
  *enabled*, *trusted* and *reachable* are now four facts shown as four things.
  Each condition is its own row with its own remedy — the capability, the egress
  allowlist, whether deliveries are signed, the inbound secret, and the inbound
  budget of 60 messages per sender per minute. Routing is owner-stored and
  defaults to record-only; side questions have no tools, active turns require an
  exact owner/target binding, and channel approval responses are separately off,
  exact and single-use. Critical and connector-write approvals remain local.

  Remaining channel-adjacent limits are tracked in
  [`plans/TO_BE_FIXED.md`](../plans/TO_BE_FIXED.md) → BUG-226 (the four hook handler types this build refuses),
  BUG-227 (no LSP surface), BUG-228 (plugin panels) and BUG-229 (a live-spec
  sign-in that only works on an empty workspace).

- **A governed command now runs inside a real OS boundary, and that boundary is
  measured rather than described.** Selecting **Native OS sandbox** runs each
  command in its own Windows AppContainer holding no network capability, with
  the workspace reachable through a single capability grant, `.raiker` denied,
  `.git` read-only, and a Job Object that takes the whole process tree; Linux
  uses bubblewrap and macOS Seatbelt. What the host actually enforces is not
  taken on trust: a probe builds the real boundary over your real workspace and
  runs a child inside it that attempts six things — each one also attempted
  *outside* the boundary as a control. Only "worked outside, refused inside"
  counts. If the control arm fails, the result is **not proven**, and nothing
  turns green on it. All six, and the probe's own outbound destination, are on
  the environment card with a **Re-measure boundary** button.
- **That sandbox is foreground-only, and the card says so.** Inside the native
  sandbox, PTY and raw input, background execution, persistent sessions,
  filtered domain egress, credential quarantine, SSH and Daytona are **not
  built** — its capability set comes from the host probe, and none of them has
  been measured inside an AppContainer. They are absent from the interface
  rather than shown disabled, because a disabled control implies it is one
  setting away. Each has its reason recorded in [`plans/TO_BE_FIXED.md`](../plans/TO_BE_FIXED.md) →
  BUG-194. `local_native` remains explicit host access with reduced isolation
  and is still the default selection; **there**, background execution, a POSIX
  terminal and restart reattachment are built, and each environment card lists
  the capabilities that boundary really has. Browser reload restores durable
  output. A Raiker restart now reattaches to a background run whose supervisor
  still answers — by authenticating to it, never by pid — and a run it cannot
  prove is still its own is marked `lost` rather than inventing success.
- **A container boundary persists for a session, and can be reset.** The
  container a session's commands run in is created once and reused, so what one
  command installs the next one can use, and **Reset environment** / **Reset and
  clear cache** put it back to a known state. The native sandbox still creates
  and deletes a profile around every command, deliberately: its container SID is
  a pure function of its name, so a predictable name is a hole.
- **What a turn thought is retained only when the owner chooses.** Reasoning is
  shown live; Settings → Privacy decides whether it is kept. A reopened turn
  states when working was not retained, while retained working remains excluded
  from search and export. Tool-call evidence remains permanent in
  **Observability → Audit log**.
- **A batch of tool calls runs in parallel only when nothing in it needs a
  decision.** Every validated read-only call in a batch is executed
  concurrently; the moment one call in the same batch requires approval, the
  whole batch is walked serially and pauses at that call. Nothing behind the
  pause is lost — the remainder is parked with the turn and re-governed one
  decision at a time when you resume — but a batch containing three edits is
  three decisions, not one.
- **Build patching is strict about which code you named, not about how you
  typed it.** One unified diff may cover several files, including creates and
  deletes, and it is applied as a single approval and a single reversible change
  set. Matching tries the exact text first; when that finds nothing, the same
  search runs again ignoring **trailing whitespace and indentation style**, so a
  quote that used spaces where the file uses a tab still names the right code —
  and the file keeps its own indentation rather than adopting the quote's. What
  does **not** relax is uniqueness: an edit still requires exactly one match and
  a relaxed search that hits two places is refused, so the tolerance can never
  land an edit somewhere it was not meant to. Interior spacing is text, not
  formatting — `a + b` and `a+b` remain a mismatch. A section that edits or
  deletes must name a text file that already exists inside the workspace and one
  that creates must name a path that does not, and a patch naming the same file
  twice is rejected before anything is written. There is still no partial
  application — one bad hunk fails the whole proposal.
- **A push needs its own switch, its own allowlist, and a credential you lend
  rather than leave lying about.** An approved `git_commit` records the change
  set you reviewed, and an approved `git_push` really publishes the branch — but
  publishing is egress carrying repository content off the machine, so it answers
  to **Git push** (`git_push_execution`) rather than to Git writes, and it does
  nothing until the remote's host is on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`. The
  credential is stored encrypted from **Settings → Git credential** and lent to
  one command at a time under a grant you make — **once**, or **for this
  session** — which carries its own expiry and can be withdrawn in a press. It is
  passed in the command's own environment rather than on a command line, and
  removed from every log, error and captured output for as long as the loan
  lasts. `RAIKER_GITHUB_TOKEN` in the host environment still works for an
  install configured that way, and the page says which of the two you are on.
  Only HTTPS GitHub remotes are pushable, because that is the credential Raiker
  holds; it never forces and never deletes a branch.
- **Web reads are on, and what they may not reach is yours to say.** `web_fetch`
  and `web_search` work on a fresh install: there is no list to fill in first,
  and `web_search` uses a keyless endpoint until you point
  `RAIKER_WEB_SEARCH_ENDPOINT` at your own. What you control is the **blocklist**
  — **Settings → Web access**, or `RAIKER_WEB_EGRESS_BLACKLIST` — which takes a
  domain (covering its subdomains), a wildcard, an IP address, a CIDR range, or a
  `/regex/`, and can be tested against a host without contacting it. What you do
  **not** control, and cannot switch off, is the address guard: https only, no
  credential in the URL, and every address a name resolves to must be public, so
  a fetch can never reach your loopback interface, your home network, or a cloud
  metadata service — including through a name that resolves to one, an
  IPv4-mapped IPv6 address, or a redirect. The connection is pinned to an address
  that already passed, so the destination cannot change between the check and the
  request. Emptying the blocklist opens none of that.
- **A fetched page reaches the model as text, not as markup or instruction.**
  Scripts, styles and comments are dropped; elements a visitor could never see —
  `hidden`, `display:none`, zero-size, off-screen, `aria-hidden` — are removed and
  counted, because text nobody can read is the usual carrier for an instruction
  meant only for a model; zero-width and bidirectional characters are stripped;
  and a line shaped like a conversation role marker is defanged so page text
  cannot open a turn. What was removed is reported alongside the page rather than
  silently swallowed. None of this is a filter that decides whether content is
  safe — the thing that stops a hijack is that fetched text never carries
  instruction authority — but an injection attempt arrives visible and inert.
- **A rewind is a request, never a button.** Restoring to a checkpoint raises a
  governed approval and performs nothing until you approve it — from
  **Observability → Checkpoints**, or with `/checkpoints restore <id> --confirm`.
  That is deliberate: a restore is a workspace mutation like any other, and the
  executor captures its own pre-image first, so the restore is itself reversible.
  A restore that would overwrite work last changed by a different principal is
  classified critical and takes the human-only, step-up lifecycle instead.

- **An audit export is bounded at 10 000 events, newest first.**
  **Observability → Audit log → Export** produces a redacted, account-scoped
  JSONL file plus a manifest hash over the exact event ids it covers. A longer
  history exports its most recent window rather than failing, and the manifest
  states that window rather than implying completeness. The export is itself a
  governed, audited action; the file it writes lives in the workspace, so
  anything with read access to the workspace can read it afterwards.

- **Remembering something is a decision, and Memory store starts off.**
  `memory_write` and `memory_forget` are offered to the model, but like every
  acting capability they answer to their own gate, which ships **off**. With it
  on, a turn proposes the exact sentence it wants to keep and you approve or
  reject it; approving really stores it, and text that looks like a credential
  is refused before you are asked. The Memory page states which of those you are
  in rather than promising proposals a disabled gate cannot produce.
- **A composer mode tightens the turn; it never widens your permissions.**
  Build's **Plan / Edit / Auto** modes are this conversation's posture, sent with
  each prompt and applied to that turn: Plan refuses file writes, patches and
  commands outright, Edit turns each one into a decision, and both leave your
  standing permissions untouched. A turn may only ever tighten itself — `allow`
  and `auto` are refused by the prompt contract — so **Auto** adds no restriction
  of its own and does exactly as much as you already allowed, which the composer
  states rather than implies. That is why Build **opens in Auto**: the default
  posture is the one that defers to Permissions instead of quietly overriding it.
  Widening a permission still happens on Permissions, under the step-up: a
  recorded reason, and a threat-model acknowledgement where the capability
  demands one.
- **The code map answers where a name is defined and where it is used, but it
  matches text rather than resolving a call graph.** Turning on **Code map** lets
  Raiker index the repository Build points at, so the agent can ask where
  something is defined instead of guessing a search pattern; it is rebuilt on
  demand and refreshed for the files an approved change touched. Python is parsed
  with a real parser; fifteen other languages are matched with bounded patterns,
  which finds most declarations and misses unusual ones — each file records which
  extractor produced it. **Find references** answers the other half — what would
  break if you changed this — by scanning the files that map already accepted for
  word-boundary uses of one identifier, excluding the declaration itself. It is
  textual, so a same-named symbol from another module matches too, and it says so
  rather than implying a precision it does not have. A scan that hits one of its
  bounds reports `partial` and names the bound rather than presenting a partial
  answer as a complete one. There is still no resolved call graph and no
  embeddings over the tree.
- **A component that keeps failing is contained, and stays contained until you
  say otherwise.** Budgets alone let a hard-down provider or a broken tool spend
  a whole turn one doomed call at a time, so Raiker counts consecutive failures
  per tool and per provider in durable state: three in a row pauses that subject
  with a stated reason and a raised finding, and further calls are refused rather
  than retried. After a minute one call is let through as a probe; if it works,
  the pause clears itself. Nothing here is a ban — Settings → Security & sign-in
  lists every contained subject with its reason and clears it in one press — but
  a turn that finds every model contained says so instead of trying them all
  again.
- **Suspicious content in a source is reported, never blocked.** Text a page,
  message or attachment carries that is shaped like a prompt-injection attempt —
  cancelling earlier instructions, impersonating a system turn, asking for a key,
  asking to skip approval, hidden characters — raises a finding naming that exact
  document or URL. It is deliberately advisory: the thing that actually stops a
  hijack is the deny-by-default tool gate, and external content is framed as data
  and never as instruction whatever the scan finds. The rules are fixed patterns
  with names, not a classifier, because a filter that is right most of the time
  would read as an assurance it cannot give.
- **A plugin signature proves an author only once you configure a key.** Raiker
  verifies manifest checksums always, and manifest signatures against
  `RAIKER_PLUGIN_SIGNING_KEY` (yours) or `RAIKER_PLUGIN_ED25519_PUBLIC_KEY` (a
  publisher's) when either is set. With neither set — the default — a signature
  is recorded as **Present only**: the checksum still catches an accidental edit,
  but nothing was checked against an author. Extensions → Plugins states which of
  the three levels each installed plugin earned and what would raise it. The
  default is not silently hardened; it is stated.
- **A model check expires, and Raiker re-confirms it rather than stopping
  you.** Before any surface will send, the exact model has to have passed a
  reachability check; that check is good for five minutes by default and 1–120
  minutes by your setting (Settings → Runtime). **An expired check is not an
  unset-up model.** If you send with one, Raiker re-takes the check as it admits
  the turn and runs on the fresh result — so no turn ever runs on a claim older
  than your window, and you are never asked to set up a model you already set up,
  however long Raiker was closed. The cost is that the first turn after an expiry
  waits for that check, and on a hosted provider the check is the same tiny
  one-token preflight the **Check again** button runs — so it can incur the same
  negligible charge without you pressing anything. Only a check that *fails*
  stops you, and it names what failed. While a work surface is open the selected model is also
  re-confirmed in the background as its window runs down, and connecting,
  switching model, pulling, or changing an endpoint or credential still
  invalidates a check immediately — that kind of invalidation is a real change
  under the model, so it is re-checked explicitly rather than silently.
- **Key pages are not locked into RAM by default.** The workspace database is
  SQLCipher-encrypted. SQLCipher can additionally lock the pages holding key
  material so they never reach swap — and Raiker leaves that **off**, explicitly,
  for two measured reasons: it costs about seven times on every store operation
  (0.17 s versus 1.14 s for a bootstrap plus two hundred reads), and when the
  platform's locked-memory allowance runs out the failure is not slow work but
  `MemoryError` on every request, because authentication opens the store — the
  lockout FIXED-150 records. Which posture you are on is not left to guesswork:
  `GET /api/health` reports the setting, the reason, and the allowance this
  machine would have given. Set `RAIKER_SQLCIPHER_MEMORY_SECURITY=on` to demand
  the stronger one; a refused lock then fails closed and names why.
- **Shipped list prices are unverified defaults.** `raiker/config/model-profiles.json`
  seeds prices only for the models whose published rate is recorded there, each
  stamped with an `as_of` date. Check them against your provider's current
  pricing page and override anything that has moved; an unpriced model reports
  its cost as unknown rather than as zero.

## Where Raiker is behind the general standard for agent products

The limits above are boundaries Raiker chose. These are the ones where it is
simply behind, stated at the point they stop being theoretical. Each is measured
on the shipped build, not estimated.

- **Memory does not retrieve by meaning — it retrieves by shared words.** Both
  halves of "hybrid" retrieval are lexical. The vector half
  (`raiker/vector/__init__.py`) is a feature-hashing bag-of-tokens embedding
  computed offline with no model: it scores word overlap, so a memory that
  answers the question in different words scores zero and is not recalled. Ask
  *"what theme does the user like"* and a stored *"the owner prefers dark
  mode"* is reachable only through the one word the two sentences happen to
  share. Products that advertise memory use a real embedding model here.
  **Partly addressed 2026-08-17 (FIXED-230):** retrieval now resolves one
  owner-selected embedding space, embeds the query in that same space, and
  refuses to mix two — and the Memory page names the space in force and says
  whether a paraphrase can recall anything at all, rather than letting the word
  "vector" imply semantics that are not there.
  **The write half closed 2026-08-25 (FIXED-283):** what was
  missing was not the *selection* of a space but any way to *produce* one.
  Memory → Recall backend now builds one — one governed `model_provider_runtime`
  action over the owner's approved memories, bounded, owner-scoped, refusing
  secret-shaped rows, with the model and the count stated before anything leaves
  the machine. Measured live on 2026-08-25 against `text-embedding-3-small`: the
  space becomes selectable and `auto` resolves to it over the fallback.
  **The read half closed 2026-08-26 (FIXED-292 through FIXED-294).** Questions
  are embedded once through the same governed provider/local path and that one
  vector is shared by ambient and explicit recall. Denial or backend failure
  falls back to lexical results without blocking the read. Managed-file passages
  participate in the same owner/project-scoped query and carry revision-bound
  source provenance.
  **Also still behind:** an install with **no** provider key and no local
  embedding model has only the labelled hashing fallback — nothing is bundled, by
  design — and recall over the chosen space is a linear scan whose cost grows
  with the corpus. Tracked as MEM-10's remainder and backlog #5. The durable
  semantic/vector *write* path — memory written straight to a vector without an
  approval — remains disabled outright (`raiker/memory/semantic.py`), which is a
  separate and deliberate boundary.
- ~~**Lexical results are ordered by recency, not relevance.**~~ **Fixed
  2026-08-17.** This said the bundled SQLCipher build had no FTS5 and therefore
  no BM25, which was true of `sqlcipher3-wheels` 0.5.2 and 0.5.4 and stopped
  being true at 0.5.6 without anyone re-measuring. Both text indexes are now
  FTS5 and both searches rank by `bm25()` before recency, so the exact answer
  from two years ago ranks first instead of being dropped. The engine is probed
  at runtime and reported on `/api/health`; a build genuinely without FTS5 still
  falls back to FTS4 and recency, and says so. Closed as FIXED-231.
- ~~**Every recall reads every embedding.**~~ **Fixed 2026-08-28
  (FIXED-301).** Eligible-memory mutations increment a durable revision; recall
  reuses its selected owner/scope/model index until that revision changes. Small
  spaces retain exact cosine ranking and large ones use bounded approximate
  lookup followed by exact score re-ranking.
- **A natural-language question drops the lexical half of retrieval
  altogether.** Terms shorter than three characters are discarded and the rest
  are combined with an implicit `AND`, so *"Kubernetes rollout"* matches and
  *"how does the Kubernetes rollout work"* matches nothing — the longer and more
  natural the question, the likelier every term must appear in one memory. The
  vector half still answers, and it is lexical too.
- **Entity relationships are evidence-bound and reviewed; nothing expires by
  itself.** Approved memory and conversation evidence now creates owner-scoped
  entity/relationship proposals, and only accepted proposals reach graph recall
  (MEM-06 / FIXED-241). No retention sweep is started, so `expires_at` is enforced only at read time
  and expired rows are collected only when the owner confirms a cleanup
  (MEM-07). Eidetic capture is invoked by the runtime as of 2026-08-17 (MEM-04),
  and what it recorded is in **Memory → Observations**; what it cannot do is
  replay the material, because it deliberately never held it.
- **The governed shell keeps unproved controls off.** Foreground SSH and Daytona
  adapters, filtered-egress policy/proxy/revocation, credential delta snapshots
  and runner trust verification now exist. This host had no container daemon or
  production signing anchor, so live egress bypass, credential delivery/merge
  and publisher verification remain unavailable rather than configuration-
  enabled. PTY and restart reattachment are POSIX-only; see BUG-194.
- **Hooks cover part of the reference lifecycle; channels stop short of routing.**
  Every event Raiker's own format accepts is emitted — twenty — with an owner off
  switch and a page that states which rules actually enforce. Measured against
  [Claude Code's thirty-one](https://code.claude.com/docs/en/hooks) that is
  **twenty of thirty-one**, which is the ceiling
  [`HOOKS_SPEC.md`](../architecture/HOOKS_SPEC.md#which-of-the-fifteen-are-worth-adding)
  assessed as worth reaching: of the eleven left, two are blocked behind a
  mid-turn question surface that does not exist, four do not apply to a
  single-owner local product, and five were judged of little value. Three handler types run — `command`, bounded
  tool-free `prompt`, and Raiker's own in-process `builtin` — so two of the five
  reference types are built. Plugins contribute
  hook rules, skills and MCP-server offers; panels and LSP servers do not, and
  four kinds Claude Code has — subagents, monitors, `bin/` executables, themes —
  Raiker
  [will not add](REFERENCE_PLATFORM_COMPATIBILITY.md#4-deliberately-refused).
  Channels gained their authority contract, then their owner surface, then
  per-sender rate limits and signed delivery. What is still short there is above
  the transport — the spec's routing modes, and resolving an approval over a
  channel.
- ~~**Eight gated capabilities have no threat model.**~~ **Closed 2026-08-23.**
  Opening a higher-risk gate requires a threat-model acknowledgement recorded
  against your principal, and eight capabilities had nothing written to
  acknowledge. Re-deriving the comparison found the count **understated**: it had
  credited any document that mentioned a capability's name in passing, which hid
  three more — `shell_execution` (the broadest capability in the product),
  `process_execution` and `semantic_memory_runtime` — and left
  `file_write_execution` / `patch_apply_execution` with only a section of
  `THREAT_MODEL.md` whose central claim had gone stale. Eleven documents now
  close it, and **all forty-six capabilities with a real executor have one**,
  each reachable from
  [the threat-models index](../threat-models/README.md#coverage--every-capability-with-a-real-executor-has-one)
  rather than only by filename. A test asserts the coverage so it cannot drift
  back.

- **`process_execution` is a real gate with no caller.** It shares
  `shell_execution`'s whole lifecycle — the same profile resolution, the same
  measured boundary, the same receipts and redaction — but no tool or route
  constructs a `process` action, and it is deliberately not relayed by an
  approval. Turning the gate on therefore changes nothing about what the agent
  can do; the command it actually runs answers to `shell_execution`. It is the
  last capability in that position, and consolidating the two is tracked in
  [the backlog](REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog).
  Detail: [`threat-models/process-execution.md`](../threat-models/process-execution.md).

- **A checkpoint over 8 MiB is captured as unrestorable, not refused.**
  `MAX_PRE_IMAGE_BYTES` is 8 MiB. A larger file is still written, and its
  pre-image is recorded with `capture_status: oversize` — restorable is exactly
  what it is not. You are told **before** you approve: the approval notice for a
  file that size drops the rewind promise and says the change cannot be undone
  and why, and the restore preflight marks the same files as not restorable.
  Capture is complete in the sense that every eligible mutation
  is attempted; it is not complete in the sense that every mutation can be
  undone. Only `file_write_execution` and `patch_apply_execution` are
  pre-image-captured at all (`CAPTURE_PATH_ARG`); a commit is git history rather
  than a file the store holds a pre-image of, and the approval notice says so.
  Detail in
  [`threat-models/workspace-file-mutation.md`](../threat-models/workspace-file-mutation.md).

- **Raiker negotiates the current MCP revision, and implements a subset of
  it.** `MCP_PROTOCOL_VERSION` is
  [`2026-07-28`](https://modelcontextprotocol.io/specification/versioning), and
  `2025-06-18`, `2025-03-26` and `2024-11-05` are accepted when a server answers
  with one of them; a revision Raiker does not implement is refused rather than
  guessed at. **Extensions → MCP** states the revision each server negotiated.
  What Raiker uses of that revision is still the bounded session — `initialize`,
  `tools/list`, `tools/call`. Streamable-HTTP session semantics, structured tool
  output, resource links, elicitation and the `server/discover` RPC are not
  implemented, and remote transport still has no OAuth flow; the `http`
  transport is Raiker's own bounded client rather than the spec's.

The memory items are the ones to weigh first if you are choosing Raiker for its
memory: the full audit, with reproductions, is
[`plans/MEMORY_RELIABILITY_PLAN.md`](../plans/MEMORY_RELIABILITY_PLAN.md).

[`plans/TO_BE_FIXED.md`](../plans/TO_BE_FIXED.md) lists only what is still open;
everything closed keeps its full record — observation, root cause, and the
interface outcome that had to be true first — in
[`plans/FIXED_ITEMS.md`](../plans/FIXED_ITEMS.md).
