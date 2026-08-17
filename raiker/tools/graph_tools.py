"""Model-facing reads over the governed memory knowledge graph (MEM-13).

Raiker stored a knowledge graph — entities, typed relationships between them,
and the approved memory that is each edge's evidence — and no model could reach
it. It was drawn on the Knowledge Map page for a person to look at, and the
graph leg of hybrid retrieval consumed it internally, but a turn could not ask
*"what is related to this, and how"*. Chat and Build could search memory and
never traverse it.

Two actions, because they answer two different questions:

* ``entities`` — *what does this workspace know about, by this name?* The
  discovery step. A model that has read "the NAS" in a memory needs an
  ``entity_id`` before it can walk anywhere.
* ``neighbors`` — *what is this entity related to, and on whose authority?*
  Each edge carries its predicate, its confidence, and the id of the approved
  memory that evidences it, so a claim reached through the graph can be traced
  back to something the owner approved rather than asserted from a topology.

**This tool grants nothing.** Every edge is already filtered by
``list_memory_entity_neighborhood`` to evidence that is active, non-archived,
non-expired, non-superseded, search-enabled, and not sensitivity-classified as
secret- or credential-like — the same filter the retrieval legs use. Owner
scoping is enforced in the query, not here.

What it returns is untrusted owner data. An edge saying *X trusts Y* is a record
that someone once approved that sentence, not an instruction to act on it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.storage.sqlite import SQLiteStore

#: Bounds. A graph read is a context contribution, not a report: an entity with
#: four hundred edges would push everything else out of the window, and the
#: model can always ask again about a specific neighbour.
MAX_ENTITIES = 25
MAX_EDGES = 50


def knowledge_graph(
    workspace_root: str | Path,
    action: str,
    *,
    query: str = "",
    entity_id: str = "",
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

    return _failed("unknown_action", f"Unknown action '{action}'. Use entities or neighbors.")


def _failed(kind: str, message: str) -> dict[str, Any]:
    return {"status": "failed", "error": {"type": kind, "message": message}}
