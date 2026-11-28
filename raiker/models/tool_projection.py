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
    "record_lesson",
    "ask_owner_question",
    "spawn_subagent",
    "skill_load",
    # Remembering and finding.
    "memory_search",
    "memory_reflect",
    "note_search",
    "note_read",
    "memory_write",
    "conversation_search",
    # How Raiker itself works (TOOL-46): asked about often, and small.
    "help_read",
    # The way a turn offers what it cannot reach (TOOL-72).
    "suggest_connection",
    # The outside world and the work it produces.
    "web_search",
    "web_fetch",
    "web_extract",
    "weather_lookup",
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
#: FIXED-1436 — the core a small-context model carries. A local model with an
#: 8K or 16K window spent most of it on ~5,500 tokens of schemas before the
#: owner typed (measured 9,459 prompt tokens for one Chat question). Below
#: :data:`SMALL_CONTEXT_TOKENS` a turn carries these and names the rest, without
#: descriptions, on `tool_search`; every other tool is still one search away and
#: passes the same gate, decision mode and approval when called.
COMPACT_PROJECTED: frozenset[str] = frozenset({
    "read_file",
    "glob",
    "grep",
    "list_directory",
    "edit_file",
    "write_file",
    "shell",
    "update_plan",
    "ask_owner_question",
    "memory_search",
    "web_search",
    "web_fetch",
})
if COMPACT_PROJECTED - ALWAYS_PROJECTED:  # pragma: no cover - a definition error
    raise ValueError("compact_projected_must_be_a_subset_of_the_core")

#: A model whose advertised window is at or below this carries the compact core.
SMALL_CONTEXT_TOKENS = 16_384


def compact_for(context_window_tokens: int | None) -> bool:
    """Whether a turn on a model with this window carries the compact core."""
    return context_window_tokens is not None and 0 < context_window_tokens <= SMALL_CONTEXT_TOKENS


DEFERRABLE_TOOL_NAMES: frozenset[str] = frozenset(
    MODEL_EXPOSED_TOOLS - ALWAYS_PROJECTED - {TOOL_SEARCH}
)


#: How much a turn will carry in *projected MCP* schemas before deferring them.
#:
#: The built-in split is a declared set, because the built-ins are Raiker's own
#: and their cost is known at import. A connected server's catalogue is neither:
#: it is whatever the owner has added, it changes between turns, and since
#: backlog #16's MCP half each tool carries the server's declared `inputSchema`
#: rather than one untyped object — so it can be a hundred tokens or ten
#: thousand. The rule is therefore a measured budget rather than a list.
#:
#: All-or-nothing on purpose. Carrying half of one server's tools and deferring
#: the rest would leave the model with an incoherent picture of that server —
#: some tools typed, some named, no way to tell which. So the catalogue is
#: carried whole while it fits and deferred whole when it does not, and either
#: way every tool is named in the index and one `tool_search` away.
MCP_SCHEMA_BUDGET_CHARS = 6_000


def deferred_tool_names() -> tuple[str, ...]:
    """The deferred set, in a stable order."""
    return tuple(sorted(DEFERRABLE_TOOL_NAMES))


def _spec_cost(spec: ToolSpec) -> int:
    """Roughly what one schema costs a request, in characters."""
    return len(spec.name) + len(spec.description) + len(str(spec.parameters))


def mcp_specs_fit_budget(mcp_specs: list[ToolSpec]) -> bool:
    """Whether this turn's projected MCP catalogue is carried rather than deferred."""
    return sum(_spec_cost(spec) for spec in mcp_specs) <= MCP_SCHEMA_BUDGET_CHARS


def _one_line(name: str, description: str | None = None) -> str:
    """The first sentence of a tool's description, for the deferred index.

    A name alone does not tell a model whether `document_symbols` is what it
    wants; the whole paragraph would put back most of what deferring saved.
    ``description`` is passed for a projected MCP tool, which has no registry
    entry — its sentence comes from the server profile instead.
    """
    text = description if description is not None else TOOL_DESCRIPTIONS.get(name, "")
    head = text.split(". ", 1)[0].strip()
    return head[:120] if head else name


def deferred_index() -> str:
    """The catalogue line a model reads to know what it can ask for."""
    return "; ".join(f"{name}: {_one_line(name)}" for name in deferred_tool_names())


