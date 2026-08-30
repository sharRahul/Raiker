"""Where a turn's answer came from, and how to open it (C6, C4).

Chat could already read an email, a calendar entry, a web page, a memory or an
attached document — and then answer as if it had simply known. The transcript
named no source, so an answer drawn from the owner's real material was
indistinguishable from an answer the model made up. For an assistant acting on
somebody's actual mail and files that is a correctness problem, not a polish
one: a claim you cannot check reads exactly like a claim you can.

This module is the ledger that closes it, and it is deliberately narrow:

* **Derived from what really ran, never from what the model says.** A source
  exists because a governed tool call returned a result, or because the owner
  attached a file to the turn. The model is *told* the ids so it can cite them;
  it cannot invent one, and an id it cites that is not in this ledger resolves
  to nothing rather than to a plausible-looking source.
* **One source per executed call.** Not per match, per result row, or per
  paragraph. A call is the unit the runtime actually governed and audited, so it
  is the unit whose provenance can be stated honestly. ``detail`` carries the
  count when a call returned several things.
* **Content is stored, not broadcast.** ``passage`` — the bounded text the
  source handed the model — is kept because opening a source *at the passage
  that was used* needs the text that was used, and re-running the tool later
  answers a different question. It never enters the durable event log: the
  streamed record is counts and tool names, and the passage is served only over
  the session-authorized read route, to the account that owns the conversation.
* **Every unopenable source says why.** Resolution reuses the statuses
  ``source_provenance`` already established — resolved, deleted, changed,
  unsupported, not authorized — so the file inspector renders one vocabulary
  whether it was opened from a memory record or from a citation chip.

**What is not claimed.** A citation says *this call produced material this turn
had in front of it*. It does not prove the sentence beside it was drawn from
that material — only the model knows that, and it is asked rather than trusted.
That distinction is why the transcript shows the whole ledger for a turn as well
as the markers the model wrote: the ledger is a fact, the marker is a claim.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.models.tool_registry import TOOL_SOURCE_KIND_BY_TOOL
from raiker.runtime.source_provenance import (
    MAX_EXCERPT_CHARS,
    build_excerpt,
    build_excerpt_at,
    locate_passage,
    normalise_whitespace,
)

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

# How much of a source's text is kept for later highlighting. Far below the
# model's own context cap: this is what a reading pane opens at, not the
# material the turn reasoned over, and an unbounded copy would turn the store
# into a second, unmanaged transcript.
MAX_PASSAGE_CHARS = 20_000

# Bound on how many sources one turn may record. A turn that reads two hundred
# files has not produced two hundred citations worth showing; past this the
# ledger states that it stopped counting rather than growing without limit.
MAX_SOURCES_PER_TURN = 40

#: Tools whose results are *material a turn read*, mapped to the source kind
#: the transcript labels them with. A tool that changes something, records a
#: plan, or answers about the runtime itself is deliberately absent: it
#: produced no material for the answer to have come from. That distinction is
#: declared once, per tool, in `raiker.models.tool_registry`.
TOOL_SOURCE_KINDS: dict[str, str] = dict(TOOL_SOURCE_KIND_BY_TOOL)

#: Attachment statuses that mean the file's material really entered the turn.
#: An image is deliberately absent: its bytes travel as an image block and its
#: context item is metadata, so there is no passage to open it at.
_INCLUDED_ATTACHMENT_STATUSES = frozenset({"included", "document_uploaded"})

# Resolution outcomes, shared with ``raiker.runtime.source_provenance`` so the
# inspector renders one vocabulary for both surfaces.
STATUS_RESOLVED = "resolved"
STATUS_NO_PROVENANCE = "no_provenance"
STATUS_SOURCE_DELETED = "source_deleted"
STATUS_SOURCE_CHANGED = "source_changed"
STATUS_UNSUPPORTED_SOURCE = "unsupported_source"
STATUS_NOT_AUTHORIZED = "not_authorized"


#: Most exchanges one cited search is allowed to name. A search that matched two
#: hundred is not a citation the owner is going to check; it is a wall of links.
MAX_SOURCE_ANCHORS = 20


@dataclass(frozen=True)
class SourceAnchor:
    """One exchange a cited call returned, as a coordinate that opens (BUG-245).

    Deliberately four fields and no text. The passage already carries what was
    read; this carries only where it was read *from*, so a chip can offer the
    link the panel's own heading was already describing in words.
    """

    session_id: str
    turn_id: str
    title: str = ""
    created_at: str = ""
    #: Which surface the exchange happened on, so the link opens where the work
    #: is. A Build conversation opened in Chat is the right coordinate and the
    #: wrong room.
    origin: str = "chat"

    def to_view(self) -> dict[str, str]:
        return {
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "title": self.title,
            "created_at": self.created_at,
            "origin": self.origin,
        }


def anchors_from_tool_result(
    tool_name: str, output: dict[str, Any] | None
) -> tuple[SourceAnchor, ...]:
    """The exchanges a cited call returned, read off the runtime's own result.

    Only `conversation_search` produces these today, and only for rows that
    carry both halves of a coordinate: a hit without a `turn_id` cannot be
    opened at the exchange, and offering a link that lands at the top of a
    conversation would be a worse answer than offering none.

    Pure and total. Anything unexpected — a non-dict row, a missing field, a
    result that is not a list — contributes nothing rather than raising: this
    runs inside recording a turn, and a malformed result must cost a link, never
    the turn.
    """
    if tool_name != "conversation_search" or not isinstance(output, dict):
        return ()
    anchors: list[SourceAnchor] = []
    seen: set[tuple[str, str]] = set()
    for item in output.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        session_id = _text(item.get("session_id"), 120)
        turn_id = _text(item.get("turn_id") or item.get("match_turn_id"), 120)
        if not session_id or not turn_id or (session_id, turn_id) in seen:
            continue
        seen.add((session_id, turn_id))
        anchors.append(
            SourceAnchor(
                session_id=session_id,
                turn_id=turn_id,
                title=_text(item.get("title"), 200),
                created_at=_text(item.get("created_at"), 40),
                origin=_text(item.get("origin"), 20) or "chat",
            )
        )
        if len(anchors) >= MAX_SOURCE_ANCHORS:
            break
    return tuple(anchors)


def anchors_from_json(raw: str) -> tuple[SourceAnchor, ...]:
    """Read anchors back out of storage, tolerating anything but a valid list."""
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(parsed, list):
        return ()
    anchors: list[SourceAnchor] = []
    for item in parsed[:MAX_SOURCE_ANCHORS]:
        if not isinstance(item, dict):
            continue
        session_id = str(item.get("session_id") or "")
        turn_id = str(item.get("turn_id") or "")
        if not session_id or not turn_id:
            continue
        anchors.append(
            SourceAnchor(
                session_id=session_id,
                turn_id=turn_id,
                title=str(item.get("title") or ""),
                created_at=str(item.get("created_at") or ""),
                origin=str(item.get("origin") or "chat"),
            )
        )
    return tuple(anchors)


@dataclass(frozen=True)
class TurnSource:
    """One thing a turn read, as the transcript and the model both see it."""

    source_id: str
    ordinal: int
    kind: str
    title: str
    locator: str = ""
    tool_name: str = ""
    detail: str = ""
    attachment_id: str = ""
    passage: str = ""
    #: BUG-245 — the exchanges this one call returned, as openable coordinates.
    #: Built from the tool result the runtime read, never from anything the model
    #: wrote. Empty for every source that is not a set of conversation hits.
    anchors: tuple[SourceAnchor, ...] = ()
    #: Set when the source is read back; the writer supplies it out of band.
    turn_id: str = ""

    @property
    def cite_as(self) -> str:
        """The marker the model is asked to put after a sentence it drew here."""
        return f"[{self.source_id}]"

    def to_view(self) -> dict[str, Any]:
        """The client-facing record. Deliberately without ``passage``.

        The chip needs a label and a locator; the passage is fetched only when
        the owner actually opens the source, which keeps a transcript's worth of
        read material out of every history load.
        """
        return {
            "source_id": self.source_id,
            "ordinal": self.ordinal,
            "kind": self.kind,
            "title": self.title,
            "locator": self.locator,
            "tool_name": self.tool_name,
            "detail": self.detail,
            "attachment_id": self.attachment_id,
            "turn_id": self.turn_id,
            "openable": bool(self.passage) or bool(self.attachment_id),
        }

    def to_row(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "ordinal": self.ordinal,
            "kind": self.kind,
            "title": self.title,
            "locator": self.locator,
            "tool_name": self.tool_name,
            "detail": self.detail,
            "attachment_id": self.attachment_id,
            "passage": self.passage,
            "anchors_json": (
                json.dumps([anchor.to_view() for anchor in self.anchors])
                if self.anchors
                else ""
            ),
        }


@dataclass(frozen=True)
class SourceDraft:
    """A source before it has been given its id. Pure data, no I/O."""

    kind: str
    title: str
    locator: str = ""
    tool_name: str = ""
    detail: str = ""
    attachment_id: str = ""
    passage: str = ""
    anchors: tuple[SourceAnchor, ...] = ()


def _text(value: Any, limit: int = 400) -> str:
    return str(value or "").strip()[:limit]


def _count_detail(count: Any, noun: str) -> str:
    try:
        n = int(count)
    except (TypeError, ValueError):
        return ""
    return f"{n} {noun}" if n != 1 else f"1 {noun[:-1] if noun.endswith('s') else noun}"


def source_from_tool_result(
    tool_name: str, arguments: dict[str, Any], output: dict[str, Any] | None
) -> SourceDraft | None:
    """The source one executed tool call produced, or ``None``.

    Pure and total: an unmapped tool, a failed call, and a call that returned
    nothing readable all answer ``None``, because a citation that points at a
    call which produced nothing is worse than no citation.
    """
    kind = TOOL_SOURCE_KINDS.get(tool_name)
    if kind is None or not isinstance(output, dict):
        return None
    if str(output.get("status", "")) != "success":
        return None

    args = arguments if isinstance(arguments, dict) else {}
    # Connector, web and subagent results carry their material under `content`;
    # the local read tools carry it under `text` or as a structured listing.
    passage = _passage_for(tool_name, output)

    if tool_name == "read_file":
        path = _text(output.get("path") or args.get("path"))
        return SourceDraft(
            kind=kind, title=path or "file", locator=path, tool_name=tool_name,
            detail="read in full" if not output.get("truncated") else "read (truncated)",
            passage=passage,
        )
    if tool_name == "list_directory":
        path = _text(output.get("path") or args.get("path")) or "."
        return SourceDraft(
            kind=kind, title=path, locator=path, tool_name=tool_name,
            detail=_count_detail(len(output.get("entries", []) or []), "entries"),
            passage=passage,
        )
    if tool_name in ("grep", "glob"):
        query = _text(args.get("query") or args.get("pattern"))
        return SourceDraft(
            kind=kind,
            title=f"{'Search' if tool_name == 'grep' else 'File match'}: {query}" if query else tool_name,
            locator=_text(args.get("path") or args.get("pattern")),
            tool_name=tool_name,
            detail=_count_detail(output.get("count", len(output.get("matches", output.get("paths", [])) or [])), "matches"),
            passage=passage,
        )
    if tool_name == "diff_files":
        before, after = _text(args.get("before_path")), _text(args.get("after_path"))
        return SourceDraft(
            kind=kind, title=f"Diff: {before} → {after}", locator=after,
            tool_name=tool_name, passage=passage,
        )
    if tool_name in ("git_status", "git_diff", "git_log"):
        return SourceDraft(
            kind=kind, title=f"Repository: {tool_name.replace('_', ' ')}",
            locator=tool_name, tool_name=tool_name, passage=passage,
        )
    if tool_name == "code_map_search":
        query = _text(args.get("query"))
        return SourceDraft(
            kind=kind,
            title=f"Code map: {query}" if query else "Code map",
            locator=_text(output.get("repository")),
            tool_name=tool_name,
            detail=_count_detail(output.get("count", 0), "declarations"),
            passage=passage,
        )
    # MEM-08 — the owner's own past conversations. `conversation_search` has
    # declared `source_kind="conversation"` since RAIKER-2020 and produced no
    # source at all, so an answer drawn from a chat three years old cited
    # nothing: the one class of material whose provenance the owner can check
    # for themselves was the one the ledger did not record. The locator is the
    # conversation when the call stayed inside one, which is the case where a
    # coordinate names something exact.
    if tool_name == "conversation_search":
        results = output.get("results", []) or []
        query = _text(args.get("query"))
        scoped = _text(args.get("session_id"), 120)
        return SourceDraft(
            kind=kind,
            title=f"Past conversations: {query}" if query else "Past conversations",
            locator=scoped,
            tool_name=tool_name,
            detail=_count_detail(output.get("count", len(results)), "exchanges"),
            passage=passage,
            # BUG-245 — the passage names each exchange; these make each one
            # openable at that exchange rather than only readable as a heading.
            anchors=anchors_from_tool_result(tool_name, output),
        )
    # The other half of the code map. `code_map_search` says where a name is
    # declared and has always been citable; this says where it is *used*, and
    # was declared alongside it and dropped in the same silence.
    if tool_name == "code_map_references":
        name = _text(args.get("name"), 200)
        return SourceDraft(
            kind=kind,
            title=f"Used by: {name}" if name else "Code map references",
            locator=_text(output.get("repository")),
            tool_name=tool_name,
            detail=_count_detail(output.get("count", 0), "references"),
            passage=passage,
        )
    # The governed graph read. Every edge it returns names the approved memory
    # it came from, which makes it the *most* citable read in the set and made
    # its absence from the ledger the least defensible.
    if tool_name == "knowledge_graph":
        action = _text(args.get("action"), 40) or _text(output.get("action"), 40)
        anchor = _text(args.get("query") or args.get("entity_id") or args.get("locator"), 200)
        return SourceDraft(
            kind=kind,
            title=f"Memory graph: {anchor}" if anchor else "Memory graph",
            locator=_text(output.get("resolved_from") or args.get("locator"), 200),
            tool_name=tool_name,
            detail=_count_detail(
                output.get("count", 0),
                "entities" if action == "entities" else "passages" if action == "passages" else "edges",
            ),
            passage=passage,
        )
    if tool_name in ("memory_search", "memory_list"):
        results = output.get("results", []) or []
        query = _text(args.get("query"))
        return SourceDraft(
            kind=kind,
            title=f"Memory: {query}" if query else "Memory",
            locator=_text(args.get("scope")),
            tool_name=tool_name,
            detail=_count_detail(output.get("count", len(results)), "memories"),
            passage=passage,
        )
    if tool_name == "memory_get":
        return SourceDraft(
            kind=kind, title=f"Memory {_text(output.get('memory_id'), 60)}",
            locator=_text(output.get("memory_id"), 60), tool_name=tool_name,
            passage=passage,
        )
    if tool_name == "skill_load":
        name = _text(args.get("name"), 120)
        return SourceDraft(
            kind=kind, title=f"Skill: {name}" if name else "Skill", locator=name,
            tool_name=tool_name, passage=passage,
        )
    if tool_name == "github_read":
        repo, number = _text(args.get("repo"), 200), _text(args.get("number"), 20)
        return SourceDraft(
            kind=kind,
            title=_text(output.get("title")) or f"{repo}#{number}",
            locator=f"{repo}#{number}" if repo else "",
            tool_name=tool_name, passage=passage,
        )
    if tool_name == "gmail_read":
        return SourceDraft(
            kind=kind, title=_text(output.get("subject")) or "Email",
            locator=_text(output.get("message_id"), 200), tool_name=tool_name,
            passage=passage,
        )
    if tool_name == "gcal_read":
        return SourceDraft(
            kind=kind, title=_text(output.get("title")) or "Calendar",
            locator=_text(output.get("event_id") or output.get("calendar_id"), 200),
            tool_name=tool_name, passage=passage,
        )
    if tool_name == "slack_read":
        channel = _text(args.get("channel"), 200)
        return SourceDraft(
            kind=kind, title=f"Slack: {channel}" if channel else "Slack",
            locator=channel, tool_name=tool_name, passage=passage,
        )
    if tool_name == "connector_read":
        connector = _text(args.get("connector_id"), 120)
        operation = _text(args.get("operation_id"), 120)
        return SourceDraft(
            kind=kind, title=f"{connector} · {operation}".strip(" ·") or "Connector",
            locator=f"{connector}/{operation}".strip("/"), tool_name=tool_name,
            passage=passage,
        )
    if tool_name == "web_fetch":
        url = _text(output.get("final_url") or output.get("url") or args.get("url"), 500)
        return SourceDraft(
            kind=kind, title=_text(output.get("title")) or url or "Web page",
            locator=url, tool_name=tool_name, passage=passage,
        )
    if tool_name == "web_search":
        query = _text(args.get("query"))
        return SourceDraft(
            kind=kind, title=f"Web search: {query}" if query else "Web search",
            locator="", tool_name=tool_name,
            detail=_count_detail(output.get("result_count", 0), "results"),
            passage=passage,
        )
    if tool_name == "spawn_subagent":
        name = _text(args.get("name") or output.get("name"), 120)
        return SourceDraft(
            kind=kind, title=f"Subagent: {name}" if name else "Subagent",
            locator=name, tool_name=tool_name,
            detail=_count_detail(output.get("steps_executed", 0), "steps"),
            passage=passage,
        )
    return None


def _passage_for(tool_name: str, output: dict[str, Any]) -> str:
    """The bounded text this result handed the model, for later highlighting."""
    for key in ("content", "text", "output", "digest"):
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            return value[:MAX_PASSAGE_CHARS]
    if tool_name == "list_directory":
        entries = [str(entry) for entry in (output.get("entries", []) or [])]
        return "\n".join(entries)[:MAX_PASSAGE_CHARS]
    # MEM-08 — a recalled exchange without its conversation and its date is not
    # something the owner can check. The heading is built from the ledger's own
    # result row, so it can only ever name a conversation the call really
    # returned.
    if tool_name == "conversation_search":
        blocks: list[str] = []
        for item in output.get("results", []) or []:
            if not isinstance(item, dict):
                continue
            heading = " · ".join(
                part
                for part in (
                    str(item.get("title") or "").strip(),
                    str(item.get("created_at") or "")[:10],
                )
                if part
            )
            body = str(item.get("text") or item.get("matched") or "").strip()
            blocks.append(f"{heading}\n{body}".strip() if heading else body)
        joined = "\n\n".join(block for block in blocks if block)
        if joined:
            return joined[:MAX_PASSAGE_CHARS]
    # The graph read carries its material under `edges` or `entities` rather
    # than `results`, so without this its source recorded a passage of nothing.
    if tool_name == "knowledge_graph":
        graph_lines: list[str] = []
        for edge in output.get("edges", []) or []:
            if isinstance(edge, dict):
                graph_lines.append(
                    f"{edge.get('subject', '')} {edge.get('predicate', '')} {edge.get('object', '')}".strip()
                )
        for entity in output.get("entities", []) or []:
            if isinstance(entity, dict):
                graph_lines.append(f"{entity.get('name', '')} ({entity.get('type', '')})".strip())
        joined = "\n".join(line for line in graph_lines if line)
        if joined:
            return joined[:MAX_PASSAGE_CHARS]
    if tool_name == "code_map_references":
        reference_lines = [
            f"{item.get('path', '')}:{item.get('line', '')}  {item.get('text', '')}".strip()
            for item in (output.get("results", []) or [])
            if isinstance(item, dict)
        ]
        joined = "\n".join(line for line in reference_lines if line)
        if joined:
            return joined[:MAX_PASSAGE_CHARS]
    results = output.get("results")
    if isinstance(results, list) and results:
        lines: list[str] = []
        for item in results:
            if isinstance(item, dict):
                lines.append(
                    str(item.get("text") or item.get("snippet") or item.get("title") or "")
                )
        joined = "\n\n".join(line for line in lines if line)
        if joined:
            return joined[:MAX_PASSAGE_CHARS]
    return ""


def attachment_sources(items: list[dict[str, Any]]) -> list[tuple[str, SourceDraft]]:
    """Sources for the files the owner attached to this turn (C4).

    An attached document is material the turn read just as surely as a tool
    result is — it is simply read by the context gatherer rather than by a call.
    Only attachments that really entered the turn become sources: one that was
    denied, dropped, or held back as metadata contributed nothing to the answer
    and must not be citable.

    Each draft is returned with the context item id it came from, so the caller
    can print the marker on the very block whose text it names.
    """
    drafts: list[tuple[str, SourceDraft]] = []
    for item in items:
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        if str(metadata.get("attachment_status", "")) not in _INCLUDED_ATTACHMENT_STATUSES:
            continue
        attachment_id = _text(metadata.get("attachment_id"), 120)
        path = _text(metadata.get("path"), 500)
        filename = _text(metadata.get("filename"), 300)
        title = filename or path or _text(item.get("title"), 300)
        if not title:
            continue
        drafts.append((
            _text(item.get("item_id"), 120),
            SourceDraft(
                kind="attachment",
                title=title,
                locator=path or attachment_id,
                tool_name="attachment",
                detail="attached to this message",
                attachment_id=attachment_id,
                passage=str(item.get("content") or "")[:MAX_PASSAGE_CHARS],
            ),
        ))
    return drafts


def record_sources(
    store: SQLiteStore,
    *,
    session_id: str,
    turn_id: str,
    principal_id: str,
    drafts: list[SourceDraft],
    starting_ordinal: int,
) -> list[TurnSource]:
    """Give *drafts* their ids, persist them, and return them.

    ``starting_ordinal`` is how many sources this turn already had, so a resumed
    turn continues the numbering rather than re-using ``s1`` for something else.
    """
    recorded: list[TurnSource] = []
    ordinal = starting_ordinal
    for draft in drafts:
        if ordinal >= MAX_SOURCES_PER_TURN:
            break
        ordinal += 1
        recorded.append(
            TurnSource(
                source_id=f"s{ordinal}",
                ordinal=ordinal,
                kind=draft.kind,
                title=draft.title,
                locator=draft.locator,
                tool_name=draft.tool_name,
                detail=draft.detail,
                attachment_id=draft.attachment_id,
                passage=draft.passage,
                anchors=draft.anchors,
            )
        )
    if recorded:
        store.record_turn_sources(
            session_id=session_id,
            turn_id=turn_id,
            principal_id=principal_id,
            rows=[source.to_row() for source in recorded],
        )
    return recorded


def load_sources(
    store: SQLiteStore, session_id: str, principal_id: str, turn_id: str | None = None
) -> list[TurnSource]:
    """This conversation's recorded sources, oldest first."""
    return [
        source_from_row(row)
        for row in store.load_turn_sources(session_id, principal_id, turn_id)
    ]


