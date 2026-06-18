from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import cast

from raiker.approval_audit_registry import approval_audit_summary, create_workspace_audit_records
from raiker.approval_preview_registry import (
    approval_preview_summary,
    create_fresh_graph_preview_for_workspace,
    create_fresh_memory_preview_for_workspace,
)
from raiker.approval_preview_registry import (
    render_approval_preview as render_stored_approval_preview,
)
from raiker.approval_previews import render_approval_preview
from raiker.approvals import ApprovalInbox
from raiker.channels.registry import ConnectorRegistry
from raiker.checkpoints.service import CheckpointService
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.diagnostics import render_doctor
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.execution.profiles import list_execution_profiles
from raiker.gateway.agent_gateway import AgentGateway
from raiker.graph.governance import graph_governance_status
from raiker.graph.planner import create_graph_codemap_plan
from raiker.memory.candidates import governed_memory_status
from raiker.memory.governance import memory_governance_summary
from raiker.memory.review import MemoryReviewQueue
from raiker.memory.semantic import semantic_memory_status
from raiker.models.registry import ModelProfileRegistry, RegistryError
from raiker.models.router import ModelRouter
from raiker.phase_gates import list_disabled_capabilities
from raiker.plugins.policy import plan_plugin_registration
from raiker.rollback_plans import render_rollback_plan
from raiker.rollback_registry import create_workspace_rollback_plans, rollback_plan_summary
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.workspace.inspection import inspect_workspace
from raiker.workspace.views import render_workspace_view


def terminal_client() -> ClientMetadata:
    return ClientMetadata(
        type="tui",
        name="raiker-terminal",
        version="0.0.0",
        interface_status="equal_primary_when_enabled",
    )


def build_prompt_envelope(
    prompt: str, *, session_id: str | None = None, client: ClientMetadata | None = None
) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=session_id or new_id("sess_"),
        turn_id=new_id("turn_"),
        client=client or terminal_client(),
        user=UserMetadata(),
        prompt=PromptPayload(text=prompt, metadata={"entry_command": "raiker"}),
        options=PromptOptions(),
    )


def render_models(path: str | Path = "config/model-profiles.json") -> str:
    registry = ModelProfileRegistry.load(path)
    lines = ["Model profiles:"]
    for profile in registry.list_profiles():
        lines.append(
            f"- {profile.profile_id} [{profile.default_state}] provider={profile.provider} model={profile.model} phase={profile.build_phase}"
        )
    return "\n".join(lines)


def render_channels(path: str | Path = "config/channel-connectors.json") -> str:
    registry = ConnectorRegistry.load(path)
    lines = ["Channel connector profiles:"]
    for profile in registry.list_profiles():
        lines.append(
            f"- {profile.connector_id} {profile.display_name} [{profile.default_state}] type={profile.channel_type} phase={profile.build_phase} status={profile.interface_status}"
        )
    return "\n".join(lines)


def handle_launch(command: str, *, workspace_root: str | Path = ".") -> str:
    parser = argparse.ArgumentParser(prog="/launch", add_help=False)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args(shlex.split(command)[1:])
    store = SQLiteStore(workspace_root)
    writer = EventLogWriter(store)
    router = ModelRouter(ModelProfileRegistry.load(), writer)
    client = terminal_client()
    result = router.launch(
        args.provider,
        args.model,
        session_id=new_id("sess_"),
        turn_id=None,
        client=client,
    )
    return result.message


def handle_status(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    events_dir = store.paths.events_dir
    checkpoints_dir = store.paths.checkpoints_dir
    db_path = store.db_path
    sessions = store.list_sessions()
    pending = 0
    with store.connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS cnt FROM approvals WHERE status = 'pending'"
        ).fetchone()
        if row:
            pending = int(row["cnt"])
    latest_session_id = sessions[0].get("session_id") if sessions else "none"
    lines = [
        f"workspace: {store.paths.workspace_root}",
        f"database: {db_path}",
        f"events: {events_dir}",
        f"checkpoints: {checkpoints_dir}",
        f"sessions: {len(sessions)}",
        f"latest_session: {latest_session_id}",
        f"pending_approvals: {pending}",
    ]
    return "\n".join(lines)


