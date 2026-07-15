"""Versioned, non-sensitive fixtures for deterministic memory retrieval evaluation."""
from __future__ import annotations

from pathlib import Path

from raiker.memory.evaluation import RetrievalCase
from raiker.memory.store import (
    MemoryForgetGovernance,
    MemoryGovernance,
    correct_memory,
    forget_memory,
    set_memory_archived,
    write_memory,
)
from raiker.storage.sqlite import SQLiteStore

MEMORY_EVAL_V1 = "memory-eval-v1"


def seed_memory_eval_v1(*, store: SQLiteStore, workspace_root: str | Path) -> tuple[RetrievalCase, ...]:
    governance = MemoryGovernance("evt_eval", "sess_eval", None, "evaluation", 1, 1, "until_forget", "approved", "evaluation")
    active = write_memory("Raiker uses archive-first durable memory.", workspace_root=workspace_root, scope="project:alpha", store=store, governance=governance)
    archived = write_memory("Raiker uses archive-first durable memory.", workspace_root=workspace_root, scope="project:beta", store=store, governance=governance)
    set_memory_archived(archived.memory_id, archived=True, workspace_root=workspace_root, store=store)
    original = write_memory("The preferred editor is Vim.", workspace_root=workspace_root, scope="project:alpha", store=store, governance=governance)
    corrected = correct_memory(
        original.memory_id, "The preferred editor is VS Code.", workspace_root=workspace_root, store=store,
        governance=governance, remembered_reason="Evaluation correction fixture.",
    )
    assert corrected is not None
    forgotten = write_memory(
        "Deprecated deployment region is northstar.", workspace_root=workspace_root,
        scope="project:alpha", store=store, governance=governance,
    )
    active_replacement = write_memory(
        "Current deployment region is skylark.", workspace_root=workspace_root,
        scope="project:alpha", store=store, governance=governance,
    )
    assert forget_memory(
        forgotten.memory_id,
        workspace_root=workspace_root,
        store=store,
        governance=MemoryForgetGovernance("evt_eval_forget", "sess_eval", None, "evaluation", "evaluation"),
    )
    sensitive = write_memory(
        "Personal contact is alice@example.test.", workspace_root=workspace_root,
        scope="project:private", store=store, governance=governance,
    )
    future = write_memory(
        "Future deployment region is kestrel.", workspace_root=workspace_root,
        scope="project:alpha", store=store, governance=governance,
    )
    with store.connect() as connection:
        connection.execute(
            "UPDATE approved_memory SET valid_from = ? WHERE memory_id = ?",
            ("2100-01-01T00:00:00Z", future.memory_id),
        )
    store.reconcile_memory_projections()
    return (
        RetrievalCase("scope-and-archive", "archive-first durable", (active.memory_id,), (archived.memory_id,), "project:alpha"),
        RetrievalCase("supersession", "VS Code editor", (corrected.memory_id,), (original.memory_id,), "project:alpha"),
        RetrievalCase("forgotten", "deployment region", (active_replacement.memory_id,), (forgotten.memory_id,), "project:alpha"),
        RetrievalCase("sensitive-scope", "personal contact", (sensitive.memory_id,), (), "project:private"),
        RetrievalCase("valid-time", "deployment region", (active_replacement.memory_id,), (future.memory_id,), "project:alpha"),
    )
