from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from raiker.models.gguf import read_gguf_metadata

TOOLCHAIN_IMAGE = (
    "ghcr.io/ggml-org/llama.cpp@"
    "sha256:bd00b69f6efef29e3fda689ea584e8fdd0a33a87860f700b16fecab147ac72f1"
)
SUPPORTED_ARCHITECTURES = frozenset(
    {
        "LlamaForCausalLM",
        "MistralForCausalLM",
        "MixtralForCausalLM",
        "Qwen2ForCausalLM",
        "Qwen3ForCausalLM",
        "GemmaForCausalLM",
        "Gemma2ForCausalLM",
        "Phi3ForCausalLM",
    }
)
SUPPORTED_QUANTIZATIONS = frozenset({"Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"})


class ConversionRefused(ValueError):
    pass


@dataclass(frozen=True)
class ConversionIsolation:
    network: bool = False
    source_read_only: bool = True
    credential_environment: tuple[str, ...] = ()
    workspace_mounted: bool = False
    max_memory_bytes: int = 16 * 1024**3
    max_cpu_count: int = 4
    max_processes: int = 256
    timeout_seconds: int = 6 * 60 * 60


@dataclass(frozen=True)
class ConversionPreview:
    source: str
    output: str
    revision: str
    architecture: str
    quantization: str
    source_bytes: int
    required_free_bytes: int
    toolchain_image: str
    convert_argv: tuple[str, ...]
    quantize_argv: tuple[str, ...]
    isolation: ConversionIsolation

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConversionProvenance:
    source_revision: str
    source_fingerprint: str
    output_fingerprint: str
    toolchain_image: str
    architecture: str
    quantization: str
    output_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DockerConversionRunner:
    def run(self, preview: ConversionPreview) -> ConversionProvenance:
        docker = shutil.which("docker")
        if not docker:
            raise ConversionRefused("isolated_conversion_worker_unavailable")
        source = Path(preview.source)
        output = Path(preview.output)
        intermediate, result = _output_paths(preview)
        convert, quantize = docker_command_plan(preview, docker)
        clean_env = {"PATH": str(Path(docker).parent)}
        if os.name == "nt" and os.environ.get("SYSTEMROOT"):
            clean_env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        for argv in (convert, quantize):
            completed = subprocess.run(
                argv,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                timeout=preview.isolation.timeout_seconds,
                env=clean_env,
            )
            if completed.returncode != 0:
                raise ConversionRefused("isolated_conversion_failed")
        metadata = read_gguf_metadata(result)
        if metadata.architecture.strip() == "":
            raise ConversionRefused("converted_gguf_invalid")
        provenance = ConversionProvenance(
            source_revision=preview.revision,
            source_fingerprint=_source_fingerprint(source, preview.revision),
            output_fingerprint=_sha256_file(result),
            toolchain_image=preview.toolchain_image,
            architecture=preview.architecture,
            quantization=preview.quantization,
            output_path=str(result.resolve()),
        )
        (output / f"{result.name}.provenance.json").write_text(
            json.dumps(provenance.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
        )
        intermediate.unlink(missing_ok=True)
        return provenance


class ModelConversionService:
    def __init__(self, runner: DockerConversionRunner | None = None) -> None:
        self.runner = runner or DockerConversionRunner()

    def preview(
        self, source: Path, output: Path, revision: str, quantization: str
    ) -> ConversionPreview:
        source = source.resolve()
        output = output.resolve()
        if len(revision) != 40 or any(
            character not in "0123456789abcdefABCDEF" for character in revision
        ):
            raise ConversionRefused("immutable_revision_required")
        if quantization not in SUPPORTED_QUANTIZATIONS:
            raise ConversionRefused("unsupported_quantization")
        if not source.is_dir() or not output.is_dir():
            raise ConversionRefused("conversion_path_missing")
        if source == output or source in output.parents or output in source.parents:
            raise ConversionRefused("conversion_mounts_must_be_separate")
        safetensors = sorted(source.glob("*.safetensors"))
        if not safetensors or any(source.glob("*.bin")) or any(source.glob("*.pt")):
            raise ConversionRefused("safetensors_required")
        config_path = source / "config.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            architecture = str(config["architectures"][0])
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ConversionRefused("model_config_invalid") from exc
        if architecture not in SUPPORTED_ARCHITECTURES:
            raise ConversionRefused("unsupported_model_architecture")
        source_bytes = sum(path.stat().st_size for path in source.rglob("*") if path.is_file())
        required = max(source_bytes * 3, 64 * 1024**2)
        if shutil.disk_usage(output).free < required:
            raise ConversionRefused("insufficient_conversion_disk_space")
        intermediate = "/models/output/model.bf16.gguf"
        result = f"/models/output/model.{quantization}.gguf"
        return ConversionPreview(
            source=str(source),
            output=str(output),
            revision=revision.lower(),
            architecture=architecture,
            quantization=quantization,
            source_bytes=source_bytes,
            required_free_bytes=required,
            toolchain_image=TOOLCHAIN_IMAGE,
            convert_argv=(
                "python",
                "/app/convert_hf_to_gguf.py",
                "/models/source",
                "--outfile",
                intermediate,
                "--outtype",
                "bf16",
            ),
            quantize_argv=("/app/llama-quantize", intermediate, result, quantization),
            isolation=ConversionIsolation(),
        )

    def convert(self, preview: ConversionPreview) -> ConversionProvenance:
        return self.runner.run(preview)


def docker_command_plan(preview: ConversionPreview, docker: str) -> tuple[list[str], list[str]]:
    source = Path(preview.source)
    output = Path(preview.output)
    intermediate, result = _output_paths(preview)
    base = [
        docker,
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cpus",
        str(preview.isolation.max_cpu_count),
        "--memory",
        str(preview.isolation.max_memory_bytes),
        "--pids-limit",
        str(preview.isolation.max_processes),
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=2g",
        "--mount",
        f"type=bind,src={source},dst=/models/source,readonly",
        "--mount",
        f"type=bind,src={output},dst=/models/output",
    ]
    convert = base + [
        "--entrypoint",
        "python",
        preview.toolchain_image,
        *preview.convert_argv[1:-3],
        "/models/output/" + intermediate.name,
        *preview.convert_argv[-2:],
    ]
    quantize = base + [
        "--entrypoint",
        "/app/llama-quantize",
        preview.toolchain_image,
        "/models/output/" + intermediate.name,
        "/models/output/" + result.name,
        preview.quantization,
    ]
    return convert, quantize


def _output_paths(preview: ConversionPreview) -> tuple[Path, Path]:
    source = Path(preview.source)
    output = Path(preview.output)
    stem = f"{source.name}-{preview.revision[:12]}"
    return (
        output / f"{stem}.bf16.gguf",
        output / f"{stem}.{preview.quantization}.gguf",
    )


def _source_fingerprint(source: Path, revision: str) -> str:
    digest = hashlib.sha256(revision.encode("ascii"))
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        relative = path.relative_to(source).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("ascii"))
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
