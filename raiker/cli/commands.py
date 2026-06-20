from __future__ import annotations

import argparse
import asyncio
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
from raiker.approvals.readiness_registry import (
    approval_readiness_summary,
    render_approval_readiness,
)
from raiker.channels.readiness_registry import channel_readiness_summary, render_channel_readiness
from raiker.channels.registry import ConnectorRegistry
from raiker.checkpoints.service import CheckpointService
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    ClientMetadata,
    ModelProfile,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    Role,
    User,
    UserMetadata,
    UserRoleAssignment,
)
from raiker.diagnostics import render_doctor
from raiker.events.query import EventViewer
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.execution.profiles import list_execution_profiles
from raiker.gateway.agent_gateway import AgentGateway
from raiker.graph.governance import graph_governance_status
from raiker.graph.planner import create_graph_codemap_plan
from raiker.graph.readiness_registry import graph_readiness_summary, render_graph_readiness
from raiker.memory.candidates import governed_memory_status
from raiker.memory.governance import memory_governance_summary
from raiker.memory.readiness_registry import (
    render_semantic_memory_readiness,
    semantic_memory_readiness_summary,
)
from raiker.memory.review import MemoryReviewQueue
from raiker.memory.semantic import semantic_memory_status
from raiker.models.exceptions import ModelProviderError, ProviderPolicyError, safe_error
from raiker.models.factory import capabilities_from_profile
from raiker.models.registry import ModelProfileRegistry, RegistryError
from raiker.models.router import ModelRouter
from raiker.models.session_state import ModelSessionState
from raiker.phase_gates import list_disabled_capabilities
from raiker.plugins.policy import plan_plugin_registration
from raiker.plugins.readiness_registry import plugin_readiness_summary, render_plugin_readiness
from raiker.remote.readiness_registry import (
    remote_readiness_summary,
    render_remote_readiness,
)
from raiker.rollback_plans import render_rollback_plan
from raiker.rollback_registry import create_workspace_rollback_plans, rollback_plan_summary
from raiker.storage.cleanup_readiness_registry import (
    cleanup_readiness_summary,
    render_cleanup_readiness,
)
from raiker.storage.lifecycle_registry import (
    render_lifecycle_evidence_summary,
    render_lifecycle_policy_simulation_summary,
    render_lifecycle_summary,
    render_retention_cleanup_handoff,
)
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


def _model_session_id() -> str:
    return "terminal-local"


def _selected_profile(
    registry: ModelProfileRegistry, workspace_root: str | Path = "."
) -> ModelProfile:
    store = SQLiteStore(workspace_root)
    state = store.load_model_session_state(_model_session_id())
    if state is not None:
        try:
            return registry.resolve_profile_id(state.profile_id)
        except RegistryError:
            pass
    for profile in registry.list_profiles():
        if profile.raw.get("is_native_default"):
            return profile
    return registry.list_profiles()[0]


async def render_models_async(
    path: str | Path = "config/model-profiles.json",
    *,
    workspace_root: str | Path = ".",
    router: ModelRouter | None = None,
) -> str:
    registry = ModelProfileRegistry.load(path)
    selected = _selected_profile(registry, workspace_root)
    lines = ["Model profiles:"]
    for profile in registry.list_profiles():
        marker = " (selected)" if profile.profile_id == selected.profile_id else ""
        lines.append(
            f"- {profile.profile_id}{marker} [{profile.default_state}] provider={profile.provider} model={profile.model} phase={profile.build_phase}"
        )
    lines.extend(["Live models for selected provider:"])
    live_router = router or ModelRouter(registry)
    try:
        models = await live_router.alist_models(selected.provider, selected.model)
    except ProviderPolicyError as exc:
        lines.extend(["status: policy_denied", f"reason: {safe_error(str(exc))}"])
    except ModelProviderError as exc:
        reason = (
            "model_listing_unsupported" if "unsupported" in str(exc) else "provider_unreachable"
        )
        lines.extend(
            [
                f"status: {'unsupported' if reason == 'model_listing_unsupported' else 'unavailable'}",
                f"reason: {reason}",
            ]
        )
    except Exception as exc:
        lines.extend(["status: unavailable", f"reason: {safe_error(type(exc).__name__)}"])
    else:
        lines.extend(
            [
                "status: available",
                f"provider: {selected.provider}",
                f"profile_id: {selected.profile_id}",
                "models:",
            ]
        )
        lines.extend(f"- {model.id}" for model in models)
    return "\n".join(lines)


def render_models(
    path: str | Path = "config/model-profiles.json", *, workspace_root: str | Path = "."
) -> str:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(render_models_async(path, workspace_root=workspace_root))
    return "Live model listing requires async command path; use render_models_async."


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
        "phase_3_status: implemented_verified",
        "phase_4_status: memory_mvp_implemented",
        "runtime_execution_enabled: False",
        "approved_memory_count: 0",
        "phase_3_4_surface_mode: read_only_planning_preview_only",
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
            f"storage_lifecycle_records: {summary['storage_lifecycle_summary']['lifecycle_record_count']}",
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


def handle_plugins(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    records = store.list_plugin_install_records()
    if not records:
        return "No plugin install records. Use /plugin-plan <manifest_path> to plan a plugin install."
    lines = ["Plugin install records:"]
    for r in records:
        lines.append(f"- {r['plugin_id']} v={r['version']} trust={r['trust_level']} status={r['status']} checksum={'yes' if r.get('checksum') else 'no'} signature={'yes' if r.get('signature') else 'no'}")
    return "\n".join(lines)


def handle_plugin_plan(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command, posix=False)
    if len(parts) < 2:
        return "Usage: /plugin-plan <manifest_path> [--install]"
    path = Path(parts[1].strip("\"'"))
    install_flag = "--install" in parts
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"Plugin plan failed: {exc}"
    if not isinstance(manifest, dict):
        return "Plugin plan failed: manifest must be a JSON object"
    plan = plan_plugin_registration(manifest).to_dict()
    lines = [
        "Plugin registration plan:",
        f"plugin_id: {plan['plugin_id']}",
        f"status: {plan['status']}",
        f"execution_enabled: {plan['execution_enabled']}",
        f"permissions: {','.join(plan['permissions'])}",
        f"reasons: {','.join(plan['reasons']) if plan['reasons'] else 'none'}",
    ]
    if install_flag and plan["status"] != "denied":
        supply_chain = manifest.get("supply_chain") or {}
        from raiker.plugins.registry import record_plugin_install
        record = record_plugin_install(
            store=SQLiteStore(workspace_root),
            plugin_id=str(plan["plugin_id"]),
            version=str(manifest.get("version", "0.0.0")),
            trust_level=str(plan["trust_level"]),
            permissions_json=json.dumps(plan["permissions"], sort_keys=True),
            checksum=supply_chain.get("checksum"),
            signature=supply_chain.get("signature"),
            source_url=supply_chain.get("source_url"),
            commit_sha=supply_chain.get("commit_sha"),
        )
        lines.append(f"Installed: {record.record_id}")
    return "\n".join(lines)


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


def handle_graph_readiness(
    command: str = "/graph-readiness", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"--summary", "--json"}):
        return "Usage: /graph-readiness [--summary|--json]"
    if len(parts) == 2 and parts[1] == "--json":
        return json.dumps(graph_readiness_summary(workspace_root=workspace_root), sort_keys=True)
    if len(parts) == 2 and parts[1] == "--summary":
        summary = graph_readiness_summary(workspace_root=workspace_root)
        return "\n".join(
            [
                "Graph/codemap indexing readiness summary:",
                f"metadata_only: {summary['metadata_only']}",
                f"ready_for_indexing: {summary['ready_for_indexing']}",
                f"indexing_jobs_enabled: {summary['indexing_jobs_enabled']}",
                f"runtime_execution_enabled: {summary['runtime_execution_enabled']}",
                f"blocker_count: {summary['blocker_count']}",
            ]
        )
    return render_graph_readiness(workspace_root=workspace_root)


