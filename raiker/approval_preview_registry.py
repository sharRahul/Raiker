from __future__ import annotations

from pathlib import Path
from typing import cast

from raiker.approval_previews import (
    ApprovalPreview,
    create_graph_indexing_approval_preview,
    create_semantic_memory_write_approval_preview,
)
from raiker.approval_previews import (
    render_approval_preview as render_preview_text,
)
from raiker.graph.planner import GraphCodemapIndexPlan, create_graph_codemap_plan
from raiker.memory.review import MemoryReviewItem, MemoryReviewQueue


class ApprovalPreviewRegistry:
    """In-memory, preview-only registry; it performs no durable approval writes."""

    def __init__(self) -> None:
        self._previews: dict[str, ApprovalPreview] = {}

    def create_graph_indexing_preview(self, plan: GraphCodemapIndexPlan) -> ApprovalPreview:
        preview = create_graph_indexing_approval_preview(plan)
        self._previews[preview.preview_id] = preview
        return preview

    def create_semantic_memory_write_preview(
        self, review_item: MemoryReviewItem
    ) -> ApprovalPreview:
        preview = create_semantic_memory_write_approval_preview(review_item)
        self._previews[preview.preview_id] = preview
        return preview

    def list_approval_previews(self) -> list[ApprovalPreview]:
        return [self._previews[key] for key in sorted(self._previews)]

    def render_approval_preview(self, preview_id: str) -> str:
        preview = self._previews.get(preview_id)
        if preview is None:
            return f"Approval preview not found in in-memory registry: {preview_id}"
        return render_preview_text(preview)


def create_graph_indexing_preview(plan: GraphCodemapIndexPlan) -> ApprovalPreview:
    return create_graph_indexing_approval_preview(plan)


def create_semantic_memory_write_preview(review_item: MemoryReviewItem) -> ApprovalPreview:
    return create_semantic_memory_write_approval_preview(review_item)


def list_approval_previews() -> list[ApprovalPreview]:
    return []


def render_approval_preview(preview_id: str) -> str:
    return f"Approval previews are not persisted in this slice; create a fresh preview instead of loading {preview_id}."


def approval_preview_summary(*, workspace_root: str | Path = ".") -> dict[str, object]:
    queue = MemoryReviewQueue(workspace_root)
    denied_memory = cast(int, queue.export_summary()["denied_secret_like_count"])
    return {
        "graph_indexing_preview_available": True,
        "semantic_memory_write_preview_available": True,
        "pending_preview_count": 0,
        "denied_preview_count": denied_memory,
        "preview_only_mode": True,
        "runtime_execution_enabled": False,
    }


def create_fresh_graph_preview_for_workspace(workspace_root: str | Path = ".") -> ApprovalPreview:
    return create_graph_indexing_preview(create_graph_codemap_plan(workspace_root))


def create_fresh_memory_preview_for_workspace(
    workspace_root: str | Path = ".",
) -> ApprovalPreview | None:
    items = MemoryReviewQueue(workspace_root).list_candidates()
    if not items:
        return None
    return create_semantic_memory_write_preview(items[0])
