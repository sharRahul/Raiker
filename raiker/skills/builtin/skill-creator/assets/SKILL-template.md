---
name: your-skill-name
description: What this does in one clause, then when to use it — "Use this whenever someone says X, mentions Y, or asks to Z." Include the informal phrasings a real user would type, not just the domain term. Add "Do not use for ..." only if another skill genuinely competes.
version: 1.0.0
---

# Your skill name

One or two sentences on what this skill makes the agent do differently, and the
failure it exists to prevent. Not a definition of the topic — the reader already
knows the topic; it does not yet know the procedure.

## When this applies

The cases this covers, and the adjacent cases it does not. Say plainly when the
right answer is to skip the procedure and just do the task.

## 1. First step

What to do, and the criterion for deciding. Say *why* it matters — an agent that
understands the reason handles the case you did not anticipate.

## 2. Second step

Keep steps in the order they are performed. Put the decision at the top of the
step, not buried after the explanation.

| Signal | Do this |
|---|---|
| ... | ... |

## 3. Verify

The smallest check that would actually fail if the work were wrong, and an
instruction to run it and report what came back.

## Report

The shape of the deliverable, in the order it should appear. Naming this stops
every invocation from inventing its own format.

## Where this usually goes wrong

- **The failure.** What it looks like, and what to do instead.
- **The next failure.** Same shape.

<!--
Bundled files, if the skill needs them. Delete this comment when done.

  your-skill-name/
  ├── SKILL.md
  ├── references/   detail loaded only when needed — say WHEN to read each
  ├── scripts/      code to run rather than prose to re-derive every time
  └── assets/       templates and files used in the output

Link them from the body with the condition attached:
  "Read `references/python.md` when implementing in Python."
Without that sentence the model loads everything or nothing.
-->