def load_source(
    store: SQLiteStore, session_id: str, turn_id: str, source_id: str, principal_id: str
) -> TurnSource | None:
    """One recorded source, or ``None`` when this account has no such row."""
    row = store.load_turn_source(session_id, turn_id, source_id, principal_id)
    return source_from_row(row) if row is not None else None


def source_from_row(row: dict[str, Any]) -> TurnSource:
    return TurnSource(
        source_id=str(row.get("source_id", "")),
        ordinal=int(row.get("ordinal", 0) or 0),
        kind=str(row.get("kind", "")),
        title=str(row.get("title", "")),
        locator=str(row.get("locator", "")),
        tool_name=str(row.get("tool_name", "")),
        detail=str(row.get("detail", "")),
        attachment_id=str(row.get("attachment_id", "")),
        passage=str(row.get("passage", "")),
        anchors=anchors_from_json(str(row.get("anchors_json", "") or "")),
        turn_id=str(row.get("turn_id", "")),
    )


def citation_prompt() -> str:
    """The standing instruction that turns markers into a habit.

    Sent once per turn, ahead of the work: a model told to cite only after it
    has already written the answer will not go back and do it.
    """
    return (
        "Citing what you used. Every tool result and attached file you receive in this "
        "conversation carries a `cite_as` marker such as `[s1]`. When a statement in your "
        "answer rests on one of them, put that marker at the end of the sentence — for "
        "example: The renewal is on 14 March [s2]. Use only markers you were actually "
        "given in this turn; never invent one, never cite a marker for a claim it does "
        "not support, and do not cite your own general knowledge."
    )