def handle_memory_readiness(
    command: str = "/memory-readiness", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"--summary", "--json"}):
        return "Usage: /memory-readiness [--summary|--json]"
    if len(parts) == 2 and parts[1] == "--json":
        return json.dumps(
            semantic_memory_readiness_summary(workspace_root=workspace_root), sort_keys=True
        )
    if len(parts) == 2 and parts[1] == "--summary":
        summary = semantic_memory_readiness_summary(workspace_root=workspace_root)
        return "\n".join(
            [
                "Semantic memory write readiness summary:",
                f"metadata_only: {summary['metadata_only']}",
                f"ready_for_memory_writes: {summary['ready_for_memory_writes']}",
                f"semantic_memory_writes_enabled: {summary['semantic_memory_writes_enabled']}",
                f"vector_writes_enabled: {summary['vector_writes_enabled']}",
                f"embedding_creation_enabled: {summary['embedding_creation_enabled']}",
                f"memory_write_jobs_enabled: {summary['memory_write_jobs_enabled']}",
                f"runtime_execution_enabled: {summary['runtime_execution_enabled']}",
                f"blocker_count: {summary['blocker_count']}",
            ]
        )
    return render_semantic_memory_readiness(workspace_root=workspace_root)


def handle_approval_readiness(
    command: str = "/approval-readiness", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"--summary", "--json"}):
        return "Usage: /approval-readiness [--summary|--json]"
    if len(parts) == 2 and parts[1] == "--json":
        return json.dumps(approval_readiness_summary(workspace_root=workspace_root), sort_keys=True)
    if len(parts) == 2 and parts[1] == "--summary":
        summary = approval_readiness_summary(workspace_root=workspace_root)
        return "\n".join(
            [
                "Approval preview persistence readiness summary:",
                f"metadata_only: {summary['metadata_only']}",
                f"ready_for_persistence: {summary['ready_for_persistence']}",
                f"approval_preview_persistence_enabled: {summary['approval_preview_persistence_enabled']}",
                f"approval_execution_enabled: {summary['approval_execution_enabled']}",
                f"approval_relay_runtime_enabled: {summary['approval_relay_runtime_enabled']}",
                f"durable_approval_queues_enabled: {summary['durable_approval_queues_enabled']}",
                f"approval_workers_enabled: {summary['approval_workers_enabled']}",
                f"runtime_execution_enabled: {summary['runtime_execution_enabled']}",
                f"blocker_count: {summary['blocker_count']}",
            ]
        )
    return render_approval_readiness(workspace_root=workspace_root)


def handle_channel_readiness(
    command: str = "/channel-readiness", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"--summary", "--json"}):
        return "Usage: /channel-readiness [--summary|--json]"
    if len(parts) == 2 and parts[1] == "--json":
        return json.dumps(channel_readiness_summary(workspace_root=workspace_root), sort_keys=True)
    if len(parts) == 2 and parts[1] == "--summary":
        summary = channel_readiness_summary(workspace_root=workspace_root)
        return "\n".join(
            [
                "External channels/notifications readiness summary:",
                f"metadata_only: {summary['metadata_only']}",
                f"ready_for_external_channels: {summary['ready_for_external_channels']}",
                f"external_channels_enabled: {summary['external_channels_enabled']}",
                f"notifications_enabled: {summary['notifications_enabled']}",
                f"push_notifications_enabled: {summary['push_notifications_enabled']}",
                f"share_links_enabled: {summary['share_links_enabled']}",
                f"webhook_dispatch_enabled: {summary['webhook_dispatch_enabled']}",
                f"channel_relay_runtime_enabled: {summary['channel_relay_runtime_enabled']}",
                f"workers_enabled: {summary['workers_enabled']}",
                f"schedulers_enabled: {summary['schedulers_enabled']}",
                f"runtime_execution_enabled: {summary['runtime_execution_enabled']}",
                f"blocker_count: {summary['blocker_count']}",
            ]
        )
    return render_channel_readiness(workspace_root=workspace_root)


def handle_remote_readiness(
    command: str = "/remote-readiness", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"--summary", "--json"}):
        return "Usage: /remote-readiness [--summary|--json]"
    if len(parts) == 2 and parts[1] == "--json":
        return json.dumps(remote_readiness_summary(workspace_root=workspace_root), sort_keys=True)
    if len(parts) == 2 and parts[1] == "--summary":
        summary = remote_readiness_summary(workspace_root=workspace_root)
        return "\n".join(
            [
                "Remote/container/cloud execution readiness summary:",
                f"metadata_only: {summary['metadata_only']}",
                f"ready_for_remote_execution: {summary['ready_for_remote_execution']}",
                f"ready_for_container_execution: {summary['ready_for_container_execution']}",
                f"ready_for_cloud_execution: {summary['ready_for_cloud_execution']}",
                f"remote_execution_enabled: {summary['remote_execution_enabled']}",
                f"container_execution_enabled: {summary['container_execution_enabled']}",
                f"cloud_execution_enabled: {summary['cloud_execution_enabled']}",
                f"hosted_routines_enabled: {summary['hosted_routines_enabled']}",
                f"runtime_jobs_enabled: {summary['runtime_jobs_enabled']}",
                f"job_dispatch_enabled: {summary['job_dispatch_enabled']}",
                f"worker_queues_enabled: {summary['worker_queues_enabled']}",
                f"workers_enabled: {summary['workers_enabled']}",
                f"schedulers_enabled: {summary['schedulers_enabled']}",
                f"file_watchers_enabled: {summary['file_watchers_enabled']}",
                f"daemons_enabled: {summary['daemons_enabled']}",
                f"client_transport_enabled: {summary['client_transport_enabled']}",
                f"external_dispatch_enabled: {summary['external_dispatch_enabled']}",
                f"credential_materialization_enabled: {summary['credential_materialization_enabled']}",
                f"secret_injection_enabled: {summary['secret_injection_enabled']}",
                f"provider_integrations_enabled: {summary['provider_integrations_enabled']}",
                f"sandbox_runtime_enabled: {summary['sandbox_runtime_enabled']}",
                f"process_execution_enabled: {summary['process_execution_enabled']}",
                f"shell_execution_enabled: {summary['shell_execution_enabled']}",
                f"network_execution_enabled: {summary['network_execution_enabled']}",
                f"runtime_execution_enabled: {summary['runtime_execution_enabled']}",
                f"blocker_count: {summary['blocker_count']}",
            ]
        )
    return render_remote_readiness(workspace_root=workspace_root)


def handle_plugin_readiness(
    command: str = "/plugin-readiness", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"--summary", "--json"}):
        return "Usage: /plugin-readiness [--summary|--json]"
    if len(parts) == 2 and parts[1] == "--json":
        return json.dumps(plugin_readiness_summary(workspace_root=workspace_root), sort_keys=True)
    if len(parts) == 2 and parts[1] == "--summary":
        summary = plugin_readiness_summary(workspace_root=workspace_root)
        return "\n".join(
            [
                "Plugin/server startup readiness summary:",
                f"metadata_only: {summary['metadata_only']}",
                f"ready_for_plugin_server_startup: {summary['ready_for_plugin_server_startup']}",
                f"plugin_execution_enabled: {summary['plugin_execution_enabled']}",
                f"plugin_installation_enabled: {summary['plugin_installation_enabled']}",
                f"plugin_activation_enabled: {summary['plugin_activation_enabled']}",
                f"mcp_server_startup_enabled: {summary['mcp_server_startup_enabled']}",
                f"lsp_server_startup_enabled: {summary['lsp_server_startup_enabled']}",
                f"plugin_server_startup_enabled: {summary['plugin_server_startup_enabled']}",
                f"monitor_daemon_startup_enabled: {summary['monitor_daemon_startup_enabled']}",
                f"marketplace_installs_enabled: {summary['marketplace_installs_enabled']}",
                f"external_channels_enabled: {summary['external_channels_enabled']}",
                f"workers_enabled: {summary['workers_enabled']}",
                f"schedulers_enabled: {summary['schedulers_enabled']}",
                f"runtime_execution_enabled: {summary['runtime_execution_enabled']}",
                f"blocker_count: {summary['blocker_count']}",
            ]
        )
    return render_plugin_readiness(workspace_root=workspace_root)


