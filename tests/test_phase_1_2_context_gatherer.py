from __future__ import annotations

from pathlib import Path

from raiker.context.gatherer import CAPABILITY_GATE_TOOLS, ContextGatherer
from raiker.context.models import SOURCE_TYPES, ContextBundle, ContextGathererConfig
from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import Checkpoint, TaskRecord, ToolAction
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.memory.candidates import create_deferred_candidate
from raiker.storage.sqlite import SQLiteStore


def _gather(tmp_path: Path, prompt: str = "do the thing", **kwargs: object) -> ContextBundle:
    gatherer = ContextGatherer()
    return gatherer.gather(
        workspace_root=tmp_path,
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        prompt_text=prompt,
        **kwargs,  # type: ignore[arg-type]
    )


def _included_types(bundle: ContextBundle) -> list[str]:
    return [item.source.source_type for item in bundle.included_items]


def _account(store: SQLiteStore) -> str:
    """Seed the minimal credential row that makes a principal a real account.

    Capability gates resolve per principal only for an account, so a test about
    an owner's own gates has to be one.
    """
    principal_id = new_id("usr_")
    now = utc_now()
    with store.connect() as connection:
        connection.execute(
            """INSERT INTO account_credentials
               (principal_id, username, password_hash, hash_algo, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (principal_id, principal_id, "x", "argon2id", now, now),
        )
    return principal_id


def _enable_principal_gate(
    store: SQLiteStore, principal_id: str, capability: str, *, decision_mode: str
) -> None:
    now = utc_now()
    store.upsert_principal_capability_gate_state(principal_id, {
        "capability": capability,
        "state": "enabled_runtime",
        "requested_by": principal_id,
        "requested_at": now,
        "activated_by": principal_id,
        "activated_at": now,
        "reason": "test",
        "readiness_snapshot_json": "",
        "created_at": now,
        "updated_at": now,
    })
    store.upsert_principal_capability_decision_mode(principal_id, {
        "capability": capability,
        "decision_mode": decision_mode,
        "set_by": principal_id,
        "set_at": now,
        "reason": "test",
        "created_at": now,
        "updated_at": now,
    })


def test_current_prompt_item_is_always_included(tmp_path: Path) -> None:
    bundle = _gather(tmp_path, prompt="hello raiker")
    prompts = [i for i in bundle.included_items if i.source.source_type == "current_prompt"]
    assert len(prompts) == 1
    assert prompts[0].content == "hello raiker"
    assert prompts[0].source.trust_level == "user_prompt"
    assert prompts[0].source.sensitivity == "unknown"


def test_workspace_summary_item_is_included(tmp_path: Path) -> None:
    bundle = _gather(tmp_path)
    summaries = [i for i in bundle.included_items if i.source.source_type == "workspace_summary"]
    assert len(summaries) == 1
    assert summaries[0].source.trust_level == "local_metadata"
    assert "workspace_root:" in summaries[0].content


def test_workspace_summary_reports_the_live_runtime_rather_than_a_fixed_string(
    tmp_path: Path,
) -> None:
    """BUG-57: two hardcoded lines told every model the runtime was off."""

    store = SQLiteStore(tmp_path)
    principal_id = _account(store)
    now = utc_now()

    bundle = _gather(tmp_path, owner_principal_id=principal_id)
    summary = [
        i for i in bundle.included_items if i.source.source_type == "workspace_summary"
    ][0]
    # A fresh install has no stored row and the runtime is on.
    assert "agent_runtime: active" in summary.content
    assert "local_read_only_planning" not in summary.content
    assert "all unsafe runtime flags remain false" not in summary.content

    store.upsert_principal_runtime_mode(principal_id, {
        "mode_name": "raiker_runtime",
        "status": "disabled",
        "activated_by": principal_id,
        "activated_at": now,
        "reason": "test",
        "updated_at": now,
    })
    disabled = _gather(tmp_path, owner_principal_id=principal_id)
    summary = [
        i for i in disabled.included_items if i.source.source_type == "workspace_summary"
    ][0]
    assert "agent_runtime: disabled" in summary.content
    assert summary.metadata["agent_runtime"] == "disabled"


def test_capability_status_reports_what_the_tools_will_actually_do(
    tmp_path: Path,
) -> None:
    """GEP-01 — the bundle reports the gate the *tool* will read, not its own.

    This used to assert every gate reads ``disabled`` on a fresh workspace, and
    that was not true of the product: `web_fetch` resolves an empty gate table
    to the shipped default (RAIKER-2021), so the model was told the capability
    was off while `WebAccessService` would have allowed the fetch. Both now read
    through ``capability_admission``, so there is one answer rather than two.
    """
    from raiker.runtime.authority.admission import capability_admission
    from raiker.storage.sqlite import SQLiteStore

    bundle = _gather(tmp_path)
    caps = [i for i in bundle.included_items if i.source.source_type == "capability_status"]
    assert len(caps) == 1
    content = caps[0].content
    store = SQLiteStore(tmp_path)
    for capability, tools in CAPABILITY_GATE_TOOLS.items():
        expected = capability_admission(store, None, capability).gate_enabled
        assert caps[0].metadata[capability]["enabled"] is expected, capability  # type: ignore[index]
        assert f"{capability}: {'enabled' if expected else 'disabled'}" in content
        # BUG-57: naming the tools each gate governs is what stops a model
        # reasoning from one capability's state to a neighbouring one.
        for tool in tools:
            assert tool in content

    # The shape the old assertion was reaching for, stated exactly: nothing that
    # writes or runs is reported on before an owner switches it on.
    assert caps[0].metadata["shell_execution"]["enabled"] is False  # type: ignore[index]


def test_capability_status_reports_a_gate_the_owner_enabled(tmp_path: Path) -> None:
    """BUG-57's required assertion: an owner's decision reaches the model."""

    store = SQLiteStore(tmp_path)
    principal_id = _account(store)
    _enable_principal_gate(store, principal_id, "web_fetch", decision_mode="allow")

    bundle = _gather(tmp_path, owner_principal_id=principal_id)
    caps = [i for i in bundle.included_items if i.source.source_type == "capability_status"][0]

    assert "web_fetch: enabled (state=enabled_runtime, decision_mode=allow)" in caps.content
    assert caps.metadata["web_fetch"]["enabled"] is True  # type: ignore[index]
    # A neighbouring capability is untouched by that decision and still says so.
    assert "shell_execution: disabled" in caps.content
    assert caps.metadata["shell_execution"]["enabled"] is False  # type: ignore[index]


def test_capability_status_agrees_with_the_gate_states_the_tools_enforce(
    tmp_path: Path,
) -> None:
    """The bundle and the tools must not hold two answers for "enabled".

    The old version of this test compared three copies of the *frozenset* and
    passed while the two disagreed, because the disagreement was never in which
    states count as on — it was in what an empty gate table means. So this
    compares the answers instead, for every capability the bundle reports and
    under both scopes, which is the thing that has to hold.
    """
    from raiker.runtime.authority.admission import capability_admission
    from raiker.runtime.web_access import WebAccessService
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(tmp_path)
    principal_id = _account(store)
    _enable_principal_gate(store, principal_id, "shell_execution", decision_mode="allow")

    for scope in (None, principal_id):
        bundle = _gather(tmp_path, owner_principal_id=scope)
        caps = [
            i for i in bundle.included_items if i.source.source_type == "capability_status"
        ][0]
        for capability in CAPABILITY_GATE_TOOLS:
            assert caps.metadata[capability]["enabled"] is (  # type: ignore[index]
                capability_admission(store, scope, capability).gate_enabled
            ), (capability, scope)
        # And against a real enforcing service rather than the helper alone.
        assert caps.metadata["web_fetch"]["enabled"] is (  # type: ignore[index]
            WebAccessService(tmp_path, store, principal_id=scope)._gate_enabled()  # noqa: SLF001
        )


def test_recent_events_are_bounded(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    session_id = new_id("sess_")
    store.create_session(session_id, str(tmp_path))
    for _ in range(15):
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=new_id("turn_"),
                event_type="prompt_received",
                actor="agent_gateway",
                payload={"prompt_length": 1},
            )
        )
    bundle = _gather(tmp_path)
    events = [i for i in bundle.included_items if i.source.source_type == "recent_events"]
    assert len(events) == 1
    # Default recent_events_limit is 10; the item must be bounded to that.
    assert events[0].metadata["event_count"] == 10
    assert len(events[0].content.splitlines()) == 10


def test_tasks_checkpoints_approvals_summaries_are_bounded(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    session_id = new_id("sess_")
    store.create_session(session_id, str(tmp_path))
    now = utc_now()
    store.insert_task(
        TaskRecord(
            task_id=new_id("task_"),
            session_id=session_id,
            title="Refactor module",
            objective="objective",
            status="queued",
            created_at=now,
            updated_at=now,
        )
    )
    store.insert_checkpoint(
        Checkpoint(
            checkpoint_id=new_id("ckpt_"),
            session_id=session_id,
            turn_id=new_id("turn_"),
            created_at=now,
            runtime_state="CLOSED",
            summary="done",
            last_event_id=new_id("evt_"),
        ),
        manifest_path=str(tmp_path / "ckpt.json"),
    )
    action = ToolAction(
        action_id=new_id("act_"),
        tool_name="write_file",
        arguments={"path": "secret_location.txt", "text": "data"},
        risk_level="high",
        requires_approval=True,
    )
    store.insert_tool_action(action, session_id, new_id("turn_"), "approval_required")
    store.insert_approval(new_id("appr_"), action.action_id)

    bundle = _gather(tmp_path)
    types = _included_types(bundle)
    assert "tasks" in types
    assert "checkpoints" in types
    assert "approvals" in types
    approvals = [i for i in bundle.included_items if i.source.source_type == "approvals"][0]
    # Approval tool arguments must be redacted/omitted from context.
    assert "write_file" in approvals.content
    assert "secret_location.txt" not in approvals.content


def test_memory_status_is_metadata_only(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.insert_memory_candidate(
        create_deferred_candidate(new_id("evt_"), "remember password=hunter2 for the db")
    )
    bundle = _gather(tmp_path)
    status = [i for i in bundle.included_items if i.source.source_type == "memory_status"][0]
    assert "semantic_writes_enabled: False" in status.content
    candidates = [i for i in bundle.included_items if i.source.source_type == "memory_candidates"]
    assert len(candidates) == 1
    # Metadata only: the raw candidate text must never be surfaced.
    assert "hunter2" not in candidates[0].content
    assert "password" not in candidates[0].content


def test_redaction_masks_secrets_tokens_emails_and_keys(tmp_path: Path) -> None:
    prompt = (
        "my api_key=ABCDEFGHIJK123456 and token is ghp_abcdefghijklmnopqrstuvwxyz012345 "
        "email me at dev@example.com sk-abcdefghijklmnop1234 "
        "-----BEGIN PRIVATE KEY-----abc-----END PRIVATE KEY-----"
    )
    bundle = _gather(tmp_path, prompt=prompt)
    item = [i for i in bundle.included_items if i.source.source_type == "current_prompt"][0]
    assert item.source.redacted is True
    assert bundle.redaction_applied is True
    assert "ABCDEFGHIJK123456" not in item.content
    assert "ghp_abcdefghijklmnopqrstuvwxyz012345" not in item.content
    assert "dev@example.com" not in item.content
    assert "[REDACTED_TOKEN]" in item.content
    assert "[REDACTED_EMAIL]" in item.content
    assert "[REDACTED_PRIVATE_KEY]" in item.content


def test_redact_text_is_total_and_deterministic() -> None:
    assert redact_text("nothing sensitive here") == ("nothing sensitive here", False)
    once = redact_text("token=supersecretvalue123")
    twice = redact_text("token=supersecretvalue123")
    assert once == twice
    assert once[1] is True


def test_budget_truncation_is_deterministic(tmp_path: Path) -> None:
    bundle = _gather(tmp_path, max_items=3)
    included = bundle.included_items
    assert len(included) == 3
    assert _included_types(bundle) == ["current_prompt", "workspace_summary", "capability_status"]
    assert bundle.truncated is True
    excluded = [i for i in bundle.items if not i.included]
    assert excluded
    assert all(i.exclusion_reason == "budget_exhausted_max_items" for i in excluded)


def test_char_budget_truncation(tmp_path: Path) -> None:
    bundle = _gather(tmp_path, max_chars=10)
    # Only the force-included current prompt should survive an extreme char budget.
    assert _included_types(bundle) == ["current_prompt"]
    assert bundle.truncated is True
    excluded = [i for i in bundle.items if not i.included]
    assert any(i.exclusion_reason == "budget_exhausted_max_chars" for i in excluded)


def test_context_summary_is_deterministic(tmp_path: Path) -> None:
    first = _gather(tmp_path, prompt="same prompt")
    second = _gather(tmp_path, prompt="same prompt")
    # Summary excludes random ids and must be stable for identical workspace state.
    assert first.summary == second.summary
    assert first.source_types() == second.source_types()


def test_no_unsafe_runtime_sources_are_present(tmp_path: Path) -> None:
    bundle = _gather(tmp_path)
    for item in bundle.items:
        assert item.source.source_type in SOURCE_TYPES
    forbidden = {"graph", "semantic", "vector", "plugin", "channel", "remote", "container", "cloud"}
    for item in bundle.items:
        assert item.source.source_type not in forbidden


def test_config_overrides_limits(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    session_id = new_id("sess_")
    store.create_session(session_id, str(tmp_path))
    for _ in range(5):
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=new_id("turn_"),
                event_type="prompt_received",
                actor="agent_gateway",
                payload={},
            )
        )
    gatherer = ContextGatherer(ContextGathererConfig(recent_events_limit=2))
    bundle = gatherer.gather(
        workspace_root=tmp_path,
        session_id=session_id,
        turn_id=new_id("turn_"),
        prompt_text="x",
    )
    events = [i for i in bundle.included_items if i.source.source_type == "recent_events"][0]
    assert events.metadata["event_count"] == 2