#: Longest answer sentence accepted as a locating quote, and the shortest
#: fragment of one worth trying. Below the floor a match says nothing — "the
#: renewal" occurs in half a contract — so a short fragment is refused rather
#: than used to mark something arbitrary.
MAX_QUOTE_CHARS = 600
MIN_QUOTE_FRAGMENT_CHARS = 24


def locate_answer_quote(document: str, quote: str) -> tuple[int, int]:
    """Where the answer's own words sit in *document*, as ``(start, length)``.

    ``(-1, 0)`` when they are not there. This is the one thing that makes "open
    the passage it used" answerable for a whole-file read: the source ledger
    knows the turn read the file, and the sentence carrying the citation is the
    only statement of *which part of it the answer rests on*.

    It is a search, and it is honest about being one:

    * **Exact runs only.** Matching is the same whitespace- and case-insensitive
      exactness :func:`locate_passage` uses. Nothing is scored, ranked or
      approximated — a paraphrase simply does not match, and the caller shows
      the source without a highlight rather than marking something near it.
    * **Longest fragment wins.** A model rarely quotes a whole sentence back, so
      the sentence is also tried in fragments split on its own punctuation. The
      longest fragment that occurs verbatim is the match, which is the most
      specific claim the text supports.
    * **A short fragment is refused.** Below
      :data:`MIN_QUOTE_FRAGMENT_CHARS` a hit is not evidence of anything.
    """
    # The marker itself, and the inline emphasis a model wraps a figure in
    # ("renews on **14 March 2029**"), are the model's presentation rather than
    # the source's words. Dropping them from the needle only ever *narrows* what
    # will match: the haystack is untouched, so nothing can be marked that the
    # source does not literally contain.
    cleaned = re.sub(r"\[s\d{1,3}\]", " ", quote)
    cleaned = re.sub(r"[*_`~]", "", cleaned)[:MAX_QUOTE_CHARS]
    if not document or not normalise_whitespace(cleaned):
        return (-1, 0)

    start, length = locate_passage(document, cleaned)
    if start >= 0:
        return (start, length)

    fragments = [
        fragment
        for fragment in re.split(r"[.;:!?\n]+|,\s+", cleaned)
        if len(normalise_whitespace(fragment)) >= MIN_QUOTE_FRAGMENT_CHARS
    ]
    best: tuple[int, int] = (-1, 0)
    for fragment in sorted(fragments, key=lambda text: len(normalise_whitespace(text)), reverse=True):
        start, length = locate_passage(document, fragment)
        if start >= 0:
            best = (start, length)
            break
    return best


