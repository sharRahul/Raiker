from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from raiker.channels.registry import ConnectorRegistry
from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, PromptEnvelope, PromptOptions, PromptPayload, UserMetadata
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.registry import ModelProfileRegistry, RegistryError
from raiker.models.router import ModelRouter
from raiker.storage.sqlite import SQLiteStore


def terminal_client() -> ClientMetadata:
    return ClientMetadata(
        type="tui",
        name="raiker-terminal",
        version="0.0.0",
        interface_status="equal_primary_when_enabled",
    )


def build_prompt_envelope(prompt: str, *, session_id: str | None = None, client: ClientMetadata | None = None) -> PromptEnvelope:
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


def handle_slash_command(command: str, *, workspace_root: str | Path = ".") -> str:
    command = command.strip()
    if command in {"/quit", "/exit"}:
        return "Exiting Raiker."
    if command == "/help":
        return "Commands: /help, /channels, /models, /launch --provider mock --model mock-deterministic, /quit"
    if command == "/models":
        return render_models()
    if command == "/channels":
        return render_channels()
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
        parts.append(f"Approval card: action={response.approval['action_id']} tool={response.approval['tool_name']} risk={response.approval['risk_level']}")
    if response.events_path:
        parts.append(f"events: {response.events_path}")
    if response.checkpoint_path:
        parts.append(f"checkpoint: {response.checkpoint_path}")
    return "\n".join(parts)
