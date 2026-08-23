"""BUG-231 — the audit log, taken out of the product.

`audit_export` was a capability in `ALL_CAPABILITIES` with no executor, so it
could not be activated and no route surfaced the redacted manifest
`raiker/events/export.py` was already building. Evidence that cannot leave is
evidence that cannot be used in a review, an incident write-up, or a second tool.

The properties held here are the ones that make an export usable *and* safe:
it is governed, it is redacted, it is scoped to the acting principal's own
account, it agrees with the on-screen record, and it is itself audited.
"""

from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.commands import bootstrap_owner
from raiker.control.service import RuntimeControlService
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    RuntimeControlService(ws).activate_runtime_mode("local_single_user_runtime", None, "test")
    return ws


def test_the_capability_has_a_real_executor_and_can_be_activated() -> None:
    from raiker.runtime.authority.activation import ACTIVATION_REQUIREMENTS
    from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

    assert "audit_export" in REAL_EXECUTOR_CAPABILITIES
    # A capability with an executor and no requirement entry cannot be turned on
    # at all — the trap BUG-62 recorded. This is the assertion that stops it.
    assert "audit_export" in ACTIVATION_REQUIREMENTS


def test_export_produces_a_redacted_file_and_a_manifest(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    store = SQLiteStore(ws)
    EventLogWriter(store).append(
        make_event(
            session_id="sess_audit",
            turn_id=None,
            event_type="prompt_received",
            actor="user",
            payload={"note": "keep this", "api_key": "sk-should-not-survive"},
        )
    )

    result = RuntimeControlService(ws).export_audit_log(None)

    assert result.ok, result.reason_code
    assert result.data["redacted"] is True
    assert int(result.data["event_count"]) > 0
    assert len(str(result.data["manifest_hash"])) == 64

    exported = Path(str(result.data["export_path"])).read_text(encoding="utf-8")
    assert "sk-should-not-survive" not in exported
    assert "***REDACTED***" in exported
    assert "keep this" in exported, "redaction removes secrets, not the record"
    for line in exported.splitlines():
        json.loads(line)  # every line is one well-formed event


def test_the_export_is_itself_an_audited_event(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    store = SQLiteStore(ws)
    EventLogWriter(store).append(
        make_event(
            session_id="sess_audit", turn_id=None, event_type="prompt_received",
            actor="user", payload={"note": "hello"},
        )
    )

    assert RuntimeControlService(ws).export_audit_log(None).ok

    types = {str(row["event_type"]) for row in store.list_event_index(limit=500)}
    assert any("audit_export" in t or "action" in t for t in types), (
        "the export enters through route_action, so it leaves a governed record"
    )


def test_export_refuses_a_non_human_principal(tmp_path: Path) -> None:
    """An automation may not take the owner's record out of the product."""
    ws = _workspace(tmp_path)
    store = SQLiteStore(ws)
    store.insert_principal(
        "principal_agent", "ai_agent", "Agent", delegated_by_user_id="owner"
    )

    result = RuntimeControlService(ws).export_audit_log("principal_agent")

    assert not result.ok
    # Principal resolution refuses an AI principal before the human-only check
    # is even reached. Either refusal is correct; what matters is that no export
    # is produced and the reason names the principal type.
    assert result.reason_code is not None
    assert "AI principal" in result.reason_code or result.reason_code == "not_authorized_human"


def test_an_empty_scope_says_so_rather_than_writing_an_empty_file(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    result = RuntimeControlService(ws).export_audit_log(
        None, session_id="sess_that_does_not_exist"
    )
    assert not result.ok
    assert result.reason_code == "audit_export_empty"


def test_the_visibility_filter_agrees_with_the_audit_log_view(tmp_path: Path) -> None:
    """BUG-231's second half: an export must be the same record as the screen.

    `DashboardService.list_events` shows a row when it belongs to one of this
    account's sessions **or to no session record at all** — the BUG-87 rule that
    keeps governed steps taken outside any conversation inside the log. The
    export's filter used to require a `sessions` row, so it silently produced a
    narrower record than the page it was taken from.
    """
    ws = _workspace(tmp_path)
    store = SQLiteStore(ws)
    EventLogWriter(store).append(
        make_event(
            session_id="terminal-local", turn_id=None, event_type="prompt_received",
            actor="user", payload={"note": "outside any conversation"},
        )
    )

    filtered = store.list_event_index(
        user_id="owner", apply_user_visibility_filter=True, limit=500
    )
    assert any(str(row["session_id"]) == "terminal-local" for row in filtered)
