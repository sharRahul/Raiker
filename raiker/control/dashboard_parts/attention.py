# mypy: disable-error-code="misc"
"""DEC-02 steps 2, 4 and 5 — one server-backed *Needs your attention* feed.

Home put together its attention rail in the browser from three reads —
approvals, runtime readiness and blocked tasks — so everything else that waits
on the owner (a memory Raiker proposed, a delivery that did not arrive, an MCP
tool held for review, a containment signal) was on its own page and nowhere
the owner starts from. The decision asks for one feed whose items each carry
a stable id, a severity, a plain title and reason, the record they came from,
the one action that resolves them and when they began — and that resolve only
from the authoritative state of the subsystem that raised them.

So this reads each subsystem's own record, every time it is asked, and keeps
nothing of its own: an item disappears when its subsystem says it is resolved,
because the next read no longer finds it. Items carry references and counts,
never copied content — a proposed memory's text stays on Memory. A subsystem
that cannot be read is named in ``unknown`` rather than counted as clear.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from typing_extensions import TypedDict

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService

AttentionSeverity = Literal["containment", "blocking", "waiting"]


class AttentionItemView(TypedDict):
    """One thing waiting on the owner, by reference."""

    #: Stable for as long as the condition holds, so a client can key on it.
    id: str
    severity: AttentionSeverity
    title: str
    reason: str
    #: The subsystem and record the item points at.
    origin_kind: str
    origin_id: str | None
    #: The one place the owner resolves it, and what that action is called.
    href: str
    action_label: str
    #: When the condition began, when the subsystem recorded that.
    since: str | None


class AttentionFeedView(TypedDict):
    items: list[AttentionItemView]
    #: Subsystems that could not be read: unknown, never an all-clear.
    unknown: list[str]


_ORDER = {"containment": 0, "blocking": 1, "waiting": 2}

#: Tasks that will not move again until a person acts — the same set Home's
#: Blocked work tile counts (`BLOCKED_TASK_STATES` in the web client).
_BLOCKED_TASK_STATES = ("waiting_for_approval", "paused")


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


class AttentionService:

    def attention_feed(
        self: DashboardService,
        principal_id: str,
        user_id: str | None,
        *,
        task_user_id: str | None = None,
    ) -> AttentionFeedView:
        """``user_id`` scopes approvals as ``GET /api/approvals`` does;
        ``task_user_id`` scopes tasks as ``GET /api/tasks`` does."""
        items: list[AttentionItemView] = []
        unknown: list[str] = []
        readers = (
            ("security", self._attention_containment),
            ("approvals", self._attention_approvals),
            ("tasks", lambda pid, _uid: self._attention_tasks(pid, task_user_id or user_id)),
            ("memory", self._attention_memory),
            ("messaging", self._attention_deliveries),
            ("mcp", self._attention_mcp),
        )
        for name, read in readers:
            try:
                items.extend(read(principal_id, user_id))
            except Exception:  # noqa: BLE001 — one unreadable subsystem is named, not fatal
                unknown.append(name)
        items.sort(key=lambda item: (_ORDER[item["severity"]], item["since"] or ""))
        return {"items": items, "unknown": unknown}

    # ── one reader per subsystem, each reading its own record ──────────────

    def _attention_containment(
        self: DashboardService, principal_id: str, _user_id: str | None
    ) -> list[AttentionItemView]:
        return [
            {
                "id": f"containment:{row['source']}:{row['subject_id']}:{row['code']}",
                "severity": "containment",
                "title": "A containment signal is alerting",
                "reason": (
                    f"{row['source']} raised {str(row['code']).replace('_', ' ')} and it has "
                    "not recovered."
                ),
                "origin_kind": "security_signal",
                "origin_id": str(row["subject_id"]),
                "href": "#/settings?tab=security",
                "action_label": "Review security",
                "since": str(row.get("updated_at") or "") or None,
            }
            for row in self.list_security_health(principal_id)
            if row["state"] == "alerting"
        ]

    def _attention_approvals(
        self: DashboardService, principal_id: str, user_id: str | None
    ) -> list[AttentionItemView]:
        pending = self.store.list_approvals(
            status="pending", user_id=user_id, principal_id=principal_id
        )
        if not pending:
            return []
        count = len(pending)
        oldest = min((str(row.get("created_at") or "") for row in pending), default="")
        return [{
            "id": "approvals:pending",
            "severity": "blocking",
            "title": f"{count} {_plural(count, 'decision is', 'decisions are')} waiting for you",
            "reason": "Each one holds a governed action until you approve or refuse it.",
            "origin_kind": "approvals",
            "origin_id": None,
            "href": "#/approvals",
            "action_label": "Review approvals",
            "since": oldest or None,
        }]

    def _attention_tasks(
        self: DashboardService, _principal_id: str, user_id: str | None
    ) -> list[AttentionItemView]:
        items: list[AttentionItemView] = []
        for task in self.list_tasks(user_id=user_id):
            status = str(task.status)
            if status not in _BLOCKED_TASK_STATES:
                continue
            waiting = status == "waiting_for_approval"
            items.append({
                "id": f"task:{task.task_id}",
                "severity": "blocking" if waiting else "waiting",
                "title": (
                    f"“{task.title}” is waiting for your decision"
                    if waiting
                    else f"“{task.title}” is paused"
                ),
                "reason": (
                    "It continues once the approval it asked for is decided."
                    if waiting
                    else "Nothing more runs until you continue or stop it."
                ),
                "origin_kind": "task",
                "origin_id": str(task.task_id),
                "href": f"#/tasks?task={task.task_id}",
                "action_label": "Open the task",
                "since": str(getattr(task, "updated_at", "") or "") or None,
            })
        return items

    def _attention_memory(
        self: DashboardService, principal_id: str, _user_id: str | None
    ) -> list[AttentionItemView]:
        # The same read Memory's Suggestions tab lists, so the two agree.
        waiting = self.list_memory_proposals(principal_id)
        if not waiting:
            return []
        count = len(waiting)
        oldest = min((str(row.get("created_at") or "") for row in waiting), default="")
        return [{
            "id": "memory:proposals",
            "severity": "waiting",
            "title": f"{count} proposed {_plural(count, 'memory', 'memories')} to review",
            "reason": "Raiker does not recall a proposal until you approve it.",
            "origin_kind": "memory_proposals",
            "origin_id": None,
            "href": "#/memory?tab=suggestions",
            "action_label": "Review proposals",
            "since": oldest or None,
        }]

    def _attention_deliveries(
        self: DashboardService, _principal_id: str, _user_id: str | None
    ) -> list[AttentionItemView]:
        rows = self.store.list_channel_deliveries_to_review(limit=200)
        by_channel: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            by_channel.setdefault(str(row["connector_id"]), []).append(row)
        items: list[AttentionItemView] = []
        for connector_id, pending in sorted(by_channel.items()):
            count = len(pending)
            unknown = sum(1 for row in pending if row.get("outcome_unknown_at"))
            items.append({
                "id": f"deliveries:{connector_id}",
                "severity": "waiting",
                "title": (
                    f"{count} {_plural(count, 'delivery', 'deliveries')} on a channel "
                    f"{_plural(count, 'needs', 'need')} a look"
                ),
                "reason": (
                    "Raiker stopped while sending, so it may have arrived; it was not sent again."
                    if unknown == count
                    else "It did not arrive. Nothing is sent again on its own."
                ),
                "origin_kind": "channel",
                "origin_id": connector_id,
                "href": "#/messaging",
                "action_label": "Open Messaging",
                "since": min((str(row.get("created_at") or "") for row in pending), default="") or None,
            })
        return items

    def _attention_mcp(
        self: DashboardService, principal_id: str, _user_id: str | None
    ) -> list[AttentionItemView]:
        from raiker.tools.mcp_review import pending_tools

        items: list[AttentionItemView] = []
        for row in self.store.list_mcp_servers(principal_id):
            held = pending_tools(row)
            if not held:
                continue
            count = len(held)
            items.append({
                "id": f"mcp:{row['server_id']}:held",
                "severity": "waiting",
                "title": f"“{row['name']}” has {count} {_plural(count, 'tool', 'tools')} to review",
                "reason": "The server added or changed them; Raiker does not offer them until you accept.",
                "origin_kind": "mcp_server",
                "origin_id": str(row["server_id"]),
                "href": "#/extensions?tab=mcp",
                "action_label": "Review tools",
                "since": str(row.get("last_connected_at") or "") or None,
            })
        return items


__all__ = ["AttentionFeedView", "AttentionItemView", "AttentionService"]
