from __future__ import annotations

from dataclasses import dataclass, field

from raiker.contracts.views import View

# Phase 1/2-safe context source types. No graph runtime, semantic search, external channel,
# remote/container/cloud, plugin execution, or scheduled automation sources are permitted.
SOURCE_TYPES = (
    "current_prompt",
    "workspace_summary",
    "recent_events",
    "tasks",
    "checkpoints",
    "approvals",
    "memory_status",
    "memory_candidates",
    "model_profile",
    "capability_status",
    "connector_status",
    "project_context",
    "memory_recall",
    # B9 — the repository code map: which files declare what, ranked against this
    # turn's prompt. Derived from workspace files, so it is untrusted data.
    "code_map",
)

# Deterministic priority order used by the gatherer when applying the budget. Higher in the
# list = kept first when the bundle is over budget.
PRIORITY_ORDER = (
    "current_prompt",
    # User-attached workspace paths (web-app task 3): explicitly attached by the
    # user this turn, so they outrank ambient metadata when the budget is tight.
    "attachment",
    "project_context",
    "memory_recall",
    "workspace_summary",
    # B9 — orientation in the repository outranks the runtime's own bookkeeping:
    # a turn that knows where the code is can act, and one that does not greps
    # blind however many gate lines it was handed.
    "code_map",
    "capability_status",
    "connector_status",
    "approvals",
    "recent_events",
    "tasks",
    "checkpoints",
    "memory_status",
    "memory_candidates",
    "model_profile",
)

TRUST_LEVELS = {"user_prompt", "local_metadata", "untrusted_external"}
SENSITIVITY_LEVELS = {"unknown", "low", "normal", "sensitive"}


@dataclass(frozen=True)
class ContextSource(View):
    source_id: str
    source_type: str
    trust_level: str
    provenance: dict[str, str]
    sensitivity: str
    redacted: bool = False


@dataclass(frozen=True)
class ContextItem(View):
    item_id: str
    source: ContextSource
    title: str
    content: str
    metadata: dict[str, object]
    token_estimate: int
    included: bool = True
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class ContextBundle(View):
    bundle_id: str
    session_id: str
    turn_id: str
    items: list[ContextItem]
    total_token_estimate: int
    max_token_budget: int
    max_chars: int
    truncated: bool
    redaction_applied: bool
    sources: list[str]
    summary: str

    @property
    def included_items(self) -> list[ContextItem]:
        return [item for item in self.items if item.included]

    def source_types(self) -> list[str]:
        seen: list[str] = []
        for item in self.included_items:
            if item.source.source_type not in seen:
                seen.append(item.source.source_type)
        return seen

    def recalled_memory_ids(self) -> list[str]:
        """C17 — which approved memories this turn was actually given.

        Ids only. The text stays in the bundle that reached the model and never
        enters the event log; the ids are what lets the transcript say *which*
        memories were used, and let the owner correct or forget one from there
        instead of hunting for it on the Memory page.
        """
        ids: list[str] = []
        for item in self.included_items:
            if item.source.source_type != "memory_recall":
                continue
            # `metadata` is `dict[str, object]`, so the list has to be recovered
            # rather than assumed: a bundle carrying something else under this
            # key contributes nothing instead of raising mid-turn.
            recalled = item.metadata.get("memory_ids")
            if not isinstance(recalled, list):
                continue
            for memory_id in recalled:
                text = str(memory_id)
                if text and text not in ids:
                    ids.append(text)
        return ids

    def event_payload(self) -> dict[str, object]:
        """Safe metadata-only payload for event logs (no item content)."""

        included = self.included_items
        return {
            "recalled_memory_ids": self.recalled_memory_ids(),
            "bundle_id": self.bundle_id,
            "context_bundle_id": self.bundle_id,
            "item_count": len(self.items),
            "included_count": len(included),
            "total_token_estimate": self.total_token_estimate,
            "truncated": self.truncated,
            "redaction_applied": self.redaction_applied,
            "source_types": self.source_types(),
            "sources": list(self.sources),
        }


@dataclass(frozen=True)
class ContextGathererConfig:
    max_items: int = 20
    max_chars: int = 12000
    max_item_chars: int = 2000
    recent_events_limit: int = 10
    tasks_limit: int = 10
    checkpoints_limit: int = 10
    approvals_limit: int = 10
    memory_candidates_limit: int = 10
    extra_metadata: dict[str, object] = field(default_factory=dict)
