"""Bounding what a turn's tool catalogue costs (compatibility backlog #16).

Forty-nine built-in tools enter every request at full schema, and every tool a
connected MCP server advertises is projected on top of that. Measured on the
current registry that is ~25 KB — roughly **6,400 tokens before a single word of
the owner's prompt**, paid on every turn of every conversation, most of it
describing tools the turn will never call.

The reference platforms answer this with a *tool search*: a small always-present
core, plus a way for the model to ask for the schema of anything else and have
it stay available for the rest of the turn. Raiker does the same, with two
properties of its own:

* **Deferring is not gating.** A deferred tool is not withheld, restricted, or
  made harder to reach; the model is told every name that exists and gets the
  full schema the moment it asks. Nothing here decides *whether* a tool may run
  — the capability gate, the decision mode, the policy engine and the approval
  queue do, unchanged, exactly as they did when every schema was in the request.
  A search that returned a tool grants precisely nothing.
* **It is derived, not remembered.** The split is one declared set checked
  against the registry at import, so a tool added tomorrow is deferred by
  default rather than silently absent from both halves.

The core set is chosen by what a turn needs *before it has thought* — reading,
searching, editing, running, planning, asking the owner. Everything else is one
tool call away.
"""

from __future__ import annotations

import re

from raiker.models.contracts import ToolSpec
from raiker.models.tool_registry import MODEL_EXPOSED_TOOLS, TOOL_DESCRIPTIONS

_WORD = re.compile(r"[a-z0-9]+")
#: Words too common in a tool description to mean anything as a query term.
_STOPWORDS = frozenset({
    "a", "all", "an", "and", "any", "are", "as", "at", "be", "by", "call",
    "can", "for", "from", "in", "is", "it", "its", "me", "my", "of", "on",
    "one", "or", "the", "this", "to", "with",
})

#: The tool that fetches a deferred schema. Always projected, by definition:
#: it is how everything else is reached.
TOOL_SEARCH = "tool_search"

#: Tools every turn carries at full schema.
#:
#: The rule is "what a turn needs before it has thought about the task": the
#: read set, the write set, the two ways to run something, the planning and
#: question tools, recall, and the web. A tool outside this set is not less
#: available — it costs one `tool_search` call to reach, and that call is
#: cheaper than carrying forty-nine schemas through every turn of a long
#: conversation.
ALWAYS_PROJECTED: frozenset[str] = frozenset({
    # Reading the workspace.
    "read_file",
    "glob",
    "grep",
    "list_directory",
    "stat_path",
    "code_map_search",
    # Changing it.
    "edit_file",
    "apply_patch",
    "write_file",
    # Running things.
    "shell",
    "run_command",
    # The turn's own controls.
    "update_plan",
    "ask_owner_question",
    "spawn_subagent",
    "skill_load",
    # Remembering and finding.
    "memory_search",
    "memory_write",
    "conversation_search",
    # The outside world and the work it produces.
    "web_search",
    "web_fetch",
    "create_task",
    "create_document",
    # Where a coding turn starts.
    "git_status",
    "git_diff",
})

# A name here that is not a model-exposed tool would silently project nothing,
# and a typo would be invisible until a turn went looking for a tool that was in
# neither half. Checked at import, where it fails loudly.
_UNKNOWN = ALWAYS_PROJECTED - MODEL_EXPOSED_TOOLS
if _UNKNOWN:  # pragma: no cover - a definition error, not a runtime state
    raise ValueError(f"always_projected_names_unknown_tools:{sorted(_UNKNOWN)}")


#: Model-exposed tools whose schema is fetched rather than carried.
DEFERRABLE_TOOL_NAMES: frozenset[str] = frozenset(
    MODEL_EXPOSED_TOOLS - ALWAYS_PROJECTED - {TOOL_SEARCH}
)


def deferred_tool_names() -> tuple[str, ...]:
    """The deferred set, in a stable order."""
    return tuple(sorted(DEFERRABLE_TOOL_NAMES))


def _one_line(name: str) -> str:
    """The first sentence of a tool's description, for the deferred index.

    A name alone does not tell a model whether `document_symbols` is what it
    wants; the whole paragraph would put back most of what deferring saved.
    """
    text = TOOL_DESCRIPTIONS.get(name, "")
    head = text.split(". ", 1)[0].strip()
    return head[:120] if head else name