def resolve_source_excerpt(
    store: SQLiteStore,
    *,
    workspace_root: str | Path,
    source: TurnSource,
    session_id: str,
    owner_principal_id: str,
    quote: str = "",
) -> dict[str, Any]:
    """Open one source at the passage the turn used (C4).

    The four honest answers ``source_provenance`` established apply here too. An
    attachment is resolved through the attachment reader, so its authorisation
    is re-checked against this caller now rather than trusted from capture time;
    a workspace file is re-read and the stored passage located inside it, so a
    file that has since changed reports ``source_changed`` instead of
    highlighting something near where the passage used to be; and a source whose
    material lives outside Raiker (a web page, an email, a connector response) is
    shown as the bounded text that actually reached the model, which is the only
    copy of it Raiker is entitled to claim.
    """
    def answer(status: str, **fields: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": status,
            "kind": source.kind,
            "title": source.title,
            "excerpt": "",
            "highlight_start": -1,
            "highlight_length": 0,
            "session_id": session_id,
            "turn_id": source.turn_id,
            "attachment_id": source.attachment_id,
            "truncated": False,
            "resolution_method": "",
            # BUG-245 — served with the passage rather than with the chip. The
            # strip needs a label; only the open panel needs the coordinates,
            # and putting them in `to_view` would carry every search's hits into
            # every history load.
            "anchors": [anchor.to_view() for anchor in source.anchors],
        }
        payload.update(fields)
        return payload

    if source.attachment_id:
        from raiker.runtime.attachment_preview import AttachmentPreviewService

        preview = AttachmentPreviewService(store).get(
            session_id, source.attachment_id, owner_principal_id
        )
        if preview is None:
            # Indistinguishable, on purpose, from "you may not read this": the
            # attachment reader answers None for both and guessing between them
            # here would leak which one it was.
            return answer(STATUS_NOT_AUTHORIZED)
        if preview.kind in ("pdf", "image", "table", "unavailable"):
            # There is a file and this account may read it — there is simply no
            # text offset to open it at. A different answer from "gone".
            return answer(
                STATUS_UNSUPPORTED_SOURCE, kind="file", title=preview.filename,
            )
        return _text_answer(
            answer, preview.text, source.passage, quote, kind="file",
            title=preview.filename,
        )

    if source.kind in ("file", "repository") and source.tool_name in (
        "read_file", "diff_files",
    ):
        from raiker.tools.filesystem import FilesystemSafetyError, read_file

        try:
            result = read_file(workspace_root, source.locator)
        except FilesystemSafetyError:
            return answer(STATUS_NOT_AUTHORIZED)
        except OSError:
            return answer(STATUS_SOURCE_DELETED, kind="file")
        if result.get("status") != "success":
            return answer(STATUS_SOURCE_DELETED, kind="file")
        return _text_answer(
            answer, str(result.get("text", "")), source.passage, quote, kind="file",
            title=source.title,
        )

    if not source.passage:
        return answer(STATUS_NO_PROVENANCE)
    # Material Raiker does not own a second copy of: what reached the model is
    # what can be shown. When the citation carried the sentence it terminated,
    # that sentence's own words locate the run inside it; otherwise the whole of
    # what arrived is shown rather than a guess at which part mattered.
    excerpt = source.passage[:MAX_EXCERPT_CHARS]
    if quote:
        start, length = locate_answer_quote(excerpt, quote)
        if start >= 0:
            return answer(
                STATUS_RESOLVED, excerpt=excerpt, highlight_start=start,
                highlight_length=length,
                truncated=len(source.passage) > len(excerpt),
                resolution_method="answer_quote",
            )
    return answer(
        STATUS_RESOLVED,
        excerpt=excerpt,
        highlight_start=0,
        highlight_length=len(excerpt),
        truncated=len(source.passage) > len(excerpt),
        resolution_method="recorded_passage",
    )


