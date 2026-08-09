from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.models.conversion import ConversionRefused, ModelConversionService

REVISION = "b" * 40


def _snapshot(tmp_path: Path, *, architecture: str = "LlamaForCausalLM") -> Path:
    source = tmp_path / "snapshot"
    source.mkdir(parents=True)
    (source / "config.json").write_text(
        json.dumps({"architectures": [architecture], "model_type": "llama"}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe tensor bytes")
    (source / "tokenizer.json").write_text("{}", encoding="utf-8")
    return source


def test_supported_safetensors_snapshot_produces_pinned_commands(tmp_path: Path) -> None:
    source = _snapshot(tmp_path)
    output = tmp_path / "output"
    output.mkdir()

    preview = ModelConversionService().preview(source, output, REVISION, "Q4_K_M")

    assert preview.architecture == "LlamaForCausalLM"
    assert preview.revision == REVISION
    assert preview.quantization == "Q4_K_M"
    assert preview.toolchain_image.endswith(
        "@sha256:bd00b69f6efef29e3fda689ea584e8fdd0a33a87860f700b16fecab147ac72f1"
    )
    assert preview.convert_argv[0:2] == ("python", "/app/convert_hf_to_gguf.py")
    assert preview.quantize_argv[0] == "/app/llama-quantize"
    assert "--outtype" in preview.convert_argv


def test_conversion_rejects_repository_code_and_pickle_weights(tmp_path: Path) -> None:
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "config.json").write_text('{"architectures":["LlamaForCausalLM"]}', encoding="utf-8")
    (source / "modeling_custom.py").write_text(
        "raise RuntimeError('must not run')", encoding="utf-8"
    )
    (source / "pytorch_model.bin").write_bytes(b"pickle")
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(ConversionRefused, match="safetensors_required"):
        ModelConversionService().preview(source, output, REVISION, "Q4_K_M")


def test_conversion_rejects_unsupported_architecture_and_moving_revision(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(ConversionRefused, match="unsupported_model_architecture"):
        ModelConversionService().preview(
            _snapshot(tmp_path, architecture="UnknownRemoteCode"), output, REVISION, "Q4_K_M"
        )
    with pytest.raises(ConversionRefused, match="immutable_revision_required"):
        ModelConversionService().preview(_snapshot(tmp_path / "second"), output, "main", "Q4_K_M")
