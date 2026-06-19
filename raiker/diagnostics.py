from __future__ import annotations

from pathlib import Path

from raiker.models.health import check_local_provider
from raiker.phase_gates import list_disabled_capabilities
from raiker.storage.sqlite import SQLiteStore


def render_doctor(workspace_root: str | Path) -> str:
    store = SQLiteStore(workspace_root)
    health = check_local_provider("llama.cpp")
    disabled = list_disabled_capabilities()
    lines = [
        "Raiker doctor:",
        f"database: {store.db_path}",
        f"llama_cpp_available: {health.available}",
        f"llama_cpp_runtime_enabled: {health.enabled_for_runtime}",
        f"phase_3_disabled: {', '.join(disabled['phase_3'])}",
        f"phase_4_disabled: {', '.join(disabled['phase_4'])}",
    ]
    return "\n".join(lines)
