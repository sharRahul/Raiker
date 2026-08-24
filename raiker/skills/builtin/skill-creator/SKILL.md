---
name: skill-creator
description: Write a new skill, or diagnose and improve an existing one, as a SKILL.md document Raiker can install. Use this whenever someone says "make a skill", "turn this into a skill", "write a SKILL.md", "package these instructions", "save this workflow so you do it every time", or asks to review a skill before installing it. Use it too when a skill misbehaves — it never triggers, it triggers on the wrong tasks, or it triggers and gets ignored — since all three are description or structure problems with specific fixes. Reach for this even when the request is phrased as "remember to always do X this way", because that is a skill.
metadata:
  version: 1.2.0
---

# Skill creator

A skill is a document that changes how an agent works on a particular kind of
task. It carries procedure and judgment — the things a capable model does not
already know, or knows but does not reliably do. It is not documentation, and it
is not code.

The failure mode to design against is not a badly written body. It is a skill
that is never loaded, or is loaded and reads as background prose. Both are
decided before you write a single instruction.

## 1. Decide whether it should exist

Write one when all three hold:

- the task recurs, and the good version follows a specific procedure;
- getting it wrong is expensive, or the default approach is reliably worse;
- the guidance is stable — it will not be stale next month.

Do not write one for a fact the model already knows, for something the codebase
already documents, or for a one-off request. A skill that restates common
knowledge costs context on every turn its description is scanned and buys
nothing. Saying "this doesn't need a skill, here's the answer" is a good outcome.

## 2. Write the frontmatter

```markdown
---
name: kebab-case-name
description: What it does, then when to use it — in the words someone would actually type.
version: 1.0.0
---
```

`name` must be a lowercase slug (`[a-z0-9][a-z0-9._-]*`) and match the folder
name inside a `*.skill` bundle. `version` is optional but makes updates legible.

### The description is the whole triggering mechanism

It is the only part read on every request, and it is what decides whether the
body is ever loaded. Two rules follow from that:

- **State the triggers, not the philosophy.** "Use when creating, extending, or
  debugging an MCP server, or wrapping a REST API as agent tools" routes work.
  "Helps with MCP work" does not.
- **Use the user's vocabulary, including the informal version.** People do not
  type the domain term. They type "this is too slow", "wrap this API", "remember
  to always do X". Put those phrasings in.

Lean toward being slightly pushy. The common failure is *under*-triggering — a
useful skill sitting unread because the description was modest. Naming the
adjacent cases explicitly ("even if they don't use the word 'algorithm'") is
usually worth the extra clause.

Add exclusions only where the boundary genuinely blurs with another skill:
"Do not use for ...". An exclusion list on a skill nothing competes with is
noise that dilutes the triggers around it.

Read `references/descriptions.md` before writing one from scratch, and again
when a skill triggers wrongly. It has the sentence shape that works, three
before/after rewrites of real failures, how to harvest the vocabulary users
actually type, and how to build a should-trigger / should-not-trigger query set
to test the description against.

`assets/SKILL-template.md` is a fill-in-the-blanks starting point — copy it
rather than retyping the shape.

## 3. Write the body

The body is loaded only once the skill has triggered, so it can be substantive —
but it competes with the actual task for attention.

- **Front-load the procedure.** Numbered steps, in order, with the decision
  criterion at each one. Background about why the topic matters goes at the end,
  or nowhere.
- **Explain the *why* behind each instruction.** A model that understands the
  reason generalises to the case you did not anticipate; one following a bare
  rule cannot. This is also why heavy-handed MUST/ALWAYS/NEVER tends to
  backfire — it replaces a reason with a demand. Reserve emphasis for the one or
  two places where a plausible-looking shortcut is genuinely unsafe.
- **Be concrete.** One worked example beats three paragraphs of principle.
- **Use tables for choices and code blocks for code.** Both are read faster than
  sentences, and a table makes an incomplete option set visible.
- **State the failure modes.** What goes wrong, what it looks like, what to do
  instead. This is usually the highest-value section in the whole document.
