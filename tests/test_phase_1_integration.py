from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.commands import build_prompt_envelope
from raiker.gateway.agent_gateway import AgentGateway
from raiker.tui.status_bar import StatusBarRenderer, StatusContext


def _copy_config(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    source_config = Path(__file__).resolve().parents[1] / "config"
    for name in ["model-profiles.json", "channel-connectors.json"]:
        (tmp_path / "config" / name).write_text((source_config / name).read_text(encoding="utf-8"), encoding="utf-8")


def test_end_to_end_event_sequences_and_checkpoint(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    _copy_config(tmp_path)
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    gateway = AgentGateway(tmp_path)
    response = gateway.submit_prompt(build_prompt_envelope("List files in this project"))
    assert response.status == "completed"
    assert response.events_path is not None
    events = [json.loads(line)["event_type"] for line in Path(response.events_path).read_text(encoding="utf-8").splitlines()]
    for expected in [
        "prompt_received",
        "prompt_normalised",
        "intent_classified",
        "risk_classified",
        "context_gathered",
        "plan_skipped",
        "action_proposed",
        "policy_decision",
        "tool_started",
        "tool_completed",
        "verification_completed",
        "response_created",
        "checkpoint_created",
        "turn_closed",
    ]:
        assert expected in events
    assert response.checkpoint_path is not None
    assert Path(response.checkpoint_path).exists()


def test_outside_workspace_read_denied_and_no_tool_started(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    _copy_config(tmp_path)
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("read file ../secret.txt"))
    assert response.status == "denied"
    events = [json.loads(line)["event_type"] for line in Path(response.events_path).read_text(encoding="utf-8").splitlines()]  # type: ignore[arg-type]
    assert "policy_decision" in events
    assert "tool_started" not in events


def test_local_action_waits_for_approval(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    _copy_config(tmp_path)
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("!pytest"))
    assert response.status == "needs_approval"
    events = [json.loads(line)["event_type"] for line in Path(response.events_path).read_text(encoding="utf-8").splitlines()]  # type: ignore[arg-type]
    assert "approval_requested" in events
    assert "tool_started" not in events


def test_status_bar_named_items_and_context_rendering() -> None:
    rendered = StatusBarRenderer().render(StatusContext(context_used=16000, context_max=32000, last_event="tool_completed"))
    assert "ctx_bar:" in rendered
    assert "50%" in rendered
    assert "ctx:16k/32k" in rendered
    assert "last:tool_completed" in rendered
