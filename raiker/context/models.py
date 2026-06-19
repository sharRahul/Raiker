from __future__ import annotations

from dataclasses import dataclass, field

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
)

# Deterministic priority order used by the gatherer when applying the budget. Higher in the
# list = kept first when the bundle is over budget.
PRIORITY_ORDER = (
    "current_prompt",
    "workspace_summary",
    "capability_status",
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
class ContextSource:
    source_id: str
    source_type: str
    trust_level: str
    provenance: dict[str, str]
    sensitivity: str
    redacted: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "trust_level": self.trust_level,
            "provenance": dict(self.provenance),
            "sensitivity": self.sensitivity,
            "redacted": self.redacted,
        }


@dataclass(frozen=True)
class ContextItem:
    item_id: str
    source: ContextSource
    title: str
    content: str
    metadata: dict[str, object]
    token_estimate: int
    included: bool = True
    exclusion_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "source": self.source.to_dict(),
            "title": self.title,
            "content": self.content,
            "metadata": dict(self.metadata),
            "token_estimate": self.token_estimate,
            "included": self.included,
            "exclusion_reason": self.exclusion_reason,
        }


@dataclass(frozen=True)
class ContextBundle:
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

    def to_dict(self) -> dict[str, object]:
        """Full bundle including item content. For model-prompt use, not event logs."""

        return {
            "bundle_id": self.bundle_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "items": [item.to_dict() for item in self.items],
            "total_token_estimate": self.total_token_estimate,
            "max_token_budget": self.max_token_budget,
            "max_chars": self.max_chars,
            "truncated": self.truncated,
            "redaction_applied": self.redaction_applied,
            "sources": list(self.sources),
            "summary": self.summary,
        }

    def event_payload(self) -> dict[str, object]:
        """Safe metadata-only payload for event logs (no item content)."""

        included = self.included_items
        return {
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