def _text_answer(
    answer: Any,
    document: str,
    passage: str,
    quote: str = "",
    *,
    kind: str,
    title: str,
) -> dict[str, Any]:
    """Answer with *document*, marked at the part of it the turn actually used.

    Two different questions, answered in the order that makes the pane useful:

    1. **Which part does this citation rest on?** Only the sentence carrying the
       marker knows, so when the caller supplied it, its own words locate the
       run (:func:`locate_answer_quote`). This is what makes a whole-file read
       openable at something narrower than the whole file.
    2. **Where is the passage the tool returned?** For a narrower result — a
       match, an excerpt — the stored passage is located directly, and a
       document that no longer contains it reports ``source_changed`` rather
       than marking something near where it used to be.
    """
    if quote:
        start, length = locate_answer_quote(document, quote)
        if start >= 0:
            excerpt, offset, marked, truncated = build_excerpt_at(document, start, length)
            return answer(
                STATUS_RESOLVED, kind=kind, title=title, excerpt=excerpt,
                highlight_start=offset, highlight_length=marked, truncated=truncated,
                resolution_method="answer_quote",
            )
    if not passage.strip():
        head = document[:4_000]
        return answer(
            STATUS_RESOLVED if document else STATUS_SOURCE_DELETED,
            kind=kind, title=title, excerpt=head, truncated=len(document) > len(head),
        )
    # A whole-file read has the file as its passage; locating it inside itself
    # would mark every character, which is a highlight that says nothing. Show
    # the document and state that all of it was read.
    if normalise_whitespace(passage) == normalise_whitespace(document):
        head = document[:4_000]
        return answer(
            STATUS_RESOLVED, kind=kind, title=title, excerpt=head,
            truncated=len(document) > len(head), resolution_method="whole_source",
        )
    start, length = locate_passage(document, passage)
    if start < 0:
        excerpt, _s, _l, truncated = build_excerpt(document, passage)
        return answer(
            STATUS_SOURCE_CHANGED, kind=kind, title=title, excerpt=excerpt,
            truncated=truncated,
        )
    excerpt, offset, marked, truncated = build_excerpt(document, passage)
    return answer(
        STATUS_RESOLVED, kind=kind, title=title, excerpt=excerpt,
        highlight_start=offset, highlight_length=marked, truncated=truncated,
        resolution_method="matching_text",
    )