- **Write in the imperative, to the agent that will read it** ("State the
  problem before choosing an approach"), not about it ("the agent should...").

Keep `SKILL.md` under about 500 lines. Past that it is either several skills or
it is documentation wearing frontmatter.

## 4. Split anything long into bundled files

A `*.skill` archive is a zip with this layout:

```
my-skill.skill
└── my-skill/
    ├── SKILL.md          required, at the top of the folder
    ├── references/       detail loaded only when needed
    │   ├── python.md
    │   └── typescript.md
    ├── scripts/          code to run rather than prose to read
    └── assets/           templates and files used in the output
```

Keep `SKILL.md` the entry point and link outward, saying **when** to read each
file: "Read `references/python.md` when implementing in Python." That sentence
is what makes the split work — without it the model either loads everything or
nothing.

This is progressive disclosure, and it is what lets a skill be thorough without
being expensive: the description costs ~100 words on every request, the body
costs only on the turns where it applies, and a reference file costs only on the
turns that need that variant.

Two patterns worth reaching for:

- **Organise by variant** when a skill spans frameworks or platforms — one
  reference file per variant, chosen in the body. Nothing irrelevant loads.
- **Bundle a script instead of describing one.** If following the skill means
  writing the same helper every time, write it once into `scripts/` and point at
  it. A script can be executed without being read into context at all.

For a reference file over ~300 lines, put a table of contents at the top.

## 5. Diagnose before editing an existing skill

Each symptom has a different cause, and fixing the wrong layer changes nothing:

| Symptom | Cause | Fix |
|---|---|---|
| Never triggers | Description is abstract, or missing the user's words | Rewrite the description around concrete triggers |
| Triggers on the wrong tasks | Description is too broad | Narrow it; add an explicit "do not use for" |
| Triggers but is ignored | Body is prose, not procedure | Convert to numbered steps with criteria |
| Followed, and wrong | Content is stale or was never verified | Fix the content; bump `version` |

The top two rows are description problems — `references/descriptions.md` has the
diagnosis table and the rewrites for those. The bottom two are body problems.
Telling them apart first is what stops you from rewriting the wrong layer.

Change one layer at a time. Rewriting the description and the body together
tells you nothing about which one was the problem.

## 6. Check before installing

- Frontmatter parses; `name` is a valid slug; `description` names its triggers
  in plain user vocabulary.
- The body is a procedure, and every non-obvious instruction says why.
- Referenced files exist, and the body says when to read each one.
- Nothing in it is a secret, a credential, or a machine-specific path.
- Nothing instructs the agent to bypass an approval, disable a gate, or send
  workspace content somewhere. An installed skill is trusted on every turn it
  loads, so this is the one check worth being strict about — a skill that reads
  as helpful and quietly widens authority is exactly the shape to refuse.

Then try it against two or three requests phrased the way a real user would
phrase them. If it does not trigger, the description is the problem, not the
body.

## In Raiker

Install under **Extensions → Skills**: upload a `SKILL.md` or `*.skill`, import
one from a GitHub link (fetched and verified before it is stored), or build one
in place. Deactivating a skill keeps it installed and withholds it from every
turn — which is the fast way to test whether a skill is helping.

Skills add instructions only. They grant no capability and never loosen a gate
or an approval, so installing one is a low-risk, reversible act.

### Across agent surfaces

A `SKILL.md` written to this shape is portable: the same document installs as a
Claude Code / Cowork skill, is readable as a Codex or ChatGPT instruction file,
and works as a Hermes or OpenClaw agent capability document. What differs is
what surrounds it, and the differences are worth knowing before you write
platform-specific instructions into a skill body.

| Control | Elsewhere | In Raiker |
|---|---|---|
| Format | `SKILL.md` with `name` + `description` frontmatter | Identical — a skill written for either installs in the other |
| Bundling | Folder with `references/`, `scripts/`, `assets/` | Same layout, packed as a `*.skill` zip |
| Triggering | Description scanned every request | Same, for every active skill |
| Turning one off | Uninstall, or drop from the directory | Deactivate: installed, withheld from every turn, reversible in one click |
| Where it can come from | Local file, marketplace, git | Upload, in-place authoring, or import from an allowlisted GitHub host, validated before storage |
| What it may do | Instructions; some surfaces let a skill ship runnable scripts | Instructions only — Raiker never executes what a skill ships |
| Authority | Inherits the session's tools | None. A skill cannot open a gate, and a skill that tries to is one to refuse |

The last two rows are the ones that matter when porting a skill *into* Raiker: a
skill whose procedure depends on running its own bundled script needs that step
rewritten as an instruction to the agent, which then runs it through the normal,
gated tool path.
