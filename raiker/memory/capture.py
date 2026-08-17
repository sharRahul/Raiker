"""MEM-04 — the call the orchestrator was never given.

`raiker.memory.eidetic` has always implemented the Stage C lifecycle correctly:
record an observation, propose a gist, preview an expiry, clean up what the
owner confirmed. Nothing in the runtime called any of it, so the flow
`EIDETIC_MEMORY_AND_LEARNING_SPEC.md` describes — *agent event → classify
sensitivity → eidetic observation → gist candidate → review → durable memory* —
existed only in tests. This module is the missing first half: it turns one
governed tool result into one observation.

Three rules shape it, and they are the reason it is a policy module rather than
three lines in the broker.

**Never the payload.** An observation stores a summary, a checksum, a byte
count, a retention class and — where one already exists — a reference to the
governed artifact. The material itself stays where it already was. A row that
carried the text would make this a second, ungoverned copy of everything the
agent has ever read.

**A refusal is a row.** Material that classifies credential- or secret-like is
not captured, and *that* is recorded, with its reason. Without it an owner
reading an empty Observations list cannot tell "nothing ran" from "everything
was refused" from "this feature is off".

**Outside material is never promotable.** A fetched page, a connector response
and an MCP tool result are untrusted content the agent read on the owner's
behalf. They are observable — that is the point — but they may not become a
candidate for durable memory, because a raw observation is not a trusted
instruction (spec, "Governance Rules", rule 1).
"""
from __future__ import annotations

import contextlib
from collections.abc import Mapping
from typing import Any

from raiker.context.redaction import redact_text
from raiker.memory.eidetic import (
    CAPTURED,
    SKIPPED,
    EideticObservation,
    propose_gist,
    record_observation,
)
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.storage.sqlite import SQLiteStore

#: Which tool produced which kind of material. A tool absent from this map
#: produced bookkeeping rather than material — `update_plan` returns a
#: checklist, `create_task` returns an id — and observing it would fill the
#: owner's list with rows that say nothing about what the agent read.
SOURCE_TYPES: Mapping[str, str] = {
    "read_file": "workspace_file",
    "diff_files": "workspace_file",
    "stat_path": "workspace_file",
    "list_directory": "workspace_index",
    "glob": "workspace_index",
    "grep": "workspace_index",
    "code_map_search": "workspace_index",
    "code_map_references": "workspace_index",
    "run_command": "command_output",
    "background_run": "command_output",
    "web_fetch": "external_web",
    "web_search": "external_web",
    "github_read": "connector",
    "gmail_read": "connector",
    "gcal_read": "connector",
    "slack_read": "connector",
    "connector_read": "connector",
    "conversation_search": "conversation",
    "knowledge_graph": "graph",
    "vector_get": "memory_index",
    "memory_search": "memory_index",
    "consult_advisor": "advisor",
    "spawn_subagent": "subagent",
    # `create_document` is the one write path whose executor returns the
    # produced material rather than a proposal snapshot. `write_file`,
    # `edit_file` and `apply_patch` return what *would* happen and are executed
    # elsewhere after approval, so observing them here would record an artifact
    # that may never exist.
    "create_document": "generated_artifact",
    "skill_load": "skill",
}

#: How long each kind is kept, absent an owner deleting it sooner. Outside
#: material and command output get the short class because their value decays
#: fastest and their volume is highest; workspace material gets the task-
#: continuity class the spec names for exactly that.
RETENTION_BY_SOURCE: Mapping[str, str] = {
    "external_web": "short_term_7_days",
    "connector": "short_term_7_days",
    "mcp_tool": "short_term_7_days",
    "command_output": "short_term_7_days",
    "advisor": "short_term_7_days",
}
DEFAULT_RETENTION = "short_term_30_days"

#: Material Raiker read or produced inside its own boundary. Only these may
#: carry `promotable_to_memory`, and only these may propose a gist.
FIRST_PARTY_SOURCES = frozenset(
    {
        "workspace_file",
        "workspace_index",
        "generated_artifact",
        "conversation",
        "graph",
        "skill",
        "subagent",
        "memory_index",
    }
)

#: The sources whose result is a *conclusion* rather than a raw read, and so the
#: only ones a gist is proposed from. Proposing one per file read would fill the
#: review queue with rows nobody would ever act on, which is how a review queue
#: stops being read at all.
GIST_SOURCES = frozenset({"generated_artifact", "subagent"})

#: Sensitivity labels that stop a capture outright.
_REFUSING_LABELS = frozenset(
    {MemorySensitivity.CREDENTIAL_LIKE.value, MemorySensitivity.SECRET_LIKE.value}
)

#: Labels that allow the observation but not its promotion.
_NON_PROMOTABLE_LABELS = frozenset({MemorySensitivity.PERSONAL.value})

#: Fields whose values are material rather than metadata. Read in this order so
#: the summary quotes the most content-bearing one first.
_MATERIAL_FIELDS = (
    "content", "answer", "text", "stdout", "diff", "excerpt", "body", "output",
    "results", "matches", "entries", "chunks", "hits", "files", "digest",
)