def matching_tools(
    query: str, *, limit: int = 8, extra: dict[str, str] | None = None
) -> tuple[str, ...]:
    """Deferred tools whose name or description matches *query*.

    Scored rather than filtered, because a model asking for "commit my work"
    should reach `git_commit` without having guessed the name. An exact name
    always wins; after that it is how many of the query's words appear, so a
    two-word query cannot be beaten by a tool that merely repeats one of them.

    ``extra`` carries this turn's projected MCP tools as name → description.
    They have no registry entry by design, so they are scored from what their
    server declared rather than from `TOOL_DESCRIPTIONS`.
    """
    terms = [word for word in _WORD.findall(query.lower()) if word not in _STOPWORDS]
    # The compact core leaves part of the full core uncarried; those must be
    # findable too, or a small model could not reach `git_status` at all.
    searchable = (*deferred_tool_names(), *sorted(ALWAYS_PROJECTED - COMPACT_PROJECTED))
    described_by = {name: TOOL_DESCRIPTIONS.get(name, "") for name in searchable}
    described_by.update(extra or {})
    scored: list[tuple[int, str]] = []
    for name in sorted(described_by):
        if name.lower() == query.strip().lower():
            scored.append((1000, name))
            continue
        # Whole words, not substrings. "all" inside "Call the tool" matched
        # five unrelated tools and turned a query that means nothing into five
        # confident answers.
        named = set(_WORD.findall(name.lower()))
        # A core tool is matched by its name only: a full-window turn already
        # carries it, so it must not crowd a search's results there, and a
        # compact turn reaches it by the name its index lists.
        described = (
            named
            if name in ALWAYS_PROJECTED
            else set(_WORD.findall(f"{name} {described_by[name]}".lower()))
        )
        # A term in the *name* is worth more than one buried in prose: "commit"
        # in `git_commit` is what the model meant; "commit" in another tool's
        # description is a coincidence.
        score = sum(1 for term in terms if term in described)
        score += sum(2 for term in terms if term in named)
        if score:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(name for _score, name in scored[:limit])


#: How many deferred tools a request may pre-reveal, and the score each needs.
PRESELECT_LIMIT = 2
PRESELECT_MIN_SCORE = 3
#: Name words shared by several tools, which say nothing about which one is meant.
_GENERIC_NAME_WORDS = frozenset({
    "git", "github", "read", "write", "get", "list", "files", "file", "session",
    "code", "memory", "run", "execute", "find", "search",
})


def preselect_for_prompt(prompt: str) -> tuple[str, ...]:
    """Deferred tools the owner's request plainly asks for, revealed up front.

    The embedding follow-up of FIXED-1425 ("rank deferred tool schemas by the
    turn") done lexically, so it costs no model call and no data leaves the
    host: a deferred tool is carried from the first request only when the
    request names it: a distinctive word of the tool's *name* (``commit`` in
    ``git_commit``, never the shared ``git`` or ``read``), scored as
    :func:`matching_tools` scores. "Commit my changes" reveals ``git_commit``;
    "what's the weather" reveals nothing.

    At most :data:`PRESELECT_LIMIT`, so a long request cannot put the deferred
    catalogue back into every call. Revealing grants nothing: the gate, the
    decision mode and approvals are unchanged, exactly as for `tool_search`.
    """
    terms = [word for word in _WORD.findall(prompt.lower()) if word not in _STOPWORDS]
    if not terms:
        return ()
    scored: list[tuple[int, str]] = []
    for name in deferred_tool_names():
        named = set(_WORD.findall(name.lower())) - _GENERIC_NAME_WORDS
        described = set(_WORD.findall(f"{name} {TOOL_DESCRIPTIONS.get(name, '')}".lower()))
        unique = set(terms)
        name_hits = sum(1 for term in unique if term in named)
        if not name_hits:
            continue
        score = 2 * name_hits + sum(1 for term in unique if term in described)
        if score >= PRESELECT_MIN_SCORE:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(name for _score, name in scored[:PRESELECT_LIMIT])


