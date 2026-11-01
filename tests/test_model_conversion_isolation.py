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


def _snapshot(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "config.json").write_text(
        json.dumps({"architectures": ["Qwen2ForCausalLM"]}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe")
    output = tmp_path / "output"
    output.mkdir()
    return source, output


@pytest.mark.parametrize(
    ("present", "reason"),
    [
        ((), "model_conversion_converter_missing"),
        (("convert_hf_to_gguf.py",), "model_conversion_quantizer_missing"),
        (("convert_hf_to_gguf.py", "llama-quantize"), "model_conversion_python_missing"),
    ],
)
def test_a_named_toolchain_missing_a_part_is_refused_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, present: tuple[str, ...], reason: str
) -> None:
    import sys

    toolchain = tmp_path / "llama.cpp"
    toolchain.mkdir()
    for name in present:
        suffix = ".exe" if name == "llama-quantize" and sys.platform == "win32" else ""
        (toolchain / f"{name}{suffix}").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIKER_LLAMA_CPP_DIR", str(toolchain))
    with pytest.raises(ConversionRefused, match=reason):
        ModelConversionService()


def test_a_real_conversion_runs_in_the_sandbox_and_writes_only_its_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real boundary (Linux): a stand-in llama.cpp, the model mounted read-only."""
    import subprocess
    import sys

    from raiker.execution.commands.backends.native import NativeSandboxDriver
    from raiker.models.conversion import NativeConversionRunner

    if not sys.platform.startswith("linux"):
        pytest.skip("the boundary mounts a model read-only on Linux only")
    probe_root = NativeConversionRunner.STATE
    probe_root.mkdir(parents=True, exist_ok=True)
    if not NativeSandboxDriver(probe_root).probe().available:
        pytest.skip("no enforced native boundary on this host")
    source, output = _snapshot(tmp_path)
    toolchain = tmp_path / "llama.cpp"
    toolchain.mkdir()
    subprocess.run(["/usr/bin/python3", "-m", "venv", str(toolchain / ".venv")], check=True)
    # The converter proves the model is readable and not writable.
    (toolchain / "convert_hf_to_gguf.py").write_text(
        "import sys, pathlib\n"
        "source, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[3])\n"
        "try:\n"
        "    (source / 'planted').write_text('x')\n"
        "    sys.exit(3)\n"
        "except OSError:\n"
        "    pass\n"
        "out.write_bytes(b'GGUF' + (source / 'model.safetensors').read_bytes())\n",
        encoding="utf-8",
    )
    quantize = toolchain / "llama-quantize"
    quantize.write_text('#!/bin/sh\n/usr/bin/cp "$1" "$2"\n', encoding="utf-8")
    quantize.chmod(0o755)
    monkeypatch.setenv("RAIKER_LLAMA_CPP_DIR", str(toolchain))

    service = ModelConversionService()
    preview = service.preview(source, output, "f" * 40, "Q4_K_M")
    provenance = service.convert(preview)

    result = Path(provenance.output_path)
    assert result.read_bytes() == b"GGUFsafe"
    assert not (source / "planted").exists()
    assert provenance.toolchain_image.startswith("llama.cpp:sha256:")
    assert sorted(path.name for path in output.iterdir()) == sorted(
        [result.name, result.name.replace("Q4_K_M", "bf16"), f"{result.name}.provenance.json"]
    )
