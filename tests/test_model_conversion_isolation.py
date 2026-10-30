from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.models.conversion import ConversionRefused, ModelConversionService


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


def test_conversion_refuses_until_a_native_toolchain_exists(tmp_path: Path) -> None:
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "config.json").write_text(
        json.dumps({"architectures": ["Qwen2ForCausalLM"]}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe")
    output = tmp_path / "output"
    output.mkdir()
    service = ModelConversionService()
    preview = service.preview(source, output, "e" * 40, "Q4_K_M")

    with pytest.raises(ConversionRefused, match="model_conversion_native_toolchain_required"):
        service.convert(preview)
    assert list(output.iterdir()) == []