def project_specs(
    all_specs: list[ToolSpec],
    *,
    revealed: frozenset[str] = frozenset(),
    defer: bool = True,
    mcp_specs: list[ToolSpec] | None = None,
    compact: bool = False,
) -> list[ToolSpec]:
    """The specs this request carries: the core, plus whatever was revealed.

    ``mcp_specs`` is this turn's projected MCP catalogue, which joins the same
    rule rather than sitting outside it: carried whole while it fits
    :data:`MCP_SCHEMA_BUDGET_CHARS`, deferred whole when it does not, and named
    in the index either way. A revealed MCP tool is carried regardless, exactly
    as a revealed built-in is.

    ``defer=False`` returns everything, which is what the owner's *Carry every
    tool schema* setting selects and what a caller with no turn state (a
    subagent step, a one-shot) gets. The order is the caller's, so a provider
    that treats the list as stable sees a stable list.
    """
    mcp = list(mcp_specs or [])
    if not defer:
        return [*all_specs, *mcp]
    core = COMPACT_PROJECTED if compact else ALWAYS_PROJECTED
    keep = core | {TOOL_SEARCH} | set(revealed)
    kept = [spec for spec in all_specs if spec.name in keep]
    mcp_carried = mcp_specs_fit_budget(mcp) and not compact
    kept.extend(spec for spec in mcp if mcp_carried or spec.name in revealed)
    # The model has to know what it can ask for, or deferring becomes hiding.
    # The catalogue rides on `tool_search`'s own description — the one spec
    # guaranteed to be in every request — as one line per deferred tool. That
    # costs a few hundred tokens against the several thousand the full schemas
    # cost, and it is the whole difference between "not carried" and "not
    # available".
    if compact:
        # Names only: the one-line descriptions alone are ~1,500 tokens.
        uncarried = (DEFERRABLE_TOOL_NAMES | (ALWAYS_PROJECTED - COMPACT_PROJECTED)) - set(revealed)
        names = sorted(uncarried) + sorted(spec.name for spec in mcp if spec.name not in revealed)
        index = ", ".join(names)
        return [
            spec
            if spec.name != TOOL_SEARCH
            else ToolSpec(
                name=spec.name,
                description=f"{spec.description} Available on request: {index}" if names else spec.description,
                parameters=spec.parameters,
            )
            for spec in kept
        ]
    entries = [(name, _one_line(name)) for name in sorted(DEFERRABLE_TOOL_NAMES - set(revealed))]
    if not mcp_carried:
        entries.extend(
            (spec.name, _one_line(spec.name, spec.description))
            for spec in sorted(mcp, key=lambda spec: spec.name)
            if spec.name not in revealed
        )
    if not entries:
        return kept
    index = "; ".join(f"{name}: {line}" for name, line in entries)
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


def search_tools(
    query: str,
    *,
    limit: int = 8,
    mcp_specs: list[ToolSpec] | None = None,
    withheld: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """The `tool_search` result: full schemas for what *query* matched.

    Shaped like every other tool result so the broker, the audit record and the
    transcript treat it as one. What the model gets back is the **same schema**
    `default_tool_specs` would have carried, produced by the same function, so a
    tool reached this way cannot be described differently from one that was in
    the request all along.

    An empty query is answered with the whole deferred catalogue rather than
    with a refusal: a model that asks "what else is there" has asked a fair
    question, and the list is small.

    ``mcp_specs`` is this turn's projected MCP catalogue. It is searchable
    whether or not it was deferred this turn, because a model that asks for a
    tool it can already see should get the same answer either way.
    """
    from raiker.models.tool_call_validation import tool_spec

    mcp = {spec.name: spec for spec in (mcp_specs or [])}
    searchable = tuple(sorted(name for name in (*deferred_tool_names(), *mcp) if name not in withheld))
    names = (
        searchable
        if not query.strip()
        else matching_tools(
            query,
            limit=limit,
            extra={name: spec.description for name, spec in mcp.items()},
        )
    )
    # ADR-0005 — a tool the turn's persona leaves out is never offered by a
    # search either; returning it made a model search for it again and again.
    refused = [name for name in names if name in withheld]
    names = tuple(name for name in names if name not in withheld)
    if not names and refused:
        return {
            "status": "success",
            "query": query,
            "matched": 0,
            "tools": [],
            "withheld": refused,
            "note": (
                "The tools that match are not available in this turn: the owner's persona "
                "leaves them out. Answer without them, and say what you could not do."
            ),
        }
    if not names:
        return {
            "status": "success",
            "query": query,
            "matched": 0,
            "tools": [],
            # Not an error: nothing matched, and saying which names exist is
            # more use than saying no.
            "available": list(searchable),
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
            # A projected MCP tool's schema comes from the same function the
            # request would have carried it with, exactly as a built-in's does.
            for spec in (mcp[name] if name in mcp else tool_spec(name) for name in names)
        ],
    }
