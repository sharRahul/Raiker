from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from raiker.context.models import (
    PRIORITY_ORDER,
    ContextBundle,
    ContextGathererConfig,
    ContextItem,
    ContextSource,
)
from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id
from raiker.memory.candidates import governed_memory_status
from raiker.memory.semantic import semantic_memory_status
from raiker.storage.sqlite import SQLiteStore

# Disabled runtime capability flags surfaced as Phase 1/2-safe context. These must all stay
# False; the gatherer reports them so the model and event log can see the runtime is gated.
CAPABILITY_FLAGS = (
    "plugin_execution_enabled",
    "graph_indexing_enabled",
    "semantic_memory_writes_enabled",
    "vector_writes_enabled",
    "embedding_creation_enabled",
    "approval_execution_enabled",
    "approval_relay_runtime_enabled",
    "cleanup_execution_enabled",
    "rollback_execution_enabled",
    "external_channels_enabled",
    "notifications_enabled",
    "remote_execution_enabled",
    "container_execution_enabled",
    "cloud_execution_enabled",
    "process_execution_enabled",
    "shell_execution_enabled",
    "network_execution_enabled",
    "runtime_execution_enabled",
)


def _token_estimate(content: str) -> int:
    return max(1, len(content) // 4)


class ContextGatherer:
    """Builds a bounded, deterministic, safe Phase 1/2 context bundle.

    Only safe local metadata is gathered. No graph runtime, semantic search, external
    channel, remote/container/cloud, plugin execution, or scheduled automation context is
    produced. Every item carries source provenance, trust level, sensitivity, and redaction
    metadata, and the bundle is budgeted deterministically.
    """

    def __init__(self, config: ContextGathererConfig | None = None) -> None:
        self.config = config or ContextGathererConfig()

    def gather(
        self,
        *,
        workspace_root: str | Path,
        session_id: str,
        turn_id: str,
        prompt_text: str,
        max_items: int = 20,
        max_chars: int = 12000,
    ) -> ContextBundle:
        root = Path(workspace_root).resolve()
        store = SQLiteStore(root)

        builders: dict[str, Callable[[], ContextItem | None]] = {
            "current_prompt": lambda: self._current_prompt(root, prompt_text),
            "workspace_summary": lambda: self._workspace_summary(root, store),
            "capability_status": lambda: self._capability_status(root),
            "approvals": lambda: self._approvals(root, store),
            "recent_events": lambda: self._recent_events(root, store),
            "tasks": lambda: self._tasks(root, store),
            "checkpoints": lambda: self._checkpoints(root, store),
            "memory_status": lambda: self._memory_status(root, store),
            "memory_candidates": lambda: self._memory_candidates(root, store),
            "model_profile": lambda: self._model_profile(root),
        }

        candidates: list[ContextItem] = []
        for source_type in PRIORITY_ORDER:
            builder = builders.get(source_type)
            if builder is None:
                continue
            try:
                item = builder()
            except Exception:  # safe degradation: a bad source must never break gathering
                item = None
            if item is not None:
                candidates.append(item)

        return self._apply_budget(
            candidates,
            session_id=session_id,
            turn_id=turn_id,
            max_items=max_items,
            max_chars=max_chars,
        )

    # --- budget -------------------------------------------------------------------

    def _apply_budget(
        self,
        candidates: list[ContextItem],
        *,
        session_id: str,
        turn_id: str,
        max_items: int,
        max_chars: int,
    ) -> ContextBundle:
        decided: list[ContextItem] = []
        used_chars = 0
        included_count = 0
        for item in candidates:
            forced = item.source.source_type == "current_prompt"
            content_len = len(item.content)
            if forced:
                decided.append(item)
                used_chars += content_len
                included_count += 1
                continue
            if included_count >= max_items:
                decided.append(
                    ContextItem(
                        item_id=item.item_id,
                        source=item.source,
                        title=item.title,
                        content=item.content,
                        metadata=item.metadata,
                        token_estimate=item.token_estimate,
                        included=False,
                        exclusion_reason="budget_exhausted_max_items",
                    )
                )
                continue
            if used_chars + content_len > max_chars:
                decided.append(
                    ContextItem(
                        item_id=item.item_id,
                        source=item.source,
                        title=item.title,
                        content=item.content,
                        metadata=item.metadata,
                        token_estimate=item.token_estimate,
                        included=False,
                        exclusion_reason="budget_exhausted_max_chars",
                    )
                )
                continue
            decided.append(item)
            used_chars += content_len
            included_count += 1

        included = [item for item in decided if item.included]
        total_tokens = sum(item.token_estimate for item in included)
        truncated = any(not item.included for item in decided)
        redaction_applied = any(item.source.redacted for item in included)
        source_types: list[str] = []
        for item in included:
            if item.source.source_type not in source_types:
                source_types.append(item.source.source_type)
        summary = (
            f"context bundle: {len(included)}/{len(decided)} items; "
            f"sources=[{','.join(source_types)}]; "
            f"tokens={total_tokens}; truncated={str(truncated).lower()}; "
            f"redaction_applied={str(redaction_applied).lower()}"
        )
        return ContextBundle(
            bundle_id=new_id("ctxb_"),
            session_id=session_id,
            turn_id=turn_id,
            items=decided,
            total_token_estimate=total_tokens,
            max_token_budget=max(1, max_chars // 4),
            max_chars=max_chars,
            truncated=truncated,
            redaction_applied=redaction_applied,
            sources=source_types,
            summary=summary,
        )

    # --- item builders ------------------------------------------------------------

    def _make_item(
        self,
        *,
        source_type: str,
        trust_level: str,
        sensitivity: str,
        provenance: dict[str, str],
        title: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> ContextItem:
        capped = content[: self.config.max_item_chars]
        redacted, changed = redact_text(capped)
        source = ContextSource(
            source_id=new_id("ctxs_"),
            source_type=source_type,
            trust_level=trust_level,
            provenance=provenance,
            sensitivity=sensitivity,
            redacted=changed,
        )
        return ContextItem(
            item_id=new_id("ctxi_"),
            source=source,
            title=title,
            content=redacted,
            metadata=metadata or {},
            token_estimate=_token_estimate(redacted),
        )

    def _current_prompt(self, root: Path, prompt_text: str) -> ContextItem:
        return self._make_item(
            source_type="current_prompt",
            trust_level="user_prompt",
            sensitivity="unknown",
            provenance={"origin": "user"},
            title="Current prompt",
            content=prompt_text,
            metadata={"char_length": len(prompt_text)},
        )

    def _workspace_summary(self, root: Path, store: SQLiteStore) -> ContextItem:
        event_count = store.count_events()
        checkpoint_count = store.count_checkpoints()
        task_count = store.count_tasks()
        pending_approvals = store.count_pending_approvals()
        lines = [
            f"workspace_root: {root}",
            f"database: {store.db_path}",
            f"event_count: {event_count}",
            f"checkpoint_count: {checkpoint_count}",
            f"task_count: {task_count}",
            f"pending_approval_count: {pending_approvals}",
            "runtime_mode: local_read_only_planning",
            "disabled_runtime: all unsafe runtime flags remain false",
        ]
        return self._make_item(
            source_type="workspace_summary",
            trust_level="local_metadata",
            sensitivity="low",
            provenance={"origin": "workspace_metadata", "workspace_root": str(root)},
            title="Workspace summary",
            content="\n".join(lines),
            metadata={
                "event_count": event_count,
                "checkpoint_count": checkpoint_count,
                "task_count": task_count,
                "pending_approval_count": pending_approvals,
            },
        )

    def _capability_status(self, root: Path) -> ContextItem:
        lines = [f"{flag}: false" for flag in CAPABILITY_FLAGS]
        return self._make_item(
            source_type="capability_status",
            trust_level="local_metadata",
            sensitivity="low",
            provenance={"origin": "phase_gates"},
            title="Capability status (disabled runtime flags)",
            content="\n".join(lines),
            metadata={flag: False for flag in CAPABILITY_FLAGS},
        )

    def _approvals(self, root: Path, store: SQLiteStore) -> ContextItem | None:
        approvals = store.list_approvals(status="pending")[: self.config.approvals_limit]
        if not approvals:
            return None
        # Tool arguments are intentionally redacted/omitted from approval context.
        lines = [
            f"{a['approval_id']} tool={a.get('tool_name')} risk={a.get('risk_level')} "
            f"status={a.get('status')}"
            for a in approvals
        ]
        return self._make_item(
            source_type="approvals",
            trust_level="local_metadata",
            sensitivity="normal",
            provenance={"origin": "approval_inbox"},
            title=f"Pending approvals ({len(approvals)})",
            content="\n".join(lines),
            metadata={"pending_count": len(approvals)},
        )

    def _recent_events(self, root: Path, store: SQLiteStore) -> ContextItem | None:
        events = store.list_event_index(limit=self.config.recent_events_limit)
        if not events:
            return None
        lines = [
            f"{e.get('event_type')} actor={e.get('actor')} at={e.get('timestamp')}"
            for e in events
        ]
        return self._make_item(
            source_type="recent_events",
            trust_level="local_metadata",
            sensitivity="low",
            provenance={"origin": "event_log"},
            title=f"Recent events ({len(events)})",
            content="\n".join(lines),
            metadata={"event_count": len(events)},
        )

    def _tasks(self, root: Path, store: SQLiteStore) -> ContextItem | None:
        tasks = store.list_tasks()[: self.config.tasks_limit]
        if not tasks:
            return None
        lines = [
            f"{t.task_id} {t.title} [{t.status}] created={t.created_at} updated={t.updated_at}"
            for t in tasks
        ]
        return self._make_item(
            source_type="tasks",
            trust_level="local_metadata",
            sensitivity="normal",
            provenance={"origin": "task_store"},
            title=f"Tasks ({len(tasks)})",
            content="\n".join(lines),
            metadata={"task_count": len(tasks)},
        )

    def _checkpoints(self, root: Path, store: SQLiteStore) -> ContextItem | None:
        checkpoints = store.list_checkpoints(limit=self.config.checkpoints_limit)
        if not checkpoints:
            return None
        lines = [
            f"{c['checkpoint_id']} created={c.get('created_at')} "
            f"session={c.get('session_id')} turn={c.get('turn_id')}"
            for c in checkpoints
        ]
        return self._make_item(
            source_type="checkpoints",
            trust_level="local_metadata",
            sensitivity="low",
            provenance={"origin": "checkpoint_timeline"},
            title=f"Checkpoint timeline ({len(checkpoints)})",
            content="\n".join(lines),
            metadata={"checkpoint_count": len(checkpoints)},
        )

    def _memory_status(self, root: Path, store: SQLiteStore) -> ContextItem:
        candidates = store.list_memory_candidates()
        governed = governed_memory_status(candidates)
        semantic = semantic_memory_status(len(candidates))
        lines = [
            f"mode: {governed['mode']}",
            f"durable_writes_enabled: {governed['durable_writes_enabled']}",
            f"candidate_count: {governed['candidate_count']}",
            f"semantic_writes_enabled: {semantic['semantic_writes_enabled']}",
            f"vector_writes_enabled: {semantic['vector_writes_enabled']}",
            "embedding_creation_enabled: False",
        ]
        return self._make_item(
            source_type="memory_status",
            trust_level="local_metadata",
            sensitivity="low",
            provenance={"origin": "memory_governance"},
            title="Memory status",
            content="\n".join(lines),
            metadata={
                "candidate_count": governed["candidate_count"],
                "durable_writes_enabled": False,
                "semantic_writes_enabled": False,
            },
        )

    def _memory_candidates(self, root: Path, store: SQLiteStore) -> ContextItem | None:
        candidates = store.list_memory_candidates()[: self.config.memory_candidates_limit]
        if not candidates:
            return None
        # Metadata-only: candidate text is never surfaced into context.
        lines = [
            f"{c['candidate_id']} decision={c.get('decision')} scope={c.get('scope')} "
            f"sensitivity={c.get('sensitivity')}"
            for c in candidates
        ]
        return self._make_item(
            source_type="memory_candidates",
            trust_level="local_metadata",
            sensitivity="normal",
            provenance={"origin": "memory_candidates"},
            title=f"Memory candidates ({len(candidates)})",
            content="\n".join(lines),
            metadata={"candidate_count": len(candidates)},
        )

    def _model_profile(self, root: Path) -> ContextItem | None:
        from raiker.models.registry import ModelProfileRegistry, RegistryError

        try:
            registry = ModelProfileRegistry.load()
        except (OSError, RegistryError, ValueError):
            return None
        profiles = registry.list_profiles()
        if not profiles:
            return None
        selected = next(
            (p for p in profiles if p.raw.get("is_native_default")), profiles[0]
        )
        local_state = "local" if selected.local_only else "hosted_or_policy_gated"
        lines = [
            f"profile_id: {selected.profile_id}",
            f"provider: {selected.provider}",
            f"model: {selected.model}",
            f"local_only: {selected.local_only}",
            f"requires_network: {selected.requires_network}",
            f"state: {local_state}",
            f"supports_reasoning: {bool(selected.raw.get('supports_reasoning'))}",
        ]
        return self._make_item(
            source_type="model_profile",
            trust_level="local_metadata",
            sensitivity="low",
            provenance={"origin": "model_profile_registry"},
            title="Selected model profile",
            content="\n".join(lines),
            metadata={
                "profile_id": selected.profile_id,
                "provider": selected.provider,
                "local_only": selected.local_only,
            },
        )