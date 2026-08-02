# Writing and testing a skill description

Read this from `SKILL.md` step 2 when writing a description from scratch, or
from step 5 when a skill triggers wrongly — never, too often, or on the wrong
tasks.

## Contents

- [Why this is the whole ballgame](#why-this-is-the-whole-ballgame)
- [The shape that works](#the-shape-that-works)
- [Worked rewrites](#worked-rewrites)
- [Vocabulary harvesting](#vocabulary-harvesting)
- [Testing a description](#testing-a-description)
- [Diagnosing a failing description](#diagnosing-a-failing-description)

## Why this is the whole ballgame

The description is the only part of a skill read on every request. The body,
however good, is dead weight if the description does not get it loaded. So
effort spent here is worth several times the same effort spent on the body.

There is an asymmetry worth internalising: the common failure is
*under*-triggering. A skill that occasionally loads when it was not needed costs
some context. A skill that never loads cost the whole effort of writing it. Bias
toward being slightly pushy.

There is also a threshold effect. Skills are consulted for tasks the model
cannot trivially do alone. "Read this file" will not trigger a skill however
well the description matches, because there is nothing to consult about.
Substantive, multi-step, or judgment-heavy requests trigger reliably when the
description matches. Write descriptions — and test queries — for those.

## The shape that works

```
<what it does, one clause>. Use this whenever <concrete trigger>, <another>, or
<another> — or when someone says "<literal phrase>", "<literal phrase>". Use it
too when <adjacent case that does not name the domain>. <Optional: Do not use
for X — that is Y's job.>
```

Four things to get right:

1. **What it does** comes first, in one clause. Not a paragraph of context.
2. **Triggers are concrete.** Situations and artefacts, not themes.
3. **Literal phrasings**, quoted, including the informal and the vague ones.
   People type "this is too slow", not "I require algorithmic optimisation".
4. **The adjacent case.** The single highest-value clause is usually the one
   naming a situation where the skill applies but the user never says the domain
   word. Spell it out: "even if the request never uses the word 'algorithm'".

Exclusions earn their place only where another skill genuinely competes. On a
skill nothing overlaps with, "do not use for cooking recipes" is noise that
dilutes the triggers around it.

## Worked rewrites

**Too abstract — never triggers**

> Helps with database work.

The failure: "database work" is a theme. Nothing a user types looks like it.

> Design, review, and fix relational database schemas and queries. Use this
> whenever someone shares a `CREATE TABLE` statement, asks about indexes,
> foreign keys, normalisation, or migrations, or says a query is "slow",
> "timing out", or "doing a full table scan". Use it too when someone describes
> data they need to store and asks how to model it, even if no SQL appears.

**Too broad — triggers on everything**

> Use for any task involving text.

> Rewrite prose for clarity and concision without changing its meaning. Use this
> when someone asks to "tighten", "shorten", "clean up", or "make this clearer",
> or shares a draft and asks for an edit. Do not use for translation, for
> generating new content from a brief, or for code comments — those are
> different jobs with different constraints.

**Right idea, missing the vocabulary**

> Use when creating Model Context Protocol servers.

The failure: correct but only fires when the user already knows the term. Most
requests arrive as "let Claude use our API".

> Build, extend, or debug an MCP server that exposes an API as agent tools. Use
> this whenever someone mentions MCP, FastMCP, mcp.json, or stdio transport —
> and equally when they say "wrap this API so Claude can use it", "give the
> agent access to our service", or "add a tool to the server". Use it too when
> an MCP server connects but its tools never get called, or responses blow the
> context window; those are tool-design problems even when nobody says "MCP".

## Vocabulary harvesting

Before writing, collect the words a real user would actually use:

- **Symptoms**, not diagnoses: "it's slow", "it crashes on empty input".
- **The artefact**: "this xlsx", "the CREATE TABLE", "my mcp.json".
- **The verb they'd type**: "wrap", "clean up", "tighten", "make it faster".
- **The vague ask**: "can you make this better?" in the context this covers.
- **Adjacent framings**: "remember to always do X this way" is a skill request
  even though it names no skill.

If the conversation that prompted the skill is still available, mine it — the
user's own phrasing is the best possible source, because it is exactly the
distribution the description has to match.

## Testing a description

Write 8–10 queries that *should* trigger and 8–10 that should *not*, then check
which way each goes.

Make them realistic: file paths, a bit of backstory, casual phrasing, the
occasional typo. Vary the length.

- Bad: `"Format this data"` — abstract, tests nothing.
- Good: `"ok so my boss sent me this xlsx (its in downloads, 'Q4 sales final
  FINAL v2.xlsx') and wants a column with profit margin as a percent. revenue is
  col C, costs col D i think"`

For the should-trigger set, cover different phrasings of one intent, cases where
the user never names the domain, and uncommon-but-valid uses.

For the should-not-trigger set, the valuable ones are **near-misses**: queries
sharing keywords but needing something else, adjacent domains, and cases where a
naive keyword match would fire. An obviously unrelated query is not a test —
"write a fibonacci function" proves nothing about a PDF skill.

## Diagnosing a failing description

| Observed | Cause | Change |
|---|---|---|
| Never triggers | Themes instead of situations | Replace abstractions with concrete triggers and literal phrasings |
| Never triggers, wording is concrete | Only the domain term is covered | Add the phrasings users type when they do not know the term |
| Triggers on adjacent tasks | Trigger clause too broad | Narrow the opening clause; add an exclusion for the specific competitor |
| Triggers on trivial requests | Nothing scopes it to substantive work | Say what kind of task it is for ("before writing production code") |
| Loads and is ignored | Not a description problem | The body is prose, not procedure — fix step 3, not this |

Change one thing at a time. Rewriting the opening clause and the trigger list
together tells you nothing about which one mattered.