def handle_cleanup_readiness(
    command: str = "/cleanup-readiness", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"--summary", "--json"}):
        return "Usage: /cleanup-readiness [--summary|--json]"
    if len(parts) == 2 and parts[1] == "--json":
        return json.dumps(cleanup_readiness_summary(workspace_root=workspace_root), sort_keys=True)
    if len(parts) == 2 and parts[1] == "--summary":
        summary = cleanup_readiness_summary(workspace_root=workspace_root)
        return "\n".join(
            [
                "Storage cleanup execution readiness summary:",
                f"metadata_only: {summary['metadata_only']}",
                f"ready_for_cleanup_execution: {summary['ready_for_cleanup_execution']}",
                f"cleanup_execution_enabled: {summary['cleanup_execution_enabled']}",
                f"deletion_execution_enabled: {summary['deletion_execution_enabled']}",
                f"purge_execution_enabled: {summary['purge_execution_enabled']}",
                f"tombstone_execution_enabled: {summary['tombstone_execution_enabled']}",
                f"rollback_execution_enabled: {summary['rollback_execution_enabled']}",
                f"cleanup_jobs_enabled: {summary['cleanup_jobs_enabled']}",
                f"workers_enabled: {summary['workers_enabled']}",
                f"schedulers_enabled: {summary['schedulers_enabled']}",
                f"runtime_execution_enabled: {summary['runtime_execution_enabled']}",
                f"blocker_count: {summary['blocker_count']}",
            ]
        )
    return render_cleanup_readiness(workspace_root=workspace_root)


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


_APPROVAL_PREVIEWS_USAGE = (
    "Usage: /approval-previews [--json] "
    "[--status <preview_created|needs_human_review|blocked|ready_for_planning|superseded>] "
    "[--limit <number>]"
)


def _parse_approval_previews_command(command: str) -> dict[str, object] | str:
    from raiker.review.models import APPROVAL_PREVIEW_STATUSES

    parts = shlex.split(command)
    as_json = False
    status: str | None = None
    limit = 20
    i = 1
    while i < len(parts):
        arg = parts[i]
        if arg == "--json":
            as_json = True
            i += 1
        elif arg == "--status" and i + 1 < len(parts):
            status = parts[i + 1]
            if status not in APPROVAL_PREVIEW_STATUSES:
                return _APPROVAL_PREVIEWS_USAGE
            i += 2
        elif arg == "--limit" and i + 1 < len(parts):
            try:
                limit = int(parts[i + 1])
            except ValueError:
                return _APPROVAL_PREVIEWS_USAGE
            if limit < 0:
                return _APPROVAL_PREVIEWS_USAGE
            i += 2
        else:
            return _APPROVAL_PREVIEWS_USAGE
    return {"as_json": as_json, "status": status, "limit": limit}


def handle_approval_previews(command: str = "/approval-previews", *, workspace_root: str | Path = ".") -> str:
    from raiker.review.approval_preview import (
        ProposalApprovalPreviewStore,
        previews_to_json,
        render_previews_text,
    )

    parts = shlex.split(command)
    if len(parts) == 1:
        summary = approval_preview_summary(workspace_root=workspace_root)
        lines = ["Approval previews:", "persistence: in_memory_only_not_persisted"]
        lines.extend(f"{key}: {value}" for key, value in summary.items())
        lines.append(
            "available_commands: /graph-approval-preview, /memory-approval-preview, /approval-preview <preview_id>, /proposal <proposal_id> --approval-preview"
        )
        return "\n".join(lines)

    parsed = _parse_approval_previews_command(command)
    if isinstance(parsed, str):
        return parsed
    preview_store = ProposalApprovalPreviewStore(SQLiteStore(workspace_root))
    status_arg = parsed["status"]
    limit_val = parsed["limit"]
    previews = preview_store.list_previews(
        status=status_arg if isinstance(status_arg, str) else None,
        limit=int(limit_val) if isinstance(limit_val, int) else 20,
    )
    if parsed["as_json"]:
        return previews_to_json(previews)
    return render_previews_text(previews)


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


_APPROVAL_PREVIEW_DETAIL_USAGE = (
    "Usage: /approval-preview <preview_id> [--json]"
)


def _parse_approval_preview_detail_command(command: str) -> dict[str, object] | str:
    parts = shlex.split(command)
    if len(parts) < 2:
        return _APPROVAL_PREVIEW_DETAIL_USAGE
    preview_id = parts[1]
    if preview_id.startswith("--"):
        return _APPROVAL_PREVIEW_DETAIL_USAGE
    as_json = False
    i = 2
    while i < len(parts):
        arg = parts[i]
        if arg == "--json":
            as_json = True
            i += 1
        else:
            return _APPROVAL_PREVIEW_DETAIL_USAGE
    return {"preview_id": preview_id, "as_json": as_json}


def handle_approval_preview_lookup(command: str, *, workspace_root: str | Path = ".") -> str:
    from raiker.review.approval_preview import (
        ProposalApprovalPreviewStore,
        preview_to_json,
        render_preview_text,
    )

    parts = shlex.split(command)
    if len(parts) >= 2 and parts[1].startswith("apv_"):
        parsed = _parse_approval_preview_detail_command(command)
        if isinstance(parsed, str):
            return parsed
        preview_store = ProposalApprovalPreviewStore(SQLiteStore(workspace_root))
        preview = preview_store.get_preview(str(parsed["preview_id"]))
        if preview is None:
            return "Approval planning preview not found."
        if parsed["as_json"]:
            return preview_to_json(preview)
        return render_preview_text(preview)
    if len(parts) >= 2:
        return render_stored_approval_preview(parts[1])
    return _APPROVAL_PREVIEW_DETAIL_USAGE


def handle_approval_audit(
    command: str = "/approval-audit", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] != "--summary"):
        return "Usage: /approval-audit [--summary]"
    if len(parts) == 2:
        summary = approval_audit_summary(workspace_root=workspace_root)
        return "\n".join(
            ["Approval audit summary:"] + [f"{key}: {value}" for key, value in summary.items()]
        )
    records = create_workspace_audit_records(workspace_root)
    lines = [
        "Approval audit previews:",
        "persistence: in_memory_only_not_persisted",
        "execution_enabled: False",
    ]
    if not records:
        lines.append("No approval audit records available.")
    for record in records:
        lines.append(
            f"- {record.audit_id} preview={record.preview_id} decision={record.decision} status={record.decision_status} can_execute_now={record.can_execute_now}"
        )
    return "\n".join(lines)


def handle_rollback_plan(*, workspace_root: str | Path = ".") -> str:
    summary = rollback_plan_summary(workspace_root=workspace_root)
    return "\n".join(
        ["Rollback planning surfaces:"] + [f"{key}: {value}" for key, value in summary.items()]
    )


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


def handle_storage_lifecycle(
    command: str = "/storage-lifecycle", *, workspace_root: str | Path = "."
) -> str:
    parts = shlex.split(command)
    if len(parts) > 2 or (len(parts) == 2 and parts[1] not in {"--summary", "--graph", "--memory"}):
        return "Usage: /storage-lifecycle [--summary|--graph|--memory]"
    if len(parts) == 2 and parts[1] == "--summary":
        return render_lifecycle_summary(workspace_root=workspace_root, summary_only=True)
    if len(parts) == 2 and parts[1] == "--graph":
        return render_lifecycle_summary(
            workspace_root=workspace_root, target_capability="graph_codemap_indexing"
        )
    if len(parts) == 2 and parts[1] == "--memory":
        return render_lifecycle_summary(
            workspace_root=workspace_root, target_capability="semantic_memory_writes"
        )
    return render_lifecycle_summary(workspace_root=workspace_root)


