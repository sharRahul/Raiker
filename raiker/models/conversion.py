"""Converting a model the owner already has into one this machine can serve.

The conversion toolchain (llama.cpp's converter and quantizer) previously ran
in a Docker container. Docker was removed by the native sandbox migration and a
native, sandboxed toolchain is not yet packaged, so :class:`UnavailableConversionRunner`
refuses every conversion with ``model_conversion_native_toolchain_required``.
Previews, provenance and cleanup remain, so stored operations still read
correctly and an owner is told exactly why the conversion cannot start.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from raiker.contracts.views import View

#: Recorded on previews in place of the retired container image digest.
TOOLCHAIN_IMAGE = "native_toolchain_required"
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


class ConversionCancelled(ConversionRefused):
    """The owner stopped this conversion while it was running (GCR-24).

    A subclass, so a caller that only knows about refusals still catches it, and
    a caller that cares can tell the two apart. They are different sentences to
    an owner: one says the work broke, the other says they stopped it.
    """


@dataclass(frozen=True)
class ConversionIsolation(View):
    network: Literal[False] = False
    source_read_only: Literal[True] = True
    credential_environment: tuple[str, ...] = ()
    workspace_mounted: Literal[False] = False
    max_memory_bytes: int = 16 * 1024**3
    max_cpu_count: int = 4
    max_processes: int = 256
    timeout_seconds: int = 6 * 60 * 60


@dataclass(frozen=True)
class ConversionPreview(View):
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


@dataclass(frozen=True)
class ConversionProvenance(View):
    source_revision: str
    source_fingerprint: str
    output_fingerprint: str
    toolchain_image: str
    architecture: str
    quantization: str
    output_path: str


class UnavailableConversionRunner:
    """Refuses: no verified native conversion toolchain is installed."""

    def run(
        self,
        preview: ConversionPreview,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ConversionProvenance:
        del preview, should_cancel
        raise ConversionRefused("model_conversion_native_toolchain_required")


class ModelConversionService:
    def __init__(self, runner: UnavailableConversionRunner | None = None) -> None:
        self.runner = runner or UnavailableConversionRunner()

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

    def convert(
        self,
        preview: ConversionPreview,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ConversionProvenance:
        return self.runner.run(preview, should_cancel)


def _output_paths(preview: ConversionPreview) -> tuple[Path, Path]:
    source = Path(preview.source)
    output = Path(preview.output)
    stem = f"{source.name}-{preview.revision[:12]}"
    return (
        output / f"{stem}.bf16.gguf",
        output / f"{stem}.{preview.quantization}.gguf",
    )


def _provenance_path(output: Path, result: Path) -> Path:
    return output / f"{result.name}.provenance.json"


def conversion_artifacts(preview: ConversionPreview) -> tuple[Path, ...]:
    """Every path this conversion can create — and nothing else it may delete.

    The output directory is a *library* directory the owner chose: converting a
    second model into it is the ordinary case, so the directory is never the
    boundary of a cleanup. These three paths are, and they are derived here
    rather than at each call site so the runner that writes them and the
    cleanup that removes them cannot drift apart (GCR-19).
    """
    intermediate, result = _output_paths(preview)
    return (intermediate, result, _provenance_path(Path(preview.output), result))


def _source_fingerprint(source: Path, revision: str) -> str:
    """What this conversion was made from, as a content-integrity claim (GCR-26).

    Every included file's *content* is hashed: a path and a length are not an
    identity, and a weights file edited in place at the same length must change
    the fingerprint. Three details that matter:

    * **Each file's own digest goes in**, rather than the bytes being streamed
      into one running hash, so two files whose contents could be re-split
      across a boundary cannot produce the same value.
    * **The length of each field is written before it**, so a filename ending
      where the next one begins cannot be rearranged into the same byte stream.
    * **The order is the sorted relative path**, so the same tree fingerprints
      the same way wherever it is mounted.

    The cost is one full read of the snapshot. That is a fraction of a
    conversion that has just read all of it several times, and it is what makes
    the recorded value mean what the record says it means.
    """
    digest = hashlib.sha256()
    _feed(digest, b"raiker.conversion.source.v2")
    _feed(digest, revision.encode("ascii"))
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        _feed(digest, path.relative_to(source).as_posix().encode("utf-8"))
        _feed(digest, _sha256_file(path).encode("ascii"))
    return digest.hexdigest()


def _feed(digest: Any, field: bytes) -> None:
    """Length-prefix one field, so the concatenation cannot be re-partitioned."""
    digest.update(len(field).to_bytes(8, "big"))
    digest.update(field)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
