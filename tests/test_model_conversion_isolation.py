from __future__ import annotations

import json
from pathlib import Path

from raiker.models.conversion import ModelConversionService, docker_command_plan


def test_conversion_worker_has_no_network_credentials_or_workspace_mount(tmp_path: Path) -> None:
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "config.json").write_text(
        json.dumps({"architectures": ["Qwen2ForCausalLM"]}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe")
    output = tmp_path / "output"
    output.mkdir()

    worker = ModelConversionService().preview(source, output, "c" * 40, "Q5_K_M").isolation

    assert worker.network is False
    assert worker.source_read_only is True
    assert worker.credential_environment == ()
    assert worker.workspace_mounted is False
    assert worker.max_memory_bytes > 0
    assert worker.max_cpu_count > 0
    assert worker.timeout_seconds > 0


def test_docker_argv_enforces_isolation_without_a_shell(tmp_path: Path) -> None:
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "config.json").write_text(
        json.dumps({"architectures": ["Qwen2ForCausalLM"]}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe")
    output = tmp_path / "output"
    output.mkdir()
    preview = ModelConversionService().preview(source, output, "e" * 40, "Q4_K_M")

    convert, quantize = docker_command_plan(preview, "docker")

    for argv in (convert, quantize):
        assert argv[0:2] == ["docker", "run"]
        assert argv[argv.index("--network") + 1] == "none"
        assert "--read-only" in argv
        mounts = [argv[index + 1] for index, value in enumerate(argv) if value == "--mount"]
        assert len(mounts) == 2
        assert mounts[0].endswith("dst=/models/source,readonly")
        assert mounts[1].endswith("dst=/models/output")
        assert preview.toolchain_image in argv