def handle_storage_lifecycle_slice_h(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    command_name = parts[0] if parts else command
    mapping = {
        "/storage-lifecycle-retention": "retention",
        "/storage-lifecycle-cleanup-preview": "cleanup-preview",
        "/storage-lifecycle-handoff": "handoff",
    }
    if (
        command_name not in mapping
        or len(parts) > 2
        or (len(parts) == 2 and parts[1] != "--summary")
    ):
        return f"Usage: {command_name} [--summary]"
    return render_retention_cleanup_handoff(
        mapping[command_name], workspace_root=workspace_root, summary_only=(len(parts) == 2)
    )


def _parse_lifecycle_slice_i(
    command: str, usage: str
) -> tuple[bool, bool, str | None, str | None, int] | str:
    parts = shlex.split(command)
    summary_only = False
    as_json = False
    status = None
    target = None
    limit = 20
    i = 1
    allowed_targets = {"graph", "memory", "rollback", "storage", "plugin", "channel", "remote"}
    while i < len(parts):
        arg = parts[i]
        if arg == "--summary":
            summary_only = True
            i += 1
        elif arg == "--json":
            as_json = True
            i += 1
        elif arg == "--status" and i + 1 < len(parts):
            status = parts[i + 1]
            i += 2
        elif arg == "--target" and i + 1 < len(parts):
            target = parts[i + 1]
            if target not in allowed_targets:
                return usage
            i += 2
        elif arg == "--limit" and i + 1 < len(parts):
            try:
                limit = int(parts[i + 1])
            except ValueError:
                return usage
            if limit < 1:
                return usage
            i += 2
        else:
            return usage
    return summary_only, as_json, status, target, limit


def handle_storage_lifecycle_evidence(command: str, *, workspace_root: str | Path = ".") -> str:
    usage = "Usage: /storage-lifecycle-evidence [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]"
    parsed = _parse_lifecycle_slice_i(command, usage)
    if isinstance(parsed, str):
        return parsed
    summary_only, as_json, status, target, limit = parsed
    return render_lifecycle_evidence_summary(
        workspace_root=workspace_root,
        summary_only=summary_only,
        as_json=as_json,
        status=status,
        target=target,
        limit=limit,
    )


def handle_storage_lifecycle_policy_simulation(
    command: str, *, workspace_root: str | Path = "."
) -> str:
    usage = "Usage: /storage-lifecycle-policy-simulation [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]"
    parsed = _parse_lifecycle_slice_i(command, usage)
    if isinstance(parsed, str):
        return parsed
    summary_only, as_json, status, target, limit = parsed
    return render_lifecycle_policy_simulation_summary(
        workspace_root=workspace_root,
        summary_only=summary_only,
        as_json=as_json,
        status=status,
        target=target,
        limit=limit,
    )


def _parse_review_command(command: str) -> dict[str, object] | str:
    usage = (
        "Usage: /review [--summary] [--staged] [--path <path>] [--json] "
        "[--limit <number>] [--severity <info|low|medium|high>] "
        "[--propose-fixes] [--proposals-only] [--save-proposals]"
    )
    parts = shlex.split(command)
    summary_only = False
    as_json = False
    staged = False
    path: str | None = None
    limit: int | None = None
    severity: str | None = None
    propose_fixes = False
    proposals_only = False
    save_proposals = False
    i = 1
    while i < len(parts):
        arg = parts[i]
        if arg == "--summary":
            summary_only = True
            i += 1
        elif arg == "--json":
            as_json = True
            i += 1
        elif arg == "--staged":
            staged = True
            i += 1
        elif arg == "--propose-fixes":
            propose_fixes = True
            i += 1
        elif arg == "--proposals-only":
            proposals_only = True
            propose_fixes = True
            i += 1
        elif arg == "--save-proposals":
            save_proposals = True
            propose_fixes = True
            i += 1
        elif arg == "--path" and i + 1 < len(parts):
            path = parts[i + 1]
            i += 2
        elif arg == "--limit" and i + 1 < len(parts):
            try:
                limit = int(parts[i + 1])
            except ValueError:
                return usage
            if limit < 0:
                return usage
            i += 2
        elif arg == "--severity" and i + 1 < len(parts):
            severity = parts[i + 1]
            if severity not in {"info", "low", "medium", "high"}:
                return usage
            i += 2
        else:
            return usage
    return {
        "summary_only": summary_only,
        "as_json": as_json,
        "staged": staged,
        "path": path,
        "limit": limit,
        "severity": severity,
        "propose_fixes": propose_fixes,
        "proposals_only": proposals_only,
        "save_proposals": save_proposals,
    }


def handle_review(command: str = "/review", *, workspace_root: str | Path = ".") -> str:
    from raiker.review.lifecycle import ProposalLifecycleStore
    from raiker.review.models import SEVERITY_RANK
    from raiker.review.render import rebuild_review_result_with_findings, render_json, render_text
    from raiker.review.workflow import CodeReviewWorkflow, ReviewPathError

    parsed = _parse_review_command(command)
    if isinstance(parsed, str):
        return parsed
    path_arg = parsed["path"]
    severity = parsed["severity"]
    limit = parsed["limit"]
    propose_fixes = bool(parsed["propose_fixes"])
    proposals_only = bool(parsed["proposals_only"])
    save_proposals = bool(parsed["save_proposals"])
    try:
        result = CodeReviewWorkflow().review(
            workspace_root=workspace_root,
            staged=bool(parsed["staged"]),
            path=path_arg if isinstance(path_arg, str) else None,
            summary_only=bool(parsed["summary_only"]),
            propose_fixes=propose_fixes,
        )
    except ReviewPathError:
        return "Review failed: path is outside the workspace."
    except (OSError, ValueError) as exc:
        return f"Review failed: {type(exc).__name__}"

    findings = list(result.findings)
    if isinstance(severity, str):
        threshold = SEVERITY_RANK[severity]
        findings = [f for f in findings if SEVERITY_RANK[f.severity] >= threshold]
    if isinstance(limit, int):
        findings = findings[:limit]
    if findings != list(result.findings) or propose_fixes:
        result = rebuild_review_result_with_findings(
            result, findings, propose_fixes=propose_fixes
        )

    if save_proposals and result.action_proposals:
        store = ProposalLifecycleStore(SQLiteStore(workspace_root))
        saved = store.save_proposals(
            result.action_proposals, review_id=result.review_id
        )
        result_metadata = dict(result.event_metadata)
        result_metadata["saved_proposal_count"] = len(saved)
        result_metadata["saved_proposal_ids"] = [r.proposal_id for r in saved]
        from dataclasses import replace as _replace

        result = _replace(result, event_metadata=result_metadata)

    if parsed["as_json"]:
        return render_json(result)
    return render_text(
        result,
        summary_only=bool(parsed["summary_only"]),
        proposals_only=proposals_only,
    )


_PROPOSAL_USAGE = (
    "Usage: /proposals [--json] [--status <proposed|acknowledged|deferred|rejected|superseded>] "
    "[--limit <number>]"
)
_PROPOSAL_DETAIL_USAGE = (
    "Usage: /proposal <proposal_id> [--json] "
    "[--mark <proposed|acknowledged|deferred|rejected|superseded>] "
    "[--approval-preview]"
)
_PROPOSAL_STATUSES = {"proposed", "acknowledged", "deferred", "rejected", "superseded"}


def _parse_proposals_command(command: str) -> dict[str, object] | str:
    parts = shlex.split(command)
    as_json = False
    status: str | None = None
    limit = 20
    i = 1
    while i < len(parts):
        arg = parts[i]
        if arg == "--json":
            as_json = True
            i += 1
        elif arg == "--status" and i + 1 < len(parts):
            status = parts[i + 1]
            if status not in _PROPOSAL_STATUSES:
                return _PROPOSAL_USAGE
            i += 2
        elif arg == "--limit" and i + 1 < len(parts):
            try:
                limit = int(parts[i + 1])
            except ValueError:
                return _PROPOSAL_USAGE
            if limit < 0:
                return _PROPOSAL_USAGE
            i += 2
        else:
            return _PROPOSAL_USAGE
    return {"as_json": as_json, "status": status, "limit": limit}


def handle_proposals(command: str = "/proposals", *, workspace_root: str | Path = ".") -> str:
    from raiker.review.lifecycle import (
        ProposalLifecycleStore,
        records_to_json,
        render_records_text,
    )

    parsed = _parse_proposals_command(command)
    if isinstance(parsed, str):
        return parsed
    store = ProposalLifecycleStore(SQLiteStore(workspace_root))
    status_arg = parsed["status"]
    limit_val = parsed["limit"]
    records = store.list_records(
        status=status_arg if isinstance(status_arg, str) else None,
        limit=int(limit_val) if isinstance(limit_val, int) else 20,
    )
    if parsed["as_json"]:
        return records_to_json(records)
    return render_records_text(records)


def _parse_proposal_detail_command(command: str) -> dict[str, object] | str:
    parts = shlex.split(command)
    if len(parts) < 2:
        return _PROPOSAL_DETAIL_USAGE
    proposal_id = parts[1]
    if proposal_id.startswith("--"):
        return _PROPOSAL_DETAIL_USAGE
    as_json = False
    mark: str | None = None
    approval_preview = False
    i = 2
    while i < len(parts):
        arg = parts[i]
        if arg == "--json":
            as_json = True
            i += 1
        elif arg == "--mark" and i + 1 < len(parts):
            mark = parts[i + 1]
            if mark not in _PROPOSAL_STATUSES:
                return _PROPOSAL_DETAIL_USAGE
            i += 2
        elif arg == "--approval-preview":
            approval_preview = True
            i += 1
        else:
            return _PROPOSAL_DETAIL_USAGE
    return {
        "proposal_id": proposal_id,
        "as_json": as_json,
        "mark": mark,
        "approval_preview": approval_preview,
    }


def handle_proposal_detail(command: str, *, workspace_root: str | Path = ".") -> str:
    from raiker.review.approval_preview import (
        ProposalApprovalPreviewStore,
        preview_to_json,
        render_preview_text,
    )
    from raiker.review.lifecycle import (
        ProposalLifecycleError,
        ProposalLifecycleStore,
        record_to_json,
        render_record_text,
    )

    parsed = _parse_proposal_detail_command(command)
    if isinstance(parsed, str):
        return parsed
    proposal_id = str(parsed["proposal_id"])
    if not proposal_id.startswith("rap_"):
        return "Proposal not found."
    approval_preview = bool(parsed.get("approval_preview", False))
    store = ProposalLifecycleStore(SQLiteStore(workspace_root))
    mark = parsed["mark"]
    record = None
    if isinstance(mark, str):
        try:
            record = store.mark_status(proposal_id, new_status=mark)
        except ProposalLifecycleError:
            return "Proposal not found."
    else:
        record = store.get_record(proposal_id)
        if record is None:
            return "Proposal not found."
    assert record is not None

    if approval_preview:
        preview_store = ProposalApprovalPreviewStore(SQLiteStore(workspace_root))
        preview = preview_store.create_from_record(record)
        if parsed["as_json"]:
            return preview_to_json(preview)
        return render_preview_text(preview)

    if parsed["as_json"]:
        return record_to_json(record)
    return render_record_text(record)


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


def _memory_tool_result(title: str, result: dict[str, object]) -> str:
    lines = [f"{title}:"]
    for key, value in result.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def handle_memory_store(command: str, *, workspace_root: str | Path = ".") -> str:
    import shlex
    from raiker.tools.memory_tools import memory_write

    parts = shlex.split(command)
    if len(parts) < 2:
        return "Usage: /memory-store <text> [--scope <scope>] [--tag <tag>]"
    text = parts[1]
    scope = "project"
    tags: list[str] = []
    i = 2
    while i < len(parts):
        if parts[i] == "--scope" and i + 1 < len(parts):
            scope = parts[i + 1]
            i += 2
        elif parts[i] == "--tag" and i + 1 < len(parts):
            tags.append(parts[i + 1])
            i += 2
        else:
            text += " " + parts[i]
            i += 1
    result = memory_write(workspace_root, text, scope=scope, tags=tuple(tags))
    return _memory_tool_result("Memory store", result)


def handle_memory_search(command: str, *, workspace_root: str | Path = ".") -> str:
    import shlex
    from raiker.tools.memory_tools import memory_search

    parts = shlex.split(command)
    if len(parts) < 2:
        return "Usage: /memory-search <query> [--scope <scope>] [--max-results <n>]"
    query = parts[1]
    scope: str | None = None
    max_results = 20
    i = 2
    while i < len(parts):
        if parts[i] == "--scope" and i + 1 < len(parts):
            scope = parts[i + 1]
            i += 2
        elif parts[i] == "--max-results" and i + 1 < len(parts):
            try:
                max_results = int(parts[i + 1])
            except ValueError:
                return "Invalid --max-results value."
            i += 2
        else:
            i += 1
    result = memory_search(workspace_root, query, scope=scope, max_results=max_results)
    return _memory_tool_result("Memory search", result)


def handle_memory_forget(command: str, *, workspace_root: str | Path = ".") -> str:
    import shlex
    from raiker.tools.memory_tools import memory_forget

    parts = shlex.split(command)
    if len(parts) != 2:
        return "Usage: /memory-forget <memory_id>"
    result = memory_forget(workspace_root, parts[1])
    return _memory_tool_result("Memory forget", result)


def handle_memory_list_command(command: str, *, workspace_root: str | Path = ".") -> str:
    import shlex
    from raiker.tools.memory_tools import memory_list

    parts = shlex.split(command)
    scope: str | None = None
    limit = 50
    i = 1
    while i < len(parts):
        if parts[i] == "--scope" and i + 1 < len(parts):
            scope = parts[i + 1]
            i += 2
        elif parts[i] == "--limit" and i + 1 < len(parts):
            try:
                limit = int(parts[i + 1])
            except ValueError:
                return "Invalid --limit value."
            i += 2
        else:
            i += 1
    result = memory_list(workspace_root, scope=scope, limit=limit)
    return _memory_tool_result("Memory list", result)


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


def _profile_status(profile: ModelProfile) -> str:
    raw = profile.raw
    if raw.get("test_only"):
        return "test-only"
    if raw.get("requires_egress_policy") or raw.get("requires_budget_policy"):
        return "policy-gated"
    return str(raw.get("default_state", "unknown"))


def handle_providers(path: str | Path = "config/model-profiles.json") -> str:
    registry = ModelProfileRegistry.load(path)
    lines = ["Configured model provider profiles:"]
    from raiker.models.endpoint_policy import classify_endpoint

    for profile in registry.list_profiles():
        raw = profile.raw
        endpoint_kind = classify_endpoint(str(raw.get("endpoint") or raw.get("base_url") or ""))
        lines.append(
            f"- {profile.profile_id} provider={profile.provider} backend={raw.get('backend', 'unknown')} model={profile.model} state={_profile_status(profile)} endpoint_kind={endpoint_kind} health=unknown streaming={bool(raw.get('supports_streaming'))} embeddings={bool(raw.get('supports_embeddings'))} tool_calls={bool(raw.get('supports_tool_calls'))} reasoning={bool(raw.get('supports_reasoning'))}"
        )
    return "\n".join(lines)


def _append_model_event(store: SQLiteStore, event_type: str, payload: dict[str, object]) -> None:
    EventLogWriter(store).append(
        make_event(
            session_id=_model_session_id(),
            turn_id=None,
            event_type=event_type,
            actor="cli",
            payload=payload,
            client=terminal_client(),
        )
    )


def _profile_event_payload(profile: ModelProfile) -> dict[str, object]:
    return {
        "profile_id": profile.profile_id,
        "provider": profile.provider,
        "model": profile.model,
        "endpoint_kind": profile.raw.get("endpoint_kind", "unknown"),
    }


async def handle_model_command_async(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    registry = ModelProfileRegistry.load()
    router = ModelRouter(registry)
    store = SQLiteStore(workspace_root)
    selected = _selected_profile(registry, workspace_root)
    if len(parts) == 1 or parts[1] == "current":
        return _render_profile_current(selected)
    if parts[1] == "capabilities":
        caps = capabilities_from_profile(selected)
        _append_model_event(
            store,
            "model_capabilities_inspected",
            {
                **_profile_event_payload(selected),
                "supports_streaming": caps.supports_streaming,
                "supports_embeddings": caps.supports_embeddings,
                "supports_tool_calls": caps.supports_tool_calls,
                "supports_json_schema": caps.supports_json_schema,
                "supports_reasoning": caps.supports_reasoning,
                "reasoning_trace_visible": caps.reasoning_trace_visible,
            },
        )
        return _render_capabilities(selected)
    if parts[1] == "health":
        _append_model_event(store, "model_health_check_started", _profile_event_payload(selected))
        try:
            health = await router.ahealth(selected.provider, selected.model)
            payload = {
                **_profile_event_payload(selected),
                "available": health.available,
                "enabled_for_runtime": health.enabled_for_runtime,
                "detail": health.detail,
            }
            _append_model_event(store, "model_health_check_completed", payload)
            return f"Model health: available={health.available} enabled={health.enabled_for_runtime} detail={health.detail} endpoint_kind={selected.raw.get('endpoint_kind', 'unknown')}"
        except Exception as exc:
            payload = {
                **_profile_event_payload(selected),
                "available": False,
                "enabled_for_runtime": False,
                "detail": "unreachable",
                "error_class": type(exc).__name__,
            }
            _append_model_event(store, "model_health_check_completed", payload)
            return f"Model health: unreachable error_class={type(exc).__name__} endpoint_kind={selected.raw.get('endpoint_kind', 'unknown')}"
    if parts[1] == "use":
        try:
            if len(parts) >= 3 and not parts[2].startswith("--"):
                profile = router.select_profile(parts[2])
            else:
                parser = argparse.ArgumentParser(prog="/model use", add_help=False)
                parser.add_argument("--provider", required=True)
                parser.add_argument("--model", required=True)
                args = parser.parse_args(parts[2:])
                matches = registry.find(args.provider, args.model)
                if len(matches) != 1:
                    return "Model selection is ambiguous or unavailable; specify a profile_id."
                profile = router.select_profile(matches[0].profile_id)
            store.save_model_session_state(
                ModelSessionState(session_id=_model_session_id(), profile_id=profile.profile_id)
            )
            _append_model_event(store, "model_profile_selected", _profile_event_payload(profile))
            return f"Selected model profile {profile.profile_id} for this session."
        except Exception as exc:
            payload = {"error_class": type(exc).__name__, "safe_error_code": safe_error(str(exc))}
            if len(parts) >= 3:
                payload["profile_id"] = parts[2]
            _append_model_event(store, "model_provider_rejected_by_policy", payload)
            return f"Model selection failed: {type(exc).__name__}:{safe_error(str(exc))}"
    return "Usage: /model [current|use <profile_id>|use --provider <provider> --model <model>|health|capabilities]"


def handle_model_command(command: str, *, workspace_root: str | Path = ".") -> str:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(handle_model_command_async(command, workspace_root=workspace_root))
    return "Model command requires async command path; use handle_model_command_async."

def _render_profile_current(profile: ModelProfile) -> str:
    return "\n".join(
        [
            "Current model profile:",
            f"profile_id: {profile.profile_id}",
            f"provider: {profile.provider}",
            f"model: {profile.model}",
            f"endpoint_kind: {profile.raw.get('endpoint_kind', 'unknown')}",
            f"policy_status: {_profile_status(profile)}",
            f"reasoning: {'supported' if profile.raw.get('supports_reasoning') else 'unsupported'}",
            f"streaming: {bool(profile.raw.get('supports_streaming'))}",
            f"embeddings: {bool(profile.raw.get('supports_embeddings'))}",
        ]
    )


def _render_capabilities(profile: ModelProfile) -> str:
    raw = profile.raw
    return "\n".join(
        [
            "Model capabilities:",
            f"streaming: {bool(raw.get('supports_streaming'))}",
            f"embeddings: {bool(raw.get('supports_embeddings'))}",
            f"tool calls: {bool(raw.get('supports_tool_calls'))}",
            f"json schema: {bool(raw.get('supports_json_schema'))}",
            f"reasoning: {bool(raw.get('supports_reasoning'))}",
            f"reasoning effort: {bool(raw.get('supports_reasoning_effort'))}",
            f"reasoning budget tokens: {bool(raw.get('supports_reasoning_budget_tokens'))}",
            f"reasoning summary: {bool(raw.get('supports_reasoning_summary'))}",
            "private chain-of-thought exposure: never",
        ]
    )


def handle_reasoning_command(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    registry = ModelProfileRegistry.load()
    store = SQLiteStore(workspace_root)
    profile = _selected_profile(registry, workspace_root)
    if len(parts) == 1 or parts[1] == "status":
        if not profile.raw.get("supports_reasoning"):
            return "Reasoning controls are not available for the selected model/profile. Private chain-of-thought exposure: never."
        return "Reasoning controls available. Private chain-of-thought exposure: never."
    if parts[1] == "off":
        store.save_model_session_state(
            ModelSessionState(
                session_id=_model_session_id(),
                profile_id=profile.profile_id,
                reasoning_enabled=False,
            )
        )
        _append_model_event(
            store,
            "reasoning_setting_changed",
            {
                **_profile_event_payload(profile),
                "reasoning_enabled": False,
                "reasoning_effort": None,
                "reasoning_mode": None,
            },
        )
        return "Reasoning controls disabled."
    if parts[1] == "set" and len(parts) == 3:
        value = parts[2]
        if not profile.raw.get("supports_reasoning"):
            _append_model_event(
                store,
                "reasoning_setting_rejected",
                {
                    **_profile_event_payload(profile),
                    "attempted_value_length": len(value),
                    "attempted_value_class": "unsupported_token",
                    "reason": "reasoning_not_supported",
                },
            )
            return "Reasoning setting rejected: selected model/profile does not support reasoning controls."
        allowed = (
            set(profile.raw.get("reasoning_effort_values", []))
            | set(profile.raw.get("reasoning_modes", []))
            | {"off"}
        )
        if value not in allowed:
            _append_model_event(
                store,
                "reasoning_setting_rejected",
                {
                    **_profile_event_payload(profile),
                    "attempted_value_length": len(value),
                    "attempted_value_class": "unsupported_token",
                    "reason": "unsupported_value",
                },
            )
            return "Reasoning setting rejected: unsupported value for selected profile."
        state = ModelSessionState(
            session_id=_model_session_id(),
            profile_id=profile.profile_id,
            reasoning_enabled=True,
            reasoning_effort=value
            if value in set(profile.raw.get("reasoning_effort_values", []))
            else None,
            reasoning_mode=value if value in set(profile.raw.get("reasoning_modes", [])) else None,
        )
        store.save_model_session_state(state)
        _append_model_event(
            store,
            "reasoning_setting_changed",
            {
                **_profile_event_payload(profile),
                "reasoning_enabled": True,
                "reasoning_effort": state.reasoning_effort,
                "reasoning_mode": state.reasoning_mode,
            },
        )
        return f"Reasoning setting changed: {value}."
    return "Usage: /reasoning [status|set <mode-or-effort>|off]"


def handle_users(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    users = store.list_users()
    if not users:
        return "No users."
    lines = ["Users:"]
    for u in users:
        active = "active" if u.get("is_active") else "inactive"
        roles = store.list_user_roles(str(u["user_id"]))
        role_names = ", ".join(str(r.get("role_name", "")) for r in roles)
        lines.append(
            f"- {u['user_id']} display={u.get('display_name', '')} email={u.get('email', '')} "
            f"status={active} roles=[{role_names}]"
        )
    return "\n".join(lines)


def handle_user_create(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    if len(parts) < 3:
        return "Usage: /user create <user_id> [--display <name>] [--email <email>]"
    user_id = parts[2]
    display_name: str | None = None
    email: str | None = None
    i = 3
    while i < len(parts):
        if parts[i] == "--display" and i + 1 < len(parts):
            display_name = parts[i + 1]
            i += 2
        elif parts[i] == "--email" and i + 1 < len(parts):
            email = parts[i + 1]
            i += 2
        else:
            i += 1
    now = utc_now()
    user = User(user_id=user_id, display_name=display_name, email=email, is_active=True, created_at=now, updated_at=now)
    store = SQLiteStore(workspace_root)
    store.insert_user(user)
    return f"User created: {user_id}"


def handle_user_deactivate(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    if len(parts) != 3:
        return "Usage: /user deactivate <user_id>"
    store = SQLiteStore(workspace_root)
    if store.deactivate_user(parts[2]):
        return f"User deactivated: {parts[2]}"
    return f"User not found or already inactive: {parts[2]}"


def handle_roles(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    role_list = store.list_roles()
    if not role_list:
        return "No roles."
    lines = ["Roles:"]
    for r in role_list:
        system = "(system)" if r.get("is_system_role") else ""
        lines.append(f"- {r['role_id']} name={r.get('name', '')} {system}")
    return "\n".join(lines)


def handle_role_create(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    if len(parts) < 4:
        return "Usage: /role create <role_id> <name> [--description <text>]"
    role_id = parts[2]
    name = parts[3]
    description: str | None = None
    i = 4
    while i < len(parts):
        if parts[i] == "--description" and i + 1 < len(parts):
            description = parts[i + 1]
            i += 2
        else:
            i += 1
    now = utc_now()
    role = Role(role_id=role_id, name=name, description=description, is_system_role=False, created_at=now)
    store = SQLiteStore(workspace_root)
    store.insert_role(role)
    return f"Role created: {role_id} ({name})"


def handle_role_grant(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    if len(parts) < 5:
        return "Usage: /role grant <role_id> <user_id>"
    role_id = parts[2]
    user_id = parts[3]
    now = utc_now()
    assignment = UserRoleAssignment(
        assignment_id=new_id("ura_"),
        user_id=user_id,
        role_id=role_id,
        granted_at=now,
        granted_by="cli",
    )
    store = SQLiteStore(workspace_root)
    store.insert_user_role_assignment(assignment)
    return f"Role '{role_id}' granted to user '{user_id}'."


def handle_role_revoke(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    if len(parts) < 5:
        return "Usage: /role revoke <role_id> <user_id>"
    role_id = parts[2]
    user_id = parts[3]
    store = SQLiteStore(workspace_root)
    assignments = store.list_user_roles(user_id)
    for a in assignments:
        if str(a.get("role_id")) == role_id:
            if store.delete_user_role_assignment(str(a["assignment_id"])):
                return f"Role '{role_id}' revoked from user '{user_id}'."
    return f"No assignment found for role '{role_id}' on user '{user_id}'."


def handle_routines(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    routines = store.list_hosted_routines()
    if not routines:
        return "No hosted routines."
    lines = ["Hosted routines:"]
    for r in routines:
        enabled = "enabled" if r.get("enabled") else "disabled"
        lines.append(f"- {r['routine_id']} name={r.get('name', '')} type={r.get('routine_type', '')} {enabled}")
    return "\n".join(lines)


def handle_budgets(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    budgets = store.list_budget_records()
    if not budgets:
        return "No budget records."
    lines = ["Budget records:"]
    for b in budgets:
        enabled = "enabled" if b.get("enabled") else "disabled"
        pct = (float(b.get("current_cost", 0)) / float(b.get("max_cost", 1))) * 100 if float(b.get("max_cost", 0)) > 0 else 0
        lines.append(f"- {b['budget_id']} name={b.get('name', '')} cost={b.get('current_cost', 0)}/{b.get('max_cost', 0)} {b.get('currency', 'USD')} ({pct:.0f}%) {enabled}")
    return "\n".join(lines)


def handle_retention(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    policies = store.list_retention_policies()
    if not policies:
        return "No retention policies."
    lines = ["Retention policies:"]
    for p in policies:
        hold = "legal_hold" if p.get("legal_hold") else ""
        enabled = "enabled" if p.get("enabled") else "disabled"
        lines.append(f"- {p['policy_id']} target={p.get('target_type', '')} days={p.get('retention_days', 0)} {hold} {enabled}")
    backups = store.list_backup_manifests(limit=5)
    if backups:
        lines.append("Recent backup manifests:")
        for b in backups:
            lines.append(f"  - {b['manifest_id']} type={b.get('backup_type', '')} size={b.get('size_bytes', 'N/A')}")
    return "\n".join(lines)


def handle_channel_pair(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    pairings = store.list_channel_pairings()
    if not pairings:
        return "No channel pairings. Connector profiles are listed via /channels."
    lines = ["Channel pairings:"]
    for p in pairings:
        enabled = "enabled" if p.get("enabled") else "disabled"
        lines.append(f"- {p['pairing_id']} connector={p.get('connector_id', '')} type={p.get('channel_type', '')} {enabled}")
    return "\n".join(lines)


def handle_approval_relay(*, workspace_root: str | Path = ".") -> str:
    return "Approval relay is disabled by default. Use /channel-pair to list paired channels."


def handle_subagents(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    contracts = store.list_subagent_contracts()
    if not contracts:
        return "No subagent contracts. Subagent spawning is disabled by default."
    lines = ["Subagent contracts:"]
    for c in contracts:
        lines.append(f"- {c['subagent_id']} name={c.get('name', '')} mode={c.get('mode', '')} status={c.get('status', '')}")
    return "\n".join(lines)


def handle_teams(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    teams = store.list_team_ledgers()
    if not teams:
        return "No team ledgers. Multi-agent team coordination is disabled by default."
    lines = ["Team ledgers:"]
    for t in teams:
        lines.append(f"- {t['team_id']} name={t.get('name', '')} mode={t.get('mode', '')} status={t.get('status', '')}")
    return "\n".join(lines)


def handle_remote_exec_profiles(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    profiles = store.list_remote_execution_profiles()
    if not profiles:
        return "No remote execution profiles. Remote execution is denied by default."
    lines = ["Remote execution profiles:"]
    for p in profiles:
        enabled = "enabled" if p.get("enabled") else "disabled"
        lines.append(f"- {p['profile_id']} name={p.get('name', '')} type={p.get('profile_type', '')} {enabled}")
    return "\n".join(lines)


def handle_plugin_exec(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    records = store.list_plugin_execution_records()
    if not records:
        return "No plugin execution records. Plugin execution is denied by default."
    lines = ["Plugin execution records:"]
    for r in records:
        lines.append(f"- {r['execution_id']} plugin={r.get('plugin_id', '')} status={r.get('status', '')}")
    return "\n".join(lines)


def handle_graph_index(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    records = store.list_graph_index_records()
    if not records:
        return "No graph index records. Graph indexing is denied by default."
    lines = ["Graph index records:"]
    for r in records:
        lines.append(f"- {r['index_id']} status={r.get('status', '')} nodes={r.get('nodes_count', 0)} edges={r.get('edges_count', 0)}")
    return "\n".join(lines)


def handle_semantic_write(*, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    records = store.list_semantic_memory_writes()
    if not records:
        return "No semantic memory write records. Semantic writes are denied by default."
    lines = ["Semantic memory write records:"]
    for r in records:
        lines.append(f"- {r['write_id']} model={r.get('embedding_model', '')} vectors={r.get('vector_count', 0)} status={r.get('status', '')}")
    return "\n".join(lines)


def handle_export_command(command: str, *, workspace_root: str | Path = ".") -> str:
    parts = shlex.split(command)
    session_id: str | None = None
    redact = True
    verify = False
    i = 1
    while i < len(parts):
        if parts[i] == "--session" and i + 1 < len(parts):
            session_id = parts[i + 1]
            i += 2
        elif parts[i] == "--no-redact":
            redact = False
            i += 1
        elif parts[i] == "--verify":
            verify = True
            i += 1
        else:
            i += 1
    store = SQLiteStore(workspace_root)
    if verify:
        from raiker.events.integrity import verify_session_events
        if not session_id:
            return "Usage: /export --verify --session <session_id>"
        result = verify_session_events(store, session_id)
        lines = [
            f"Session: {result['session_id']}",
            f"Total events: {result['total_events']}",
            f"Passed: {result['passed']}",
            f"Failed: {result['failed']}",
            f"Chain intact: {result['chain_intact']}",
        ]
        for d in result["details"]:
            if d.get("hash_matches") is False or d.get("chain_gap"):
                lines.append(f"  FAIL: event={d['event_id']} error={d.get('error', 'chain_gap')}")
        return "\n".join(lines)
    from raiker.events.export import generate_export
    manifest = generate_export(store, session_id, redact=redact)
    lines = [
        f"Export created: {manifest.export_id}",
        f"  Events: {manifest.event_count}",
        f"  Redacted: {manifest.redacted}",
        f"  Manifest hash: {manifest.manifest_hash}",
        f"  Path: {manifest.export_path or 'N/A'}",
    ]
    if manifest.first_event_id:
        lines.append(f"  Range: {manifest.first_event_id} .. {manifest.last_event_id}")
    return "\n".join(lines)


def handle_slash_command(command: str, *, workspace_root: str | Path = ".") -> str:
    command = command.strip()
    if command in {"/quit", "/exit"}:
        return "Exiting Raiker."
    if command == "/help":
        return (
            "Commands: /help, /providers, /models, /model current, /model use <profile_id>, /model use --provider <provider> --model <model>, /model health, /model capabilities, /reasoning, /reasoning status, /reasoning set <mode-or-effort>, /reasoning off, /status, /tasks, /events, /checkpoints, /approvals, /approve <id>, /deny <id>, /memory, /semantic-memory, /capabilities, /execution-profiles, /workspace, /workspace-view, /clients, /plugins, /plugin-plan <manifest_path>, /graph-status, /graph-plan, /graph-readiness [--summary|--json], /memory-readiness [--summary|--json], /approval-readiness [--summary|--json], /cleanup-readiness [--summary|--json], /remote-readiness [--summary|--json], /plugin-readiness [--summary|--json], /channel-readiness [--summary|--json], /memory-review [--summary], /approval-previews, /approval-previews [--json] [--status <status>] [--limit <n>], /graph-approval-preview, /memory-approval-preview [--summary], /approval-preview <preview_id>, /approval-preview <preview_id> [--json], /approval-audit [--summary], /rollback-plan, /graph-rollback-plan, /memory-rollback-plan, /storage-lifecycle [--summary|--graph|--memory], /storage-lifecycle-retention [--summary], /storage-lifecycle-cleanup-preview [--summary], /storage-lifecycle-handoff [--summary], /storage-lifecycle-evidence [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>], /storage-lifecycle-policy-simulation [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>], /review [--summary] [--staged] [--path <path>] [--json] [--limit <number>] [--severity <info|low|medium|high>] [--propose-fixes] [--proposals-only] [--save-proposals], /proposals [--json] [--status <proposed|acknowledged|deferred|rejected|superseded>] [--limit <number>], /proposal <proposal_id> [--json] [--mark <proposed|acknowledged|deferred|rejected|superseded>] [--approval-preview], /doctor, /channels, /launch --provider mock --model mock-deterministic (test-only; policy-blocked in normal CLI), /quit\n"
            "Status: Phase 3 Slice B approval planning preview is implemented. Phase 3 is complete for safe foundation/readiness slices A-P; Phase 4 is blocked; runtime execution remains disabled. Current launchable UI is a simple terminal/CLI shell. Desktop/Web/Dashboard/Mobile/REST/Rich TUI panels are contract-only or specified/deferred unless explicitly implemented. Phase 3 and Phase 4 commands are read-only, planning, preview, or metadata-only surfaces."
        )
    if command == "/providers":
        return handle_providers()
    if command == "/models":
        return render_models(workspace_root=workspace_root)
    if command == "/model" or command.startswith("/model "):
        return handle_model_command(command, workspace_root=workspace_root)
    if command == "/reasoning" or command.startswith("/reasoning "):
        return handle_reasoning_command(command, workspace_root=workspace_root)
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
    if command == "/memory-store" or command.startswith("/memory-store "):
        return handle_memory_store(command, workspace_root=workspace_root)
    if command == "/memory-search" or command.startswith("/memory-search "):
        return handle_memory_search(command, workspace_root=workspace_root)
    if command == "/memory-forget" or command.startswith("/memory-forget "):
        return handle_memory_forget(command, workspace_root=workspace_root)
    if command == "/memory-list" or command.startswith("/memory-list "):
        return handle_memory_list_command(command, workspace_root=workspace_root)
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
    if command == "/graph-readiness" or command.startswith("/graph-readiness "):
        return handle_graph_readiness(command, workspace_root=workspace_root)
    if command == "/memory-readiness" or command.startswith("/memory-readiness "):
        return handle_memory_readiness(command, workspace_root=workspace_root)
    if command == "/approval-readiness" or command.startswith("/approval-readiness "):
        return handle_approval_readiness(command, workspace_root=workspace_root)
    if command == "/cleanup-readiness" or command.startswith("/cleanup-readiness "):
        return handle_cleanup_readiness(command, workspace_root=workspace_root)
    if command == "/remote-readiness" or command.startswith("/remote-readiness "):
        return handle_remote_readiness(command, workspace_root=workspace_root)
    if command == "/plugin-readiness" or command.startswith("/plugin-readiness "):
        return handle_plugin_readiness(command, workspace_root=workspace_root)
    if command == "/channel-readiness" or command.startswith("/channel-readiness "):
        return handle_channel_readiness(command, workspace_root=workspace_root)
    if command == "/memory-review" or command.startswith("/memory-review "):
        return handle_memory_review(command, workspace_root=workspace_root)
    if command == "/approval-previews" or command.startswith("/approval-previews "):
        return handle_approval_previews(command, workspace_root=workspace_root)
    if command == "/graph-approval-preview":
        return handle_graph_approval_preview(workspace_root=workspace_root)
    if command == "/memory-approval-preview" or command.startswith("/memory-approval-preview "):
        return handle_memory_approval_preview(command, workspace_root=workspace_root)
    if command == "/approval-preview" or command.startswith("/approval-preview "):
        return handle_approval_preview_lookup(command, workspace_root=workspace_root)
    if command == "/approval-audit" or command.startswith("/approval-audit "):
        return handle_approval_audit(command, workspace_root=workspace_root)
    if command == "/rollback-plan":
        return handle_rollback_plan(workspace_root=workspace_root)
    if command == "/graph-rollback-plan":
        return handle_graph_rollback_plan(workspace_root=workspace_root)
    if command == "/memory-rollback-plan":
        return handle_memory_rollback_plan(workspace_root=workspace_root)
    if command == "/storage-lifecycle" or command.startswith("/storage-lifecycle "):
        return handle_storage_lifecycle(command, workspace_root=workspace_root)
    if (
        command
        in {
            "/storage-lifecycle-retention",
            "/storage-lifecycle-cleanup-preview",
            "/storage-lifecycle-handoff",
        }
        or command.startswith("/storage-lifecycle-retention ")
        or command.startswith("/storage-lifecycle-cleanup-preview ")
        or command.startswith("/storage-lifecycle-handoff ")
    ):
        return handle_storage_lifecycle_slice_h(command, workspace_root=workspace_root)
    if command == "/storage-lifecycle-evidence" or command.startswith(
        "/storage-lifecycle-evidence "
    ):
        return handle_storage_lifecycle_evidence(command, workspace_root=workspace_root)
    if command == "/storage-lifecycle-policy-simulation" or command.startswith(
        "/storage-lifecycle-policy-simulation "
    ):
        return handle_storage_lifecycle_policy_simulation(command, workspace_root=workspace_root)
    if command == "/clients":
        return handle_clients()
    if command == "/plugins":
        return handle_plugins(workspace_root=workspace_root)
    if command == "/plugin-plan" or command.startswith("/plugin-plan "):
        return handle_plugin_plan(command, workspace_root=workspace_root)
    if command == "/review" or command.startswith("/review "):
        return handle_review(command, workspace_root=workspace_root)
    if command == "/proposals" or command.startswith("/proposals "):
        return handle_proposals(command, workspace_root=workspace_root)
    if command == "/proposal" or command.startswith("/proposal "):
        return handle_proposal_detail(command, workspace_root=workspace_root)
    if command == "/users":
        return handle_users(workspace_root=workspace_root)
    if command == "/user create" or command.startswith("/user create "):
        return handle_user_create(command, workspace_root=workspace_root)
    if command == "/user deactivate" or command.startswith("/user deactivate "):
        return handle_user_deactivate(command, workspace_root=workspace_root)
    if command == "/roles":
        return handle_roles(workspace_root=workspace_root)
    if command == "/role create" or command.startswith("/role create "):
        return handle_role_create(command, workspace_root=workspace_root)
    if command == "/role grant" or command.startswith("/role grant "):
        return handle_role_grant(command, workspace_root=workspace_root)
    if command == "/role revoke" or command.startswith("/role revoke "):
        return handle_role_revoke(command, workspace_root=workspace_root)
    if command == "/routines":
        return handle_routines(workspace_root=workspace_root)
    if command == "/channel-pair":
        return handle_channel_pair(workspace_root=workspace_root)
    if command == "/approval-relay":
        return handle_approval_relay(workspace_root=workspace_root)
    if command == "/subagents":
        return handle_subagents(workspace_root=workspace_root)
    if command == "/teams":
        return handle_teams(workspace_root=workspace_root)
    if command == "/remote-exec":
        return handle_remote_exec_profiles(workspace_root=workspace_root)
    if command == "/plugin-exec":
        return handle_plugin_exec(workspace_root=workspace_root)
    if command == "/graph-index":
        return handle_graph_index(workspace_root=workspace_root)
    if command == "/semantic-write":
        return handle_semantic_write(workspace_root=workspace_root)
    if command == "/budgets":
        return handle_budgets(workspace_root=workspace_root)
    if command == "/retention":
        return handle_retention(workspace_root=workspace_root)
    if command == "/export" or command.startswith("/export "):
        return handle_export_command(command, workspace_root=workspace_root)
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
