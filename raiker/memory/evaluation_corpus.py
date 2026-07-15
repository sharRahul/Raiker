"""Versioned, non-sensitive fixtures for deterministic memory retrieval evaluation."""
from __future__ import annotations

from pathlib import Path

from raiker.memory.evaluation import RetrievalCase
from raiker.memory.store import MemoryGovernance, correct_memory, set_memory_archived, write_memory
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
    return (
        RetrievalCase("scope-and-archive", "archive-first durable", (active.memory_id,), (archived.memory_id,), "project:alpha"),
        RetrievalCase("supersession", "VS Code editor", (corrected.memory_id,), (original.memory_id,), "project:alpha"),
    )
