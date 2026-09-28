from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_known_raiker_internal_writers_use_the_storage_boundary() -> None:
    files = [
        "raiker/api/app.py",
        "raiker/api/routes_models.py",
        "raiker/app/backup.py",
        "raiker/app/host.py",
        "raiker/app/uninstall.py",
        "raiker/auth/app_key.py",
        "raiker/auth/vault_key_file.py",
        # GCR-43 — the service's parts that write under `.raiker`. The service
        # module itself is no longer listed: its one remaining `.raiker` path is
        # `_project_migration_area`, which must see a symlinked `.raiker` in
        # order to refuse it, and `internal_io_path` resolves symlinks away. It
        # passed this text check before only because other code in the same
        # file used the helper.
        "raiker/control/dashboard_parts/knowledge.py",
        "raiker/control/dashboard_parts/memory.py",
        "raiker/execution/container_tools.py",
        "raiker/execution/commands/backends/container.py",
        "raiker/execution/commands/backends/native.py",
        "raiker/memory/integrity.py",
        "raiker/memory/store.py",
        "raiker/runtime/executors/containers.py",
        "raiker/storage/sqlcipher_probe.py",
    ]
    offenders: list[str] = []
    for relative in files:
        text = (ROOT / relative).read_text(encoding="utf-8")
        if (' / ".raiker"' in text or " / '.raiker'" in text) and "internal_io_path" not in text:
            offenders.append(relative)
    assert offenders == [], f"Raiker-owned writers bypass internal_io_path: {offenders}"


def test_cli_and_export_surfaces_do_not_render_extended_paths() -> None:
    consumers = [
        "raiker/cli/commands.py",
        "raiker/control/dashboard_parts/memory.py",
        "raiker/events/export.py",
    ]
    missing = [
        relative
        for relative in consumers
        if "display_path" not in (ROOT / relative).read_text(encoding="utf-8")
    ]
    assert missing == [], f"Internal paths cross a display boundary in: {missing}"