#: Below this, a result is a status rather than material — an empty grep, a
#: `stat` that returned three numbers. Observing them adds rows and no recall.
MINIMUM_MATERIAL_BYTES = 32

#: The observation summary is a label, not a payload. Long enough to recognise
#: the material, far too short to be a copy of it.
_SUMMARY_LIMIT = 180


def source_type_for(tool_name: str) -> str | None:
    """The material kind this tool produces, or ``None`` if it produces none."""
    if tool_name.startswith("mcp__"):
        return "mcp_tool"
    return SOURCE_TYPES.get(tool_name)


def _material(value: Any, depth: int = 0) -> str:
    """Concatenate the content-bearing parts of a tool result.

    Bounded in depth rather than trusted to be shallow: a connector or MCP
    result is a shape an outside program chose, and walking it without a floor
    is how a deeply nested response turns metadata extraction into a stack
    overflow.
    """
    if depth > 3:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list | tuple):
        return "\n".join(part for part in (_material(item, depth + 1) for item in value) if part)
    if isinstance(value, dict):
        parts: list[str] = []
        for field in _MATERIAL_FIELDS:
            if field in value:
                parts.append(_material(value[field], depth + 1))
        if not parts and depth == 0:
            # A result whose material is under a name we do not know is still
            # material. Fall back to every string leaf rather than recording a
            # zero-byte observation that claims nothing was produced.
            parts = [
                _material(item, depth + 1)
                for item in value.values()
                if isinstance(item, str | list | dict)
            ]
        return "\n".join(part for part in parts if part)
    return ""


def _provenance(arguments: Mapping[str, Any]) -> str:
    """The one argument that names *what* was read, redacted and shortened."""
    for key in ("path", "url", "query", "pattern", "repo", "resource", "command", "run_id", "name"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            redacted, _ = redact_text(value.strip())
            return redacted[:80]
    return ""


def summarize(tool_name: str, arguments: Mapping[str, Any], material: str) -> str:
    """A one-line label for the material — never a copy of it."""
    provenance = _provenance(arguments)
    head = f"{tool_name} — {provenance}" if provenance else tool_name
    redacted, _ = redact_text(material.strip().splitlines()[0] if material.strip() else "")
    opening = redacted.strip()[:80]
    label = f"{head}: {opening}" if opening else head
    return label[:_SUMMARY_LIMIT]


def capture_tool_observation(
    store: SQLiteStore,
    *,
    tool_name: str,
    arguments: Mapping[str, Any],
    output: Any,
    source_event_id: str,
    session_id: str,
    turn_id: str,
    owner_principal_id: str,
    artifact_ref: str | None = None,
) -> EideticObservation | None:
    """Record one observation for one successful governed tool result.

    Returns the observation, or ``None`` when this tool produced no material to
    observe. Never raises for a capture problem: an observation is a record
    *about* work, and failing the work because the record failed would trade a
    reliability property for a bookkeeping one.
    """
    source_type = source_type_for(tool_name)
    if source_type is None:
        return None
    material = _material(output)
    if len(material.encode("utf-8", errors="ignore")) < MINIMUM_MATERIAL_BYTES:
        return None
    label = classify_memory_sensitivity(material).value
    retention = RETENTION_BY_SOURCE.get(source_type, DEFAULT_RETENTION)
    if label in _REFUSING_LABELS:
        # Named, not silent. The summary deliberately omits the material — the
        # provenance is what the owner needs to find it, and the reason is what
        # tells them the absence was a decision.
        return record_observation(
            store=store,
            source_event_id=source_event_id,
            session_id=session_id,
            summary=summarize(tool_name, arguments, ""),
            content="",
            retention=retention,
            artifact_ref=artifact_ref,
            owner_principal_id=owner_principal_id,
            turn_id=turn_id,
            tool_name=tool_name,
            source_type=source_type,
            sensitivity=label,
            capture_status=SKIPPED,
            skip_reason=f"observation_sensitivity_{label}",
        )
    promotable = source_type in FIRST_PARTY_SOURCES and label not in _NON_PROMOTABLE_LABELS
    observation = record_observation(
        store=store,
        source_event_id=source_event_id,
        session_id=session_id,
        summary=summarize(tool_name, arguments, material),
        content=material,
        retention=retention,
        artifact_ref=artifact_ref,
        owner_principal_id=owner_principal_id,
        turn_id=turn_id,
        tool_name=tool_name,
        source_type=source_type,
        sensitivity=label,
        capture_status=CAPTURED,
        promotable_to_memory=promotable,
    )
    if promotable and source_type in GIST_SOURCES:
        # `pending_review` is where it stops. A gist is a candidate for durable
        # memory, and nothing in Raiker turns a candidate into a memory without
        # the owner.
        with contextlib.suppress(ValueError):
            propose_gist(
                store=store,
                observation_id=observation.observation_id,
                summary=observation.summary,
                confidence=0.5,
            )
    return observation
