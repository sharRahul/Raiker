# Risk model — what low, medium, high and critical mean

> **Canonical** for the meaning of Raiker's risk bands. The bands are declared as
> data in [`raiker/policy/risk.py`](../../raiker/policy/risk.py) and rendered by
> `describe_risk_model()`; this document is the prose beside that data, not a
> second copy of it. Where the two differ, the module is right and this file is
> stale.
>
> Written **2026-08-29**.

## The defect this replaces

`RISK_LEVELS` accepted four names and Raiker defined none of them. A band was
therefore whatever the literal at each call site decided:

* `PolicyEngine.decide` asserted `high` for every tool that parked;
* the broker asserted `high` in three more places, including the
  `approval_requested` event every approval card is built from;
* four modules held their own `_READ_RISK = "medium"` / `_CALL_RISK` constant,
  each with a comment explaining that the action was "not low-risk" because it
  left the machine — the reasoning was right and the band was a guess;
* the subagent runner stamped `low` on every step whatever the tool was, and the
  plugin runtime stamped `medium`.

The measurable symptom: across 46 registered tools the declared band was exactly
`read_shaped ? medium : high`. Four names carried one bit. Nothing was `low` and
nothing was `critical`, and **both of those bands have real behaviour behind
them** — `auto_requires_approval` runs only `low` unprompted, and the router
floors `critical` to a human-only decision. Auto mode's entire benefit was
unreachable for tool calls.

The worse symptom is the one an owner feels. "High risk" meant *this parked*
rather than *this is dangerous*, so a routine workspace write and a force push to
a shared branch arrived on the queue wearing the same word. An approval queue
works because its entries mean something; teaching someone that "high" is what
ordinary work looks like is how a queue stops being read.

## Risk is a property of the action, not of the tool

This is the mistake the model is built to avoid. `write_file` is not dangerous:
writing a file inside the workspace that a checkpoint captured is ordinary, and
writing one no checkpoint can restore is not. The band belongs to the **action in
its context** and is derived from named, checkable properties of it.

A tool still *declares* a band in
[`raiker/models/tool_registry.py`](../../raiker/models/tool_registry.py). That
declaration is the **floor** — the band an action carries when nothing raises
it — and it is itself derived from the tool's declared signals, so the two halves
cannot drift: a `ToolDefinition` whose `risk` disagrees with its `risk_signals`
does not construct.

### The questions that separate the bands

| Axis | The question |
|---|---|
| Reversibility | Can it be undone, and by what? |
| Reach | Does the effect stay on this machine? |
| Observability | Can anybody but the owner see it? |
| Blast radius | Is the effect bounded to what the turn named? |
| Authority | Does it change who may act, or the agent's own oversight? |

## The four bands

| Band | What it means | What undoes it | What the runtime does |
|---|---|---|---|
| **low** | Changes nothing observable, reaches nothing off this machine, bounded to what was named. Running it twice is the same as running it once | Nothing to undo | Runs. It is not offered as a decision, because there is no decision in it |
| **medium** | Changes state on this machine only — the workspace or the owner's own records — and a checkpoint written before it restores what it replaced. Nobody outside this machine can observe it | A checkpoint restore | Runs under the owner's approval mode. `manual` parks it; `auto` may run it after the alignment check |
| **high** | **Any one of**: somebody other than the owner can see the effect; the effect leaves this machine; or the change is not covered by a checkpoint. These are checked, not counted — one is enough | Not by restoring. Undoing it is its own action, and may not be possible | Parks for the owner's approval before anything runs |
| **critical** | Destroys something no checkpoint holds outside the workspace, has a blast radius wider than what the turn named, or changes authority itself — who may act, what a capability permits, or the agent's own oversight | Nothing in Raiker | A live human decides in person. `auto` never runs it, an approval rule never pre-approves it, and its resting state is denial |

`blocked` is not a band. It is what a decision records when the action will not
happen at all, ranked above `critical` so an ordering comparison never treats a
refusal as milder than the worst band.

## The signals

A signal is a question with an answer the runtime can determine about *this*
call. None is derived from the model's description of what it is doing, because a
signal the model can phrase its way past is not a control.

