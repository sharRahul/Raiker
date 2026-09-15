"""Converting a model the owner already has into one this machine can serve.

**Cancel means cancel, while it is running (GCR-24).** The two steps are Docker
containers and the isolation budget allows six hours, and the worker used to
check the cancellation flag immediately before starting the first one and
immediately after the last finished. In between there was nothing to check it:
``subprocess.run`` blocks until the child exits. So pressing **Cancel** on a
conversion that had just started left the operation at ``cancel_requested``, with
the CPU still committed, potentially for the rest of the day.

Three things make it answer now:

* **A handle instead of a wait.** Each step runs under ``Popen`` and is polled,
  so the flag is read on a cadence rather than at two instants.
* **A name for the container.** Killing the ``docker run`` client does not stop
  the container it started — the work goes on without anything watching it. Each
  step is given a deterministic name, derived from the preview, and cancelling
  stops *that container* by name. Deterministic rather than random on purpose:
  the preview is what is persisted with the operation, so the names can be
  recomputed by anything that has to clean up after a host restart, without
  storing a second identity that could drift from the first.
* **A cancellation is not a failure.** It raises
  :class:`ConversionCancelled` rather than the generic refusal, so the owner is
  told their conversion stopped because they stopped it, and not that it broke.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
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


class ConversionCancelled(ConversionRefused):
    """The owner stopped this conversion while it was running (GCR-24).

    A subclass, so a caller that only knows about refusals still catches it, and
    a caller that cares can tell the two apart. They are different sentences to
    an owner: one says the work broke, the other says they stopped it.
    """


#: How often a running step is asked whether it should stop. Short enough that
#: Cancel feels immediate, long enough that a six-hour conversion spends no
#: measurable time being asked. The container stop below is what actually takes
#: a moment.
CANCEL_POLL_SECONDS = 1.0

#: How long a stopped container is given to exit before it is killed outright.
#: Docker's own default is ten seconds and the toolchain has nothing to flush.
CONTAINER_STOP_SECONDS = 10


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
    def run(
        self,
        preview: ConversionPreview,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ConversionProvenance:
        """Convert, answering ``should_cancel`` throughout rather than at the ends.

        ``should_cancel`` is optional so every existing caller and test keeps
        working unchanged; without one the steps run to completion exactly as
        they did, and with one a conversion stops when the owner says so.
        """
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
        names = conversion_container_names(preview)
        for argv, name in zip((convert, quantize), names, strict=True):
            returncode = self._step(argv, name, docker, clean_env, preview, should_cancel)
            if returncode != 0:
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
        _provenance_path(output, result).write_text(
            json.dumps(provenance.to_dict(), sort_keys=True, indent=2), encoding="utf-8"
        )
        intermediate.unlink(missing_ok=True)
        return provenance

    def _step(
        self,
        argv: list[str],
        container: str,
        docker: str,
        env: dict[str, str],
        preview: ConversionPreview,
        should_cancel: Callable[[], bool] | None,
    ) -> int:
        """Run one container to completion, cancellation or the isolation deadline.

        Output goes to ``DEVNULL`` rather than to pipes. It was captured and
        never read, and a step that is *waited on* rather than drained can fill
        a pipe buffer and block — which for a converter that prints a line per
        tensor is not hypothetical. Nothing that was used is lost.
        """
        process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell, cleaned env
            argv,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        deadline = time.monotonic() + preview.isolation.timeout_seconds
        while True:
            try:
                return process.wait(timeout=CANCEL_POLL_SECONDS)
            except subprocess.TimeoutExpired:
                pass
            if should_cancel is not None and should_cancel():
                self._stop(process, container, docker, env)
                raise ConversionCancelled("conversion_cancelled_by_owner")
            if time.monotonic() >= deadline:
                self._stop(process, container, docker, env)
                raise ConversionRefused("isolated_conversion_timed_out")

    def _stop(
        self, process: subprocess.Popen[bytes], container: str, docker: str, env: dict[str, str]
    ) -> None:
        """Stop the container, then the client that is waiting on it.

        In that order, and both: terminating the ``docker run`` client alone
        leaves the container running with nothing watching it, which is the
        worst of the three outcomes — the owner is told it stopped and the CPU
        is still committed.
        """
        # Docker itself may be unreachable. The client below is still killed in
        # that case, so the worker settles rather than waiting for ever on
        # something it has no way to stop.
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(  # noqa: S603 - fixed argv, no shell, cleaned env
                [docker, "stop", "--time", str(CONTAINER_STOP_SECONDS), container],
                shell=False,
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=CONTAINER_STOP_SECONDS + 20,
                env=env,
            )
        process.terminate()
        try:
            process.wait(timeout=CONTAINER_STOP_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=CONTAINER_STOP_SECONDS)


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

    def convert(
        self,
        preview: ConversionPreview,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ConversionProvenance:
        return self.runner.run(preview, should_cancel)


def conversion_container_names(preview: ConversionPreview) -> tuple[str, str]:
    """The two containers this conversion runs, named ``(convert, quantize)``.

    Derived from the preview rather than generated, which is what makes the
    identity *recoverable* (GCR-24): the preview is persisted with the
    operation, so anything cleaning up after a host restart can recompute these
    names and remove the containers, without a second stored identity that could
    disagree with the first.

    The digest covers everything that decides what the container does, so two
    conversions the owner could reasonably run at once — the same source at two
    quantizations, or the same model into two libraries — never collide on a
    name and stop each other.
    """
    digest = hashlib.sha256(
        "\x00".join(
            (preview.source, preview.output, preview.revision, preview.quantization)
        ).encode("utf-8")
    ).hexdigest()[:16]
    return (f"raiker-convert-{digest}", f"raiker-quantize-{digest}")


def docker_command_plan(preview: ConversionPreview, docker: str) -> tuple[list[str], list[str]]:
    source = Path(preview.source)
    output = Path(preview.output)
    intermediate, result = _output_paths(preview)
    convert_name, quantize_name = conversion_container_names(preview)
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
    # GCR-24 — a named container is one Cancel can reach. Without it the only
    # handle is the `docker run` client, and killing that leaves the work going.
    convert = base + [
        "--name",
        convert_name,
        "--entrypoint",
        "python",
        preview.toolchain_image,
        *preview.convert_argv[1:-3],
        "/models/output/" + intermediate.name,
        *preview.convert_argv[-2:],
    ]
    quantize = base + [
        "--name",
        quantize_name,
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

    It used to hash the declared revision, each relative filename and each
    file's *byte size*, and never the bytes. A path and a length are not an
    identity: edit a weights file in place, keep its length, and the fingerprint
    is unchanged — so the provenance record recorded a different model under the
    same value, which is the one thing a fingerprint exists not to do.

    Now every included file's content is hashed. Three details that matter:

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
