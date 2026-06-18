from __future__ import annotations

PHASE_3_DISABLED_CAPABILITIES = {
    "desktop_ui",
    "web_ui",
    "dashboard",
    "plugin_execution",
    "graph_codemap_indexing",
    "semantic_memory_writes",
}
PHASE_4_DISABLED_CAPABILITIES = {
    "external_channels",
    "subagents",
    "multi_agent_teams",
    "remote_execution",
    "container_execution",
}


def list_disabled_capabilities() -> dict[str, list[str]]:
    return {
        "phase_3": sorted(PHASE_3_DISABLED_CAPABILITIES),
        "phase_4": sorted(PHASE_4_DISABLED_CAPABILITIES),
    }


def assert_capability_disabled(capability: str) -> None:
    if capability in PHASE_3_DISABLED_CAPABILITIES | PHASE_4_DISABLED_CAPABILITIES:
        raise PermissionError(f"phase_gated_disabled:{capability}")