def deferred_index() -> str:
    """The catalogue line a model reads to know what it can ask for."""
    return "; ".join(f"{name}: {_one_line(name)}" for name in deferred_tool_names())


def matching_tools(query: str, *, limit: int = 8) -> tuple[str, ...]:
    """Deferred tools whose name or description matches *query*.

    Scored rather than filtered, because a model asking for "commit my work"
    should reach `git_commit` without having guessed the name. An exact name
    always wins; after that it is how many of the query's words appear, so a
    two-word query cannot be beaten by a tool that merely repeats one of them.
    """
    terms = [word for word in _WORD.findall(query.lower()) if word not in _STOPWORDS]
    scored: list[tuple[int, str]] = []
    for name in deferred_tool_names():
        if name.lower() == query.strip().lower():
            scored.append((1000, name))
            continue
        # Whole words, not substrings. "all" inside "Call the tool" matched
        # five unrelated tools and turned a query that means nothing into five
        # confident answers.
        described = set(_WORD.findall(f"{name} {TOOL_DESCRIPTIONS.get(name, '')}".lower()))
        named = set(_WORD.findall(name.lower()))
        # A term in the *name* is worth more than one buried in prose: "commit"
        # in `git_commit` is what the model meant; "commit" in another tool's
        # description is a coincidence.
        score = sum(1 for term in terms if term in described)
        score += sum(2 for term in terms if term in named)
        if score:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(name for _score, name in scored[:limit])


def project_specs(
    all_specs: list[ToolSpec],
    *,
    revealed: frozenset[str] = frozenset(),
    defer: bool = True,
) -> list[ToolSpec]:
    """The specs this request carries: the core, plus whatever was revealed.

    ``defer=False`` returns everything, which is what the owner's *Carry every
    tool schema* setting selects and what a caller with no turn state (a
    subagent step, a one-shot) gets. The order is the caller's, so a provider
    that treats the list as stable sees a stable list.
    """
    if not defer:
        return all_specs
    keep = ALWAYS_PROJECTED | {TOOL_SEARCH} | set(revealed)
    kept = [spec for spec in all_specs if spec.name in keep]
    # The model has to know what it can ask for, or deferring becomes hiding.
    # The catalogue rides on `tool_search`'s own description — the one spec
    # guaranteed to be in every request — as one line per deferred tool. That
    # costs a few hundred tokens against the several thousand the full schemas
    # cost, and it is the whole difference between "not carried" and "not
    # available".
    still_deferred = sorted(DEFERRABLE_TOOL_NAMES - set(revealed))
    if not still_deferred:
        return kept
    index = "; ".join(f"{name}: {_one_line(name)}" for name in still_deferred)
    return [
        (
            spec
            if spec.name != TOOL_SEARCH
            else ToolSpec(
                name=spec.name,
                description=(
                    f"{spec.description} Available on request — {index}"
                ),
                parameters=spec.parameters,
            )
        )
        for spec in kept
    ]


def search_tools(query: str, *, limit: int = 8) -> dict[str, object]:
    """The `tool_search` result: full schemas for what *query* matched.

    Shaped like every other tool result so the broker, the audit record and the
    transcript treat it as one. What the model gets back is the **same schema**
    `default_tool_specs` would have carried, produced by the same function, so a
    tool reached this way cannot be described differently from one that was in
    the request all along.

    An empty query is answered with the whole deferred catalogue rather than
    with a refusal: a model that asks "what else is there" has asked a fair
    question, and the list is small.
    """
    from raiker.models.tool_call_validation import tool_spec

    names = deferred_tool_names() if not query.strip() else matching_tools(query, limit=limit)
    if not names:
        return {
            "status": "success",
            "query": query,
            "matched": 0,
            "tools": [],
            # Not an error: nothing matched, and saying which names exist is
            # more use than saying no.
            "available": list(deferred_tool_names()),
        }
    return {
        "status": "success",
        "query": query,
        "matched": len(names),
        "tools": [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            }
            for spec in (tool_spec(name) for name in names)
        ],
    }
