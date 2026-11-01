"""Converting a model the owner already has into one this machine can serve.

The conversion toolchain (llama.cpp's converter and quantizer) previously ran
in a Docker container, which the native sandbox migration removed. It now runs
in the native sandbox, from a llama.cpp the owner installed and named in
``RAIKER_LLAMA_CPP_DIR`` (:class:`NativeConversionRunner`). Without one, or on a
host whose boundary cannot mount the model read-only, every conversion is
refused with a named reason. Previews, provenance and cleanup are unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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


#: The variable naming the owner's llama.cpp: a folder holding
#: `convert_hf_to_gguf.py`, a built `llama-quantize` (or `build/bin/…`), and a
#: `.venv` with the converter's requirements installed.
TOOLCHAIN_VARIABLE = "RAIKER_LLAMA_CPP_DIR"


@dataclass(frozen=True)
class LlamaCppToolchain:
    root: Path
    python: Path
    converter: Path
    quantizer: Path

    @classmethod
    def locate(cls, root: Path) -> LlamaCppToolchain:
        """The toolchain in *root*, or a refusal naming the part that is missing."""
        root = root.resolve()
        windows = sys.platform == "win32"
        python = root / ".venv" / ("Scripts/python.exe" if windows else "bin/python")
        converter = root / "convert_hf_to_gguf.py"
        name = "llama-quantize.exe" if windows else "llama-quantize"
        quantizer = next(
            (path for path in (root / name, root / "build" / "bin" / name) if path.is_file()), None
        )
        if not converter.is_file():
            raise ConversionRefused("model_conversion_converter_missing")
        if quantizer is None:
            raise ConversionRefused("model_conversion_quantizer_missing")
        if not python.is_file():
            raise ConversionRefused("model_conversion_python_missing")
        return cls(root, python, converter, quantizer)

    def digest(self) -> str:
        """What ran, for provenance: the converter and the quantizer, by content."""
        digest = hashlib.sha256()
        _feed(digest, b"raiker.conversion.llama_cpp.v1")
        _feed(digest, _sha256_file(self.converter).encode("ascii"))
        _feed(digest, _sha256_file(self.quantizer).encode("ascii"))
        return f"llama.cpp:sha256:{digest.hexdigest()}"


class NativeConversionRunner:
    """llama.cpp's converter and quantizer, each run in the native sandbox.

    The model and the toolchain are mounted read-only and the run writes only
    its own scratch folder, with no network. The two results are moved into
    the output folder afterwards, so nothing the sandbox wrote lands anywhere
    else. Mounting read-only is a Linux capability of the boundary; elsewhere
    this refuses rather than copying gigabytes or widening the boundary.
    """

    #: Where the boundary keeps its own state for conversions; never the
    #: owner's model library.
    STATE = Path(tempfile.gettempdir()) / "raiker-conversion"

    def __init__(self, toolchain: LlamaCppToolchain) -> None:
        self.toolchain = toolchain

    def run(
        self,
        preview: ConversionPreview,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ConversionProvenance:
        from raiker.execution.commands.backends.base import CommandBackendError
        from raiker.execution.commands.backends.native import scratch_run

        if not sys.platform.startswith("linux"):
            raise ConversionRefused("model_conversion_platform_unsupported")
        source, output = Path(preview.source), Path(preview.output)
        intermediate, result = _output_paths(preview)
        isolation = preview.isolation
        self.STATE.mkdir(parents=True, exist_ok=True)
        try:
            with scratch_run(
                self.STATE, "convert", timeout_seconds=isolation.timeout_seconds,
                memory_bytes=isolation.max_memory_bytes,
            ) as run:
                scratch_bf16 = run.folder / "model.bf16.gguf"
                scratch_result = run.folder / f"model.{preview.quantization}.gguf"
                mounts = (source, self.toolchain.root)
                steps = (
                    [str(self.toolchain.python), str(self.toolchain.converter), str(source),
                     "--outfile", str(scratch_bf16), "--outtype", "bf16"],
                    [str(self.toolchain.quantizer), str(scratch_bf16), str(scratch_result),
                     preview.quantization],
                )
                for argv in steps:
                    self._step(
                        run.command(argv, read_only=mounts, max_processes=isolation.max_processes),
                        run.environment({"PATH": os.environ.get("PATH", "")}),
                        isolation.timeout_seconds,
                        should_cancel,
                    )
                if not scratch_result.is_file():
                    raise ConversionRefused("model_conversion_output_missing")
                shutil.move(str(scratch_bf16), intermediate)
                shutil.move(str(scratch_result), result)
        except CommandBackendError:
            raise ConversionRefused("native_sandbox_required") from None
        provenance = ConversionProvenance(
            source_revision=preview.revision,
            source_fingerprint=_source_fingerprint(source, preview.revision),
            output_fingerprint=_sha256_file(result),
            toolchain_image=self.toolchain.digest(),
            architecture=preview.architecture,
            quantization=preview.quantization,
            output_path=str(result),
        )
        _provenance_path(output, result).write_text(
            json.dumps(provenance.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return provenance

    @staticmethod
    def _step(
        argv: list[str],
        environment: dict[str, str],
        timeout: float,
        should_cancel: Callable[[], bool] | None,
    ) -> None:
        process = subprocess.Popen(  # noqa: S603 - the runner's own argv, no shell
            argv, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if should_cancel is not None and should_cancel():
                process.kill()
                process.wait()
                raise ConversionCancelled("model_conversion_cancelled")
            if time.monotonic() > deadline:
                process.kill()
                process.wait()
                raise ConversionRefused("model_conversion_timeout")
            time.sleep(0.5)
        if process.returncode != 0:
            raise ConversionRefused(f"model_conversion_step_failed:{process.returncode}")


def default_conversion_runner() -> UnavailableConversionRunner | NativeConversionRunner:
    """The owner's llama.cpp when one is named, else the refusing runner."""
    configured = os.environ.get(TOOLCHAIN_VARIABLE, "").strip()
    if not configured:
        return UnavailableConversionRunner()
    return NativeConversionRunner(LlamaCppToolchain.locate(Path(configured)))


class ModelConversionService:
    def __init__(
        self, runner: UnavailableConversionRunner | NativeConversionRunner | None = None
    ) -> None:
        self.runner = runner or default_conversion_runner()

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
