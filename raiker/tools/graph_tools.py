"""Model-facing reads over the governed memory knowledge graph (MEM-13).

Raiker stored a knowledge graph — entities, typed relationships between them,
and the approved memory that is each edge's evidence — and no model could reach
it. It was drawn on the Knowledge Map page for a person to look at, and the
graph leg of hybrid retrieval consumed it internally, but a turn could not ask
*"what is related to this, and how"*. Chat and Build could search memory and
never traverse it.

Four actions, because they answer four different questions:

* ``entities`` — *what does this workspace know about, by this name?* The
  discovery step. A model that has read "the NAS" in a memory needs an
  ``entity_id`` before it can walk anywhere.
* ``neighbors`` — *what is this entity related to, and on whose authority?*
  Each edge carries its predicate, its confidence, and the id of the approved
  memory that evidences it, so a claim reached through the graph can be traced
  back to something the owner approved rather than asserted from a topology.
* ``references`` — *what work cited this source, and what was cited beside it?*
* ``passages`` — *what did this source actually say?*

The last two exist because the first two are a graph of **claims** and a model
building an understanding of a workspace also needs the graph of **material**.
Obsidian's metadata cache is the reference model here, and Raiker turned out to
already hold every fact it exposes — ``turn_sources`` records one row per source
a turn used, carrying the target's locator and the bounded passage that reached
the model, which is ``resolvedLinks``, ``getBacklinksForFile`` and a block
reference in one table read only ever forwards. Three things were borrowed
deliberately:

* **A link is counted, not just present.** Obsidian reports how many references
  one document holds to another because one passing mention and nine are
  different facts; ``references`` returns ``refs`` per edge for the same reason.
* **Unresolved references are surfaced, not dropped.** ``unresolvedLinks`` is a
  first-class half of the cache. A citation whose file has since been deleted is
  reported as ``unresolved`` rather than quietly omitted, because "the answer
  rested on something that is gone" is the more useful of the two facts.
* **The reference resolves to a passage, not a document.** A block reference
  points at a paragraph. ``passages`` returns the stored text the source really
  contributed — the copy that reached the model, not whatever the file says
  today, which is the only version a later turn can honestly quote.

Where Raiker's graph differs from a vault's: nobody wrote these links. A vault's
edges are authored, and one work session's citations are evidence that some work
needed both of two things — a weaker claim, so ``related`` edges report the
number of conversations behind them rather than appearing as bare links.

**This tool grants nothing.** Every edge is already filtered by
``list_memory_entity_neighborhood`` to evidence that is active, non-archived,
non-expired, non-superseded, search-enabled, and not sensitivity-classified as
secret- or credential-like — the same filter the retrieval legs use. Owner
scoping is enforced in the query, not here. ``references`` and ``passages`` read
only material that already reached a turn this owner ran; they open nothing new,
re-run no tool, and re-read no file.

What it returns is untrusted owner data. An edge saying *X trusts Y* is a record
that someone once approved that sentence, not an instruction to act on it, and a
passage is a quotation from a document, not a message to the model.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import FilesystemSafetyError, resolve_workspace_path

#: Bounds. A graph read is a context contribution, not a report: an entity with
#: four hundred edges would push everything else out of the window, and the
#: model can always ask again about a specific neighbour.
MAX_ENTITIES = 25
MAX_EDGES = 50

#: Passages are text, so they are bounded twice: by how many come back and by
#: how long each may be. The stored passage is already capped at capture time;
#: this is the second cap, because five long ones still add up.
MAX_PASSAGES = 5
MAX_PASSAGE_CHARS = 1200

#: Tools whose locator really is a workspace path, and so can be checked for
#: existence. The same pair ``resolve_source_excerpt`` re-reads from disk, and
#: for the same reason: ``git_status`` also records kind ``repository``, but its
#: locator is the tool's own name, and testing that for a file would report a
#: deleted document every time. Everything else — a URL, a Slack channel, a
#: connector operation — lives outside Raiker and is reported as ``external``
#: rather than guessed at. Calling a web page "unresolved" because it is not on
#: this disk would be a claim about the internet, which is not Raiker's to make.
_LOCAL_SOURCE_TOOLS = frozenset({"read_file", "diff_files", "list_directory"})
_LOCAL_SOURCE_KINDS = frozenset({"file", "repository"})


def knowledge_graph(
    workspace_root: str | Path,
    action: str,
    *,
    query: str = "",
    entity_id: str = "",
    locator: str = "",
    session_id: str = "",
    scope: str | None = None,
    max_results: int = MAX_EDGES,
    owner_principal_id: str | None = None,
) -> dict[str, Any]:
    store = SQLiteStore(workspace_root)
    limit = max(1, min(int(max_results), MAX_EDGES))

    if action == "entities":
        if not query.strip():
            return _failed("empty_query", "A search term is required to find entities.")
        rows = store.match_memory_entities(query, limit=min(limit, MAX_ENTITIES))
        return {
            "status": "success",
            "action": "entities",
            "count": len(rows),
            "entities": [
                {
                    "entity_id": str(row["entity_id"]),
                    "name": str(row["display_name"]),
                    "type": str(row["entity_type"]),
                }
                for row in rows
            ],
            "trust_label": "untrusted_memory_data",
        }

    if action == "neighbors":
        anchor = entity_id.strip()
        resolved_from = ""
        if not anchor:
            # Resolving a name here rather than making the model call
            # `entities` first is the difference between a tool it can use and
            # one it has to be taught a protocol for. The resolution is
            # reported, so an answer is never attributed to an entity the
            # caller did not actually name.
            if not query.strip():
                return _failed(
                    "missing_anchor", "Pass entity_id, or query to resolve one by name."
                )
            matches = store.match_memory_entities(query, limit=1)
            if not matches:
                return {
                    "status": "success",
                    "action": "neighbors",
                    "count": 0,
                    "resolved_from": query,
                    "entity": None,
                    "edges": [],
                    "trust_label": "untrusted_memory_data",
                }
            anchor = str(matches[0]["entity_id"])
            resolved_from = str(matches[0]["display_name"])

        rows = store.list_memory_entity_neighborhood(
            anchor, scope=scope, owner_principal_id=owner_principal_id
        )
        edges = [
            {
                "subject": str(row["subject_name"]),
                "predicate": str(row["predicate"]),
                "object": str(row["object_name"]),
                # The whole point of the graph being *governed*: every edge
                # names the approved memory it came from, so the model can read
                # the sentence rather than trust the shape.
                "evidence_memory_id": str(row["evidence_memory_id"]),
                "confidence": round(float(row["confidence"]), 6),
                "direction": (
                    "outgoing" if str(row["subject_entity_id"]) == anchor else "incoming"
                ),
            }
            for row in rows[:limit]
        ]
        return {
            "status": "success",
            "action": "neighbors",
            "entity": {"entity_id": anchor, "name": resolved_from},
            "resolved_from": resolved_from,
            "count": len(edges),
            "truncated": len(rows) > limit,
            "edges": edges,
            "trust_label": "untrusted_memory_data",
        }

    if action == "references":
        return _references(
            store,
            workspace_root,
            locator=locator.strip(),
            session_id=session_id.strip(),
            limit=limit,
            owner_principal_id=owner_principal_id,
        )

    if action == "passages":
        return _passages(
            store, locator=locator.strip(), limit=limit, owner_principal_id=owner_principal_id
        )

    return _failed(
        "unknown_action",
        f"Unknown action '{action}'. Use entities, neighbors, references or passages.",
    )


def _references(
    store: SQLiteStore,
    workspace_root: str | Path,
    *,
    locator: str,
    session_id: str,
    limit: int,
    owner_principal_id: str | None,
) -> dict[str, Any]:
    """The citation ledger read backwards and sideways.

    Anchored on a *source*, it answers "which work used this, and what did that
    work use alongside it". Anchored on a *conversation*, it answers "what did
    this piece of work rest on" — Obsidian's outgoing links, for a session.
    """
    if session_id and not locator:
        # A source with no locator — a web search, say — is a real citation with
        # nothing to point at, so it is dropped from a *reference* read rather
        # than returned as an edge to nowhere. Dropped before the count, or the
        # count would describe a longer list than the caller receives.
        rows = [
            row
            for row in store.list_source_outlinks(
                session_id, principal_id=owner_principal_id, limit=limit
            )
            if str(row["locator"]).strip()
        ]
        return {
            "status": "success",
            "action": "references",
            "anchor": {"kind": "session", "session_id": session_id},
            "count": len(rows),
            "outbound": [
                {
                    "locator": str(row["locator"]),
                    "title": str(row["title"] or ""),
                    "kind": str(row["kind"] or ""),
                    "tool_name": str(row["tool_name"] or ""),
                    "refs": int(row["refs"]),
                    "turns": int(row["turns"]),
                    # Whether `passages` has anything to hand back for this
                    # target, so the model can tell a readable reference from a
                    # bare mention without spending a call to find out.
                    "has_passages": int(row["passages"] or 0) > 0,
                    "last_referenced_at": str(row["last_referenced_at"] or ""),
                    "resolution": reference_resolution(
                        workspace_root,
                        kind=str(row["kind"] or ""),
                        locator=str(row["locator"]),
                        attachment_id=str(row["attachment_id"] or ""),
                        tool_name=str(row["tool_name"] or ""),
                    ),
                }
                for row in rows
                if str(row["locator"]).strip()
            ],
            "trust_label": "untrusted_source_data",
        }

    if not locator:
        return _failed(
            "missing_anchor",
            "Pass locator to see what cited a source, or session_id to see what a conversation cited.",
        )

    backlinks = store.list_source_backlinks(
        locator, principal_id=owner_principal_id, limit=limit
    )
    related = store.list_co_cited_sources(
        locator, principal_id=owner_principal_id, limit=limit
    )
    kind = str(backlinks[0]["kind"] or "") if backlinks else ""
    title = str(backlinks[0]["title"] or "") if backlinks else ""
    tool_name = str(backlinks[0]["tool_name"] or "") if backlinks else ""
    return {
        "status": "success",
        "action": "references",
        "anchor": {
            "kind": "source",
            "locator": locator,
            "title": title,
            "source_kind": kind,
            "resolution": reference_resolution(
                workspace_root,
                kind=kind,
                locator=locator,
                attachment_id="",
                tool_name=tool_name,
            ),
        },
        "count": len(backlinks),
        # One entry per citing conversation, carrying how many references it
        # holds — the shape `getBacklinksForFile` returns, and the reason a
        # count is worth keeping: nine references and one are different facts.
        "backlinks": [
            {
                "session_id": str(row["session_id"]),
                "session_title": str(row["session_title"] or ""),
                "surface": str(row["session_origin"] or ""),
                "refs": int(row["refs"]),
                "turns": int(row["turns"]),
                "has_passages": int(row["passages"] or 0) > 0,
                "last_referenced_at": str(row["last_referenced_at"] or ""),
            }
            for row in backlinks
        ],
        "related": [
            {
                "locator": str(row["locator"]),
                "title": str(row["title"] or ""),
                "kind": str(row["kind"] or ""),
                # Named for what it is. Nobody authored this edge: it says some
                # work needed both sources, and the number of conversations is
                # the whole of the evidence for it.
                "shared_sessions": int(row["shared_sessions"]),
                "refs": int(row["refs"]),
            }
            for row in related
        ],
        "trust_label": "untrusted_source_data",
    }


def _passages(
    store: SQLiteStore, *, locator: str, limit: int, owner_principal_id: str | None
) -> dict[str, Any]:
    if not locator:
        return _failed("missing_anchor", "A locator is required to read stored passages.")
    rows = store.list_source_passages(
        locator, principal_id=owner_principal_id, limit=min(limit, MAX_PASSAGES)
    )
    return {
        "status": "success",
        "action": "passages",
        "locator": locator,
        "count": len(rows),
        "passages": [
            {
                "session_id": str(row["session_id"]),
                "turn_id": str(row["turn_id"]),
                "source_id": str(row["source_id"]),
                "title": str(row["title"] or ""),
                "kind": str(row["kind"] or ""),
                "tool_name": str(row["tool_name"] or ""),
                "captured_at": str(row["created_at"] or ""),
                # Said plainly, because it is the difference between a quotation
                # and a claim about the file: this is what the source handed a
                # turn at that moment. The file may have changed since.
                "text": str(row["passage"] or "")[:MAX_PASSAGE_CHARS],
                "truncated": len(str(row["passage"] or "")) > MAX_PASSAGE_CHARS,
            }
            for row in rows
        ],
        "note": (
            "Each passage is the text this source handed an earlier turn, as it "
            "was then. Re-read the source if the current contents matter."
        ),
        "trust_label": "untrusted_source_data",
    }


def reference_resolution(
    workspace_root: str | Path,
    *,
    kind: str,
    locator: str,
    attachment_id: str,
    tool_name: str,
) -> str:
    """Does this reference still point at something? ``unresolvedLinks``, ported.

    Three answers, not two. ``external`` is the honest one for a web page or a
    connector response: Raiker never held the target, so its absence from disk
    says nothing about whether it exists.
    """
    if attachment_id:
        return "attachment"
    if (
        kind not in _LOCAL_SOURCE_KINDS
        or tool_name not in _LOCAL_SOURCE_TOOLS
        or not locator.strip()
    ):
        return "external"
    try:
        resolved = resolve_workspace_path(workspace_root, locator)
    except (FilesystemSafetyError, OSError, ValueError):
        return "external"
    try:
        return "resolved" if resolved.exists() else "unresolved"
    except OSError:
        return "unresolved"


def _failed(kind: str, message: str) -> dict[str, Any]:
    return {"status": "failed", "error": {"type": kind, "message": message}}