def handle_tasks(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    writer = EventLogWriter(store)
    manager = TaskManager(store, writer)
    tasks = manager.list_tasks()
    if not tasks:
        return "No tasks."
    lines = ["Tasks:"]
    for task in tasks:
        lines.append(
            f"- {task.task_id} {task.title} [{task.status}] progress={task.progress_percent or 0}%"
        )
    return "\n".join(lines)


def handle_events(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    viewer = EventViewer(store)
    events = viewer.list_events(limit=20)
    if not events:
        return "No events."
    lines = ["Recent events:"]
    for event in events:
        lines.append(
            f"- {event['event_type']} {event['actor']} {event['timestamp']} {event['event_id']}"
        )
    return "\n".join(lines)


def handle_checkpoints(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    service = CheckpointService(store)
    checkpoints = service.list_checkpoints(limit=50)
    if not checkpoints:
        return "No checkpoints."
    lines = ["Checkpoints:"]
    for cp in checkpoints:
        summary = cp.get("summary", "")
        lines.append(
            f"- {cp['checkpoint_id']} session={cp['session_id']} turn={cp['turn_id']} type={cp['checkpoint_type']} created={cp['created_at']} summary={summary}"
        )
    return "\n".join(lines)


def handle_memory(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    candidates = store.list_memory_candidates()
    status = governed_memory_status(candidates)
    lines = [
        "Memory status:",
        f"mode: {status['mode']}",
        f"durable_writes_enabled: {status['durable_writes_enabled']}",
        f"candidate_count: {status['candidate_count']}",
    ]
    for candidate in candidates[:10]:
        lines.append(
            f"- {candidate['candidate_id']} decision={candidate['decision']} scope={candidate['scope']}"
        )
    return "\n".join(lines)


def handle_capabilities() -> str:
    disabled = list_disabled_capabilities()
    lines = ["Phase capability gates:"]
    for phase, capabilities in disabled.items():
        lines.append(f"{phase}:")
        for capability in capabilities:
            lines.append(f"- {capability}: disabled")
    return "\n".join(lines)


def handle_workspace(*, workspace_root: str | Path = ".") -> str:
    summary = inspect_workspace("terminal", workspace_root=workspace_root)
    return "\n".join(
        [
            "Workspace inspection:",
            f"read_only: {summary['contract']['read_only']}",
            f"shared_contract_path: {summary['contract']['shared_contract_path']}",
            f"sessions: {summary['runtime_status']['session_count']}",
            f"events: {len(summary['recent_events'])}",
            f"checkpoints: {len(summary['checkpoint_timeline'])}",
            f"tasks: {len(summary['tasks'])}",
            f"pending_approvals: {len(summary['approvals'])}",
        ]
    )


def handle_clients() -> str:
    client_types = [
        "terminal",
        "desktop",
        "web",
        "dashboard",
        "ide",
        "voice",
        "mobile_companion",
        "browser_extension",
        "chat/channel client",
    ]
    lines = ["Client contract parity:"]
    for client_type in client_types:
        lines.append(
            f"- {client_type}: UIActionEnvelope shared_gateway equal_primary_when_enabled privileged=False"
        )
    return "\n".join(lines)


def handle_plugins() -> str:
    return "Plugin registration plans:\n- no persisted plugin plans; use /plugin-plan <manifest_path> for read-only planning"


def handle_plugin_plan(command: str) -> str:
    parts = shlex.split(command)
    if len(parts) != 2:
        return "Usage: /plugin-plan <manifest_path>"
    path = Path(parts[1])
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"Plugin plan failed: {exc}"
    if not isinstance(manifest, dict):
        return "Plugin plan failed: manifest must be a JSON object"
    plan = plan_plugin_registration(manifest).to_dict()
    return "\n".join(
        [
            "Plugin registration plan:",
            f"plugin_id: {plan['plugin_id']}",
            f"status: {plan['status']}",
            f"execution_enabled: {plan['execution_enabled']}",
            f"permissions: {','.join(plan['permissions'])}",
            f"reasons: {','.join(plan['reasons']) if plan['reasons'] else 'none'}",
        ]
    )


def handle_workspace_view(
    command: str = "/workspace-view", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) != 1:
        return "Usage: /workspace-view"
    return render_workspace_view(workspace_root=workspace_root, client_type="terminal")


def handle_graph_status() -> str:
    status = graph_governance_status()
    return "\n".join(
        ["Graph/codemap status:"] + [f"{key}: {value}" for key, value in status.items()]
    )


def handle_graph_plan(*, workspace_root: str | Path = ".") -> str:
    try:
        plan = create_graph_codemap_plan(workspace_root).to_dict()
        included_paths = cast(list[str], plan["included_paths"])
        excluded_paths = cast(list[dict[str, object]], plan["excluded_paths"])
    except (OSError, ValueError) as exc:
        return f"Graph plan failed: {exc}"
    return "\n".join(
        [
            "Graph/codemap dry-run plan:",
            f"plan_id: {plan['plan_id']}",
            f"can_index: {plan['can_index']}",
            f"runtime_indexing_enabled: {plan['runtime_indexing_enabled']}",
            f"requires_approval: {plan['requires_approval']}",
            f"included_paths: {len(included_paths)}",
            f"excluded_paths: {len(excluded_paths)}",
            f"policy_decision: {plan['policy_decision']}",
        ]
    )


def handle_memory_review(
    command: str = "/memory-review", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] != "--summary"):
        return "Usage: /memory-review [--summary]"
    queue = MemoryReviewQueue(workspace_root)
    if len(parts) == 2:
        summary = queue.export_summary()
        return "\n".join(
            ["Memory review summary:"] + [f"{key}: {value}" for key, value in summary.items()]
        )
    items = queue.list_candidates()
    lines = [
        "Memory review queue:",
        f"semantic_writes_enabled: {memory_governance_summary(workspace_root)['semantic_writes_enabled']}",
    ]
    if not items:
        lines.append("No memory candidates.")
    for item in items[:10]:
        lines.append(
            f"- {item.candidate_id} decision={item.decision} sensitivity={item.sensitivity} can_write_semantic_memory={item.can_write_semantic_memory}"
        )
    return "\n".join(lines)


def handle_approval_previews(*, workspace_root: str | Path = ".") -> str:
    summary = approval_preview_summary(workspace_root=workspace_root)
    lines = ["Approval previews:", "persistence: in_memory_only_not_persisted"]
    lines.extend(f"{key}: {value}" for key, value in summary.items())
    lines.append(
        "available_commands: /graph-approval-preview, /memory-approval-preview, /approval-preview <preview_id>"
    )
    return "\n".join(lines)


def handle_graph_approval_preview(*, workspace_root: str | Path = ".") -> str:
    try:
        preview = create_fresh_graph_preview_for_workspace(workspace_root)
    except (OSError, ValueError) as exc:
        return f"Graph approval preview failed: {exc}"
    return render_approval_preview(preview)


def handle_memory_approval_preview(
    command: str = "/memory-approval-preview", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] != "--summary"):
        return "Usage: /memory-approval-preview [--summary]"
    if len(parts) == 2:
        summary = approval_preview_summary(workspace_root=workspace_root)
        return "\n".join(
            ["Memory approval preview summary:"]
            + [f"{key}: {value}" for key, value in summary.items()]
        )
    preview = create_fresh_memory_preview_for_workspace(workspace_root)
    if preview is None:
        return "Memory approval preview: no memory review candidates available; add/review candidates without semantic writes first."
    return render_approval_preview(preview)


def handle_approval_preview_lookup(command: str) -> str:
    parts = shlex.split(command)
    if len(parts) != 2:
        return "Usage: /approval-preview <preview_id>"
    return render_stored_approval_preview(parts[1])



def handle_approval_audit(command: str = "/approval-audit", *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] != "--summary"):
        return "Usage: /approval-audit [--summary]"
    if len(parts) == 2:
        summary = approval_audit_summary(workspace_root=workspace_root)
        return "\n".join(["Approval audit summary:"] + [f"{key}: {value}" for key, value in summary.items()])
    records = create_workspace_audit_records(workspace_root)
    lines = ["Approval audit previews:", "persistence: in_memory_only_not_persisted", "execution_enabled: False"]
    if not records:
        lines.append("No approval audit records available.")
    for record in records:
        lines.append(f"- {record.audit_id} preview={record.preview_id} decision={record.decision} status={record.decision_status} can_execute_now={record.can_execute_now}")
    return "\n".join(lines)


def handle_rollback_plan(*, workspace_root: str | Path = ".") -> str:
    summary = rollback_plan_summary(workspace_root=workspace_root)
    return "\n".join(["Rollback planning surfaces:"] + [f"{key}: {value}" for key, value in summary.items()])


def handle_graph_rollback_plan(*, workspace_root: str | Path = ".") -> str:
    try:
        plan = create_workspace_rollback_plans(workspace_root)[0]
    except (OSError, ValueError) as exc:
        return f"Graph rollback plan failed: {exc}"
    return render_rollback_plan(plan)


def handle_memory_rollback_plan(*, workspace_root: str | Path = ".") -> str:
    try:
        plans = create_workspace_rollback_plans(workspace_root)
    except (OSError, ValueError) as exc:
        return f"Memory rollback plan failed: {exc}"
    memory_plans = [plan for plan in plans if plan.target_capability == "semantic_memory_writes"]
    if not memory_plans:
        return "Memory rollback plan: no semantic memory review candidates available; preview-only rollback surface is available and rollback_execution_enabled: False."
    return render_rollback_plan(memory_plans[0])

def handle_execution_profiles() -> str:
    lines = ["Execution profiles:"]
    for profile in list_execution_profiles():
        lines.append(
            f"- {profile.profile_id} kind={profile.kind} state={profile.default_state} requires_approval={profile.requires_approval}"
        )
    return "\n".join(lines)


def handle_semantic_memory(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    status = semantic_memory_status(len(store.list_memory_candidates()))
    return "\n".join([f"{key}: {value}" for key, value in status.items()])


def handle_approvals(*, workspace_root: str | Path = ".") -> str:
    inbox = ApprovalInbox(SQLiteStore(workspace_root))
    approvals = inbox.list_pending()
    if not approvals:
        return "No pending approvals."
    lines = ["Pending approvals:"]
    for approval in approvals:
        lines.append(
            f"- {approval['approval_id']} action={approval['action_id']} tool={approval['tool_name']} risk={approval['risk_level']}"
        )
    return "\n".join(lines)


def handle_approval_resolution(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    if len(parts) != 2:
        return "Usage: /approve <approval_id> or /deny <approval_id>"
    inbox = ApprovalInbox(SQLiteStore(workspace_root))
    try:
        resolution = inbox.resolve(parts[1], approve=parts[0] == "/approve")
    except ValueError as exc:
        return f"Approval resolution failed: {exc}"
    return (
        f"Approval {resolution.approval_id} {resolution.status} for action {resolution.action_id}."
    )


def handle_slash_command(command: str, *, workspace_root: str | Path = ".") -> str:
    command = command.strip()
    if command in {"/quit", "/exit"}:
        return "Exiting Raiker."
    if command == "/help":
        return "Commands: /help, /status, /tasks, /events, /checkpoints, /approvals, /approve <id>, /deny <id>, /memory, /semantic-memory, /capabilities, /execution-profiles, /workspace, /workspace-view, /clients, /plugins, /plugin-plan <manifest_path>, /graph-status, /graph-plan, /memory-review [--summary], /approval-previews, /graph-approval-preview, /memory-approval-preview [--summary], /approval-preview <preview_id>, /approval-audit [--summary], /rollback-plan, /graph-rollback-plan, /memory-rollback-plan, /doctor, /channels, /models, /launch --provider mock --model mock-deterministic, /quit"
    if command == "/models":
        return render_models()
    if command == "/channels":
        return render_channels()
    if command == "/status":
        return handle_status(workspace_root=workspace_root)
    if command == "/tasks":
        return handle_tasks(workspace_root=workspace_root)
    if command == "/events":
        return handle_events(workspace_root=workspace_root)
    if command == "/checkpoints":
        return handle_checkpoints(workspace_root=workspace_root)
    if command == "/approvals":
        return handle_approvals(workspace_root=workspace_root)
    if command == "/memory":
        return handle_memory(workspace_root=workspace_root)
    if command == "/semantic-memory":
        return handle_semantic_memory(workspace_root=workspace_root)
    if command == "/capabilities":
        return handle_capabilities()
    if command == "/execution-profiles":
        return handle_execution_profiles()
    if command == "/workspace":
        return handle_workspace(workspace_root=workspace_root)
    if command == "/workspace-view" or command.startswith("/workspace-view "):
        return handle_workspace_view(command, workspace_root=workspace_root)
    if command == "/graph-status":
        return handle_graph_status()
    if command == "/graph-plan":
        return handle_graph_plan(workspace_root=workspace_root)
    if command == "/memory-review" or command.startswith("/memory-review "):
        return handle_memory_review(command, workspace_root=workspace_root)
    if command == "/approval-previews":
        return handle_approval_previews(workspace_root=workspace_root)
    if command == "/graph-approval-preview":
        return handle_graph_approval_preview(workspace_root=workspace_root)
    if command == "/memory-approval-preview" or command.startswith("/memory-approval-preview "):
        return handle_memory_approval_preview(command, workspace_root=workspace_root)
    if command == "/approval-preview" or command.startswith("/approval-preview "):
        return handle_approval_preview_lookup(command)
    if command == "/approval-audit" or command.startswith("/approval-audit "):
        return handle_approval_audit(command, workspace_root=workspace_root)
    if command == "/rollback-plan":
        return handle_rollback_plan(workspace_root=workspace_root)
    if command == "/graph-rollback-plan":
        return handle_graph_rollback_plan(workspace_root=workspace_root)
    if command == "/memory-rollback-plan":
        return handle_memory_rollback_plan(workspace_root=workspace_root)
    if command == "/clients":
        return handle_clients()
    if command == "/plugins":
        return handle_plugins()
    if command == "/plugin-plan" or command.startswith("/plugin-plan "):
        return handle_plugin_plan(command)
    if command == "/doctor":
        return render_doctor(workspace_root=workspace_root)
    if (
        command in {"/approve", "/deny"}
        or command.startswith("/approve ")
        or command.startswith("/deny ")
    ):
        return handle_approval_resolution(command, workspace_root=workspace_root)
    if command.startswith("/launch "):
        try:
            return handle_launch(command, workspace_root=workspace_root)
        except (RegistryError, SystemExit, ValueError) as exc:
            return f"Launch failed: {exc}"
    return f"Unknown command: {command}"


def submit_terminal_prompt(prompt: str, *, workspace_root: str | Path = ".") -> str:
    gateway = AgentGateway(workspace_root)
    envelope = build_prompt_envelope(prompt)
    response = gateway.submit_prompt(envelope)
    parts = [response.message]
    if response.approval is not None:
        parts.append(
            f"Approval card: action={response.approval['action_id']} tool={response.approval['tool_name']} risk={response.approval['risk_level']}"
        )
    if response.events_path:
        parts.append(f"events: {response.events_path}")
    if response.checkpoint_path:
        parts.append(f"checkpoint: {response.checkpoint_path}")
    return "\n".join(parts)
