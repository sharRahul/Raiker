from __future__ import annotations

from pathlib import Path

from raiker.memory.review import MemoryReviewQueue


def memory_governance_summary(workspace_root: str | Path = ".") -> dict[str, object]:
    return MemoryReviewQueue(workspace_root).export_summary()