| Signal | Raises to | The question |
|---|---|---|
| `changes_state` | medium | Does anything on this machine differ afterwards? |
| `not_covered_by_checkpoint` | high | Would a checkpoint restore put this back? |
| `leaves_this_machine` | high | Does anything cross the network as a result? |
| `crosses_sandbox_boundary` | high | Does it need to reach outside the boundary this turn runs in? |
| `observable_by_others` | high | Can anybody but the owner see that this happened? |
| `spends_owner_credential` | high | Does it authenticate as the owner, or spend against their account? |
| `unbounded_target` | critical | Can the runtime resolve exactly what this affects? |
| `destroys_outside_workspace` | critical | Does it remove something no checkpoint holds, outside the workspace? |
| `changes_authority` | critical | Does it change who may act, or what a capability permits? |
| `changes_own_oversight` | critical | Does it change the controls that govern the agent itself? |

### The rules that make it safe to tune

1. A tool's declared band is the floor, never the answer.
2. A signal can only **raise** an action's band. Nothing lowers it.
3. The band is the highest floor raised, so signals never contradict each other.
4. An owner setting may raise a tool's floor and can never lower one.
5. Unknown scope is treated as the widest scope.

Rule 4 is why an owner can be given this control at all: the worst a setting can
do is make Raiker ask more often. It is the same asymmetry hooks follow, for the
same reason.

## Where `critical` comes from

No tool declares `critical`, and that is correct: a tool is not critical, an
*action* is. The band is reached at the authority layer through
[`raiker/runtime/authority/critical.py`](../../raiker/runtime/authority/critical.py),
whose five criteria are already data with stable codes and an extension-only
invariant. They map onto the two critical signals above:

| Criterion | Signal it expresses |
|---|---|
| Tier-2 execution relaxation | `changes_own_oversight` |
| External send to a non-allowlisted recipient | `observable_by_others` with an unbounded recipient |
| Cross-principal checkpoint restore | `destroys_outside_workspace` |
| Standing-grant creation or broadening | `changes_authority` |
| Vault, credential or egress-allowlist operation | `changes_authority` |

## Two facts that used to wear one name

**Parking is not a band.** Whether an action waits for the owner is decided by
`approval_required_actions` in
[`raiker/policy/config.py`](../../raiker/policy/config.py); how dangerous it is
is decided here. `git_commit` is `medium` **and** parks. ADD-22's question is
`low` **and** parks. Keeping them apart is what let the question surface exist:
a question that reached the owner labelled a high-risk approval would have been
worse than not having one.

## How the reference platforms decide, and what Raiker took

Both were read for this design rather than recalled.

**Claude Code** treats risk as a property of the action and checks it against
published rule lists — what the auto-mode classifier
[blocks and allows by default](https://code.claude.com/docs/en/permission-modes),
plus two path classes: *protected* paths that no mode auto-writes, and *critical*
paths that no allow rule and no `PreToolUse` hook may approve for removal. The
lists are data an owner can print (`claude auto-mode defaults`). The signals above
are the same idea reduced to the questions that separate the bands rather than to
an enumeration of cases.

**Codex** splits it differently and more sharply: a *sandbox mode*
(`read-only`, `workspace-write`, `danger-full-access`) sets the boundary and an
*approval policy* (`untrusted`, `on-request`, `never`) says what happens when an
action needs to leave it. Risk, in that model, is the single question *does this
have to cross the boundary?*
([Codex sandboxing](https://learn.chatgpt.com/docs/sandboxing).)

Raiker takes Codex's question — `crosses_sandbox_boundary` — and can answer it
more honestly, because its OS boundary is measured rather than asserted. It takes
Claude Code's insistence that the rules are published data. And it keeps one
property neither has: **a band is recorded with the signals that produced it**, so
an assessment can be recomputed from the audit trail months later instead of
being trusted.

### Deliberately not built

Claude Code's classifier treats a boundary the owner states in conversation
("don't push until I've reviewed it") as a block signal that stays in force until
lifted. Raiker has nowhere to put that today: it would need a stored,
owner-visible constraint rather than a model's recollection of a sentence, and a
control that depends on the model remembering is not a control. Recorded here so
the absence is a decision rather than an oversight.

## Adding a tool

Declare what it does; the band follows.

```python
ToolDefinition(
    name="send_invoice",
    risk="high",                       # must equal what the signals produce
    risk_signals=("changes_state", "leaves_this_machine", "observable_by_others"),
    ...
)
```

A definition whose two halves disagree raises
`tool_definition_risk_not_derived` at import, and a signal this build does not
define raises `tool_definition_risk_signal_unknown`. Both fail at construction
rather than at review, which is the point: the band is no longer a word somebody
chose.

`tests/test_risk_model.py` holds the conformance rules — that anything leaving
the machine is at least `high`, that every band a consumer branches on is
reachable, and that every delegable tool is `low` so a subagent cannot launder
one into a milder band than it carries.
