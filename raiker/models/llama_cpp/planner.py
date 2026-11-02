"""How a GGUF model should be started here, and whether it fits at all.

``llama-server`` started with defaults offloads nothing to the GPU unless told
(older builds) or tries to offload everything (newer ones), and allocates the
model's full trained context — 128K tokens for many current models, which on a
16 GB laptop is a KV cache larger than the model. Either way the owner finds out
by the server dying, or by the machine swapping until it is unusable.

The planner decides before anything starts:

* **GPU layers** — how many transformer blocks fit in the GPU's free memory
  after the compute buffer, each costing its share of the weights plus its
  share of the KV cache. A model that fits entirely is offloaded entirely,
  output layer included.
* **Context** — what the owner asked for, or, on *auto*, up to
  :data:`AUTO_CONTEXT_TARGET` tokens (never more than the model was trained
  on), halved until the plan fits, but not below :data:`AUTO_CONTEXT_FLOOR`.
* **Memory** — what stays in system memory, compared against what is
  available now after a reserve for the rest of the computer and the
  estimated footprint of every other model Raiker is already serving. A plan
  that does not fit is refused unless the owner has explicitly allowed
  overcommit for that model.

The figures are estimates, labelled as such wherever they are shown. They are
deliberately conservative: a refusal that could have run is a smaller harm than
a start that freezes the owner's computer.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

from raiker.contracts.views import View

GIB = 1024**3
MIB = 1024**2

AUTO_CONTEXT_TARGET = 8192
AUTO_CONTEXT_FLOOR = 2048
MIN_CONTEXT = 512
MAX_CONTEXT = 1_048_576
MAX_GPU_LAYERS = 1000

FlashAttention = Literal["auto", "on", "off"]
KvCacheType = Literal["f16", "q8_0", "q4_0"]
_KV_BYTES: dict[str, float] = {"f16": 2.0, "q8_0": 34 / 32, "q4_0": 18 / 32}


# ── settings the owner controls ────────────────────────────────────────


@dataclass(frozen=True)
class RuntimeSettings(View):
    """Per-model launch settings. ``None`` means *let Raiker decide*."""

    gpu_layers: int | None = None
    context_size: int | None = None
    threads: int | None = None
    flash_attention: FlashAttention = "auto"
    kv_cache_type: KvCacheType = "f16"
    #: Start even when the estimate says memory is short. Off by default.
    allow_overcommit: bool = False

    @staticmethod
    def from_mapping(data: Mapping[str, Any] | None) -> RuntimeSettings:
        """Validated settings; raises ``ValueError`` with a reason code."""
        data = dict(data or {})
        unknown = set(data) - {
            "gpu_layers", "context_size", "threads", "flash_attention",
            "kv_cache_type", "allow_overcommit",
        }
        if unknown:
            raise ValueError("runtime_settings_unknown_field")

        def bounded(name: str, low: int, high: int) -> int | None:
            value = data.get(name)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"runtime_settings_invalid_{name}")
            return value

        flash = str(data.get("flash_attention") or "auto")
        if flash not in {"auto", "on", "off"}:
            raise ValueError("runtime_settings_invalid_flash_attention")
        kv = str(data.get("kv_cache_type") or "f16")
        if kv not in _KV_BYTES:
            raise ValueError("runtime_settings_invalid_kv_cache_type")
        if kv != "f16" and flash == "off":
            # llama.cpp needs flash attention for a quantised V cache.
            raise ValueError("runtime_settings_kv_cache_needs_flash_attention")
        overcommit = data.get("allow_overcommit", False)
        if not isinstance(overcommit, bool):
            raise ValueError("runtime_settings_invalid_allow_overcommit")
        return RuntimeSettings(
            gpu_layers=bounded("gpu_layers", 0, MAX_GPU_LAYERS),
            context_size=bounded("context_size", MIN_CONTEXT, MAX_CONTEXT),
            threads=bounded("threads", 1, 512),
            flash_attention=cast(FlashAttention, flash),
            kv_cache_type=cast(KvCacheType, kv),
            allow_overcommit=overcommit,
        )


# ── what the model is ──────────────────────────────────────────────────


@dataclass(frozen=True)
class ModelShape(View):
    architecture: str
    layers: int
    trained_context: int | None
    embedding: int | None
    #: Sum over layers of (key + value) width per token; drives the KV cache.
    kv_width_total: int
    weights_bytes: int
    estimated: bool = False


class _Header:
    def __init__(self, stream: BinaryIO, limit: int) -> None:
        self.stream = stream
        self.limit = limit
        self.used = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.used + size > self.limit:
            raise ValueError("gguf_header_too_large")
        data = self.stream.read(size)
        self.used += size
        if len(data) != size:
            raise ValueError("truncated_gguf_header")
        return data

    def skip(self, size: int) -> None:
        if size < 0 or self.used + size > self.limit:
            raise ValueError("gguf_header_too_large")
        self.stream.seek(size, 1)
        self.used += size

    def u32(self) -> int:
        return int(struct.unpack("<I", self.take(4))[0])

    def u64(self) -> int:
        return int(struct.unpack("<Q", self.take(8))[0])


_SCALARS = {0: ("<B", 1), 1: ("<b", 1), 2: ("<H", 2), 3: ("<h", 2), 4: ("<I", 4), 5: ("<i", 4),
            6: ("<f", 4), 7: ("<?", 1), 10: ("<Q", 8), 11: ("<q", 8), 12: ("<d", 8)}


def _value(header: _Header, kind: int, keep: bool) -> Any:
    if kind == 8:
        length = header.u64()
        if not keep:
            header.skip(length)
            return None
        return header.take(length).decode("utf-8", errors="replace")
    if kind == 9:
        element = header.u32()
        count = header.u64()
        if element in _SCALARS and not keep:
            header.skip(_SCALARS[element][1] * count)
            return None
        if count > 4_000_000:
            raise ValueError("gguf_metadata_array_too_large")
        # Only small numeric arrays (per-layer head counts) are ever kept.
        keep_items = keep and element in _SCALARS and count <= 4096
        values = [_value(header, element, keep_items) for _ in range(count)]
        return values if keep_items else None
    scalar = _SCALARS.get(kind)
    if scalar is None:
        raise ValueError("unsupported_gguf_metadata_type")
    return struct.unpack(scalar[0], header.take(scalar[1]))[0]


def read_model_metadata(path: Path, *, limit: int = 64 * MIB) -> dict[str, Any]:
    """The GGUF header's scalar metadata, skipping the tokenizer's large arrays."""
    with path.open("rb") as stream:
        header = _Header(stream, limit)
        if header.take(4) != b"GGUF":
            raise ValueError("invalid_gguf_magic")
        version = header.u32()
        if version not in {2, 3}:
            raise ValueError("unsupported_gguf_version")
        header.u64()  # tensor count
        count = header.u64()
        if count > 100_000:
            raise ValueError("gguf_metadata_count_too_large")
        metadata: dict[str, Any] = {}
        for _ in range(count):
            key = header.take(header.u64()).decode("utf-8", errors="replace")
            kind = header.u32()
            keep = not key.startswith("tokenizer.")
            value = _value(header, kind, keep)
            if keep and value is not None:
                metadata[key] = value
    return metadata


def _number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    return None


def model_shape(metadata: Mapping[str, Any], weights_bytes: int) -> ModelShape:
    arch = str(metadata.get("general.architecture") or "unknown")

    def key(name: str) -> Any:
        return metadata.get(f"{arch}.{name}")

    layers = _number(key("block_count"))
    embedding = _number(key("embedding_length"))
    heads = key("attention.head_count")
    heads_kv = key("attention.head_count_kv")
    head_count = _number(heads) or (max(heads) if isinstance(heads, list) and heads else None)
    key_len = _number(key("attention.key_length"))
    value_len = _number(key("attention.value_length"))
    if (key_len is None or value_len is None) and embedding and head_count:
        key_len = key_len or embedding // head_count
        value_len = value_len or embedding // head_count
    estimated = False
    if layers is None:
        layers, estimated = 32, True
    per_layer_kv: list[int]
    if isinstance(heads_kv, list) and heads_kv:
        per_layer_kv = [int(item) for item in heads_kv[:layers] if isinstance(item, (int, float))]
    else:
        count = _number(heads_kv) or head_count
        per_layer_kv = [count] * layers if count else []
    if per_layer_kv and key_len and value_len:
        kv_width = sum(n * (key_len + value_len) for n in per_layer_kv)
    else:
        # Unknown attention shape: assume a grouped-query model's typical
        # 1024-wide K and V per layer, which overstates most small models.
        kv_width, estimated = layers * 2048, True
    return ModelShape(
        architecture=arch,
        layers=layers,
        trained_context=_number(key("context_length")),
        embedding=embedding,
        kv_width_total=kv_width,
        weights_bytes=weights_bytes,
        estimated=estimated,
    )


def model_files(primary: Path) -> list[Path]:
    """Every shard of a split GGUF (``…-00001-of-00003.gguf``), or the file alone."""
    import re

    match = re.match(r"^(?P<stem>.+)-(?P<index>\d{5})-of-(?P<count>\d{5})\.gguf$", primary.name, re.I)
    if not match:
        return [primary]
    count = int(match.group("count"))
    stem = match.group("stem")
    return [primary.with_name(f"{stem}-{index:05d}-of-{count:05d}.gguf") for index in range(1, count + 1)]


def inspect_model(primary: Path) -> ModelShape:
    weights = sum(path.stat().st_size for path in model_files(primary) if path.is_file())
    try:
        metadata = read_model_metadata(primary)
    except (OSError, ValueError):
        metadata = {}
    return model_shape(metadata, weights)


# ── where it runs ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class MemoryBudget(View):
    backend: str
    #: What the GPU has free right now (``None`` for CPU or when unknown).
    gpu_free_bytes: int | None
    #: Apple silicon: the GPU's memory *is* system memory.
    unified: bool
    available_memory_bytes: int | None
    total_memory_bytes: int | None
    #: Estimated memory already held by other models Raiker is serving.
    committed_bytes: int = 0
    cpu_cores: int = 1


@dataclass(frozen=True)
class LaunchPlan(View):
    backend: str
    gpu_layers: int
    total_layers: int
    full_offload: bool
    context_size: int
    trained_context: int | None
    threads: int | None
    flash_attention: str
    kv_cache_type: str
    weights_bytes: int
    kv_cache_bytes: int
    gpu_bytes: int
    system_bytes: int
    #: The weights left in system memory. Memory-mapped, so the operating system
    #: counts them as reclaimable cache rather than used memory; other models'
    #: plans add this to their committed figure so the next model is not
    #: planned into memory a running one is really using.
    system_weights_bytes: int
    gpu_budget_bytes: int | None
    system_budget_bytes: int | None
    #: ``fits``, ``tight`` (within 15% of a limit) or ``insufficient_memory``.
    verdict: str
    allowed: bool
    notes: tuple[str, ...]
    args: tuple[str, ...]
    estimated: bool = True
    settings: RuntimeSettings = field(default_factory=RuntimeSettings)


def _gpu_budget(budget: MemoryBudget) -> int | None:
    if budget.backend == "cpu" or budget.gpu_free_bytes is None:
        return None
    reserve = max(512 * MIB, int(budget.gpu_free_bytes * 0.05))
    return max(0, budget.gpu_free_bytes - reserve)


def _system_budget(budget: MemoryBudget) -> int | None:
    if budget.available_memory_bytes is None:
        return None
    total = budget.total_memory_bytes or budget.available_memory_bytes
    reserve = max(GIB, int(total * 0.10))
    return max(0, budget.available_memory_bytes - reserve - budget.committed_bytes)


def _overhead(shape: ModelShape, context: int) -> int:
    """Compute buffers: a floor plus a term that grows with context and width."""
    width = shape.embedding or 4096
    return min(4 * GIB, 384 * MIB + context * width * 8)


def _evaluate(
    shape: ModelShape, budget: MemoryBudget, settings: RuntimeSettings, context: int
) -> tuple[int, int, int, int, int | None, int | None, int]:
    """``(gpu_layers, kv, gpu, system, gpu_budget, system_budget, system_weights)``."""
    kv_bytes = int(context * shape.kv_width_total * _KV_BYTES[settings.kv_cache_type])
    layers = shape.layers
    layer_weight = shape.weights_bytes / (layers + 1)
    layer_kv = kv_bytes / layers
    overhead = _overhead(shape, context)
    gpu_budget = _gpu_budget(budget)
    system_budget = _system_budget(budget)
    if budget.backend == "cpu":
        offload = 0
    elif settings.gpu_layers is not None:
        offload = min(settings.gpu_layers, layers + 1)
    elif budget.unified:
        offload = layers + 1  # no copy to make: Metal maps the weights in place
    elif gpu_budget is None:
        offload = 0  # a GPU of unknown size is not filled blind
    else:
        room = gpu_budget - overhead
        offload = max(0, min(layers, int(room // (layer_weight + layer_kv)))) if room > 0 else 0
        if offload == layers and room - layers * (layer_weight + layer_kv) >= layer_weight:
            offload = layers + 1
    on_gpu_blocks = min(offload, layers)
    gpu_bytes = 0
    if offload > 0:
        gpu_bytes = int(on_gpu_blocks * (layer_weight + layer_kv) + overhead)
        if offload > layers:
            gpu_bytes += int(layer_weight)
    cpu_weights = shape.weights_bytes * (layers + 1 - min(offload, layers + 1)) // (layers + 1)
    system_bytes = int(cpu_weights + (layers - on_gpu_blocks) * layer_kv + 256 * MIB)
    if offload == 0:
        system_bytes += overhead
    if budget.unified:
        # One pool: everything the GPU holds is also system memory.
        system_bytes += gpu_bytes
    return offload, kv_bytes, gpu_bytes, system_bytes, gpu_budget, system_budget, cpu_weights


def _verdict(used: int, limit: int | None) -> str:
    if limit is None:
        return "fits"
    if used > limit:
        return "insufficient_memory"
    return "tight" if used > limit * 0.85 else "fits"


def plan_launch(shape: ModelShape, budget: MemoryBudget, settings: RuntimeSettings) -> LaunchPlan:
    """The arguments to start this model with, and whether it fits."""
    trained = shape.trained_context
    notes: list[str] = []
    if settings.context_size is not None:
        context = settings.context_size
        if trained and context > trained:
            notes.append(f"Context is longer than the {trained:,} tokens this model was trained on.")
        candidates = [context]
    else:
        target = min(AUTO_CONTEXT_TARGET, trained) if trained else AUTO_CONTEXT_TARGET
        candidates = []
        value = max(target, MIN_CONTEXT)
        while True:
            candidates.append(value)
            if value <= AUTO_CONTEXT_FLOOR or value // 2 < MIN_CONTEXT:
                break
            value = max(AUTO_CONTEXT_FLOOR, value // 2)
    chosen: tuple[int, tuple[int, int, int, int, int | None, int | None, int], str] | None = None
    for context in candidates:
        evaluated = _evaluate(shape, budget, settings, context)
        _offload, _kv, gpu, system, gpu_budget, system_budget, _weights = evaluated
        verdict = _verdict(system, system_budget)
        if verdict != "insufficient_memory" and _verdict(gpu, gpu_budget) == "insufficient_memory":
            verdict = "insufficient_memory"
        chosen = (context, evaluated, verdict)
        if verdict != "insufficient_memory":
            break
    assert chosen is not None
    context, evaluated, verdict = chosen
    offload, kv_bytes, gpu_bytes, system_bytes, gpu_budget, system_budget, system_weights = evaluated
    if settings.context_size is None and context < candidates[0]:
        notes.append(f"Context reduced to {context:,} tokens to fit in memory.")
    if budget.backend != "cpu" and offload == 0:
        notes.append(
            "The GPU's free memory could not be measured; the model runs on the processor."
            if _gpu_budget(budget) is None and not budget.unified and settings.gpu_layers is None
            else "No layers fit on the GPU; the model runs on the processor."
        )
    elif 0 < offload <= shape.layers and budget.backend != "cpu":
        notes.append(
            f"{offload} of {shape.layers} layers run on the GPU; the rest use the processor and are slower."
        )
    if verdict == "insufficient_memory":
        notes.append(
            "This model needs more memory than is free. Close other programs, choose a smaller "
            "context or quantisation, or allow overcommit for this model."
        )
    if shape.estimated:
        notes.append("This model's file does not describe its shape fully; memory figures are rough.")
    args: list[str] = ["--jinja", "-ngl", str(offload), "-c", str(context)]
    if settings.threads is not None:
        args += ["-t", str(settings.threads)]
    if settings.flash_attention != "auto":
        args += ["--flash-attn", settings.flash_attention]
    if settings.kv_cache_type != "f16":
        args += ["--cache-type-k", settings.kv_cache_type, "--cache-type-v", settings.kv_cache_type]
    return LaunchPlan(
        backend=budget.backend,
        gpu_layers=offload,
        total_layers=shape.layers,
        full_offload=offload > shape.layers,
        context_size=context,
        trained_context=trained,
        threads=settings.threads,
        flash_attention=settings.flash_attention,
        kv_cache_type=settings.kv_cache_type,
        weights_bytes=shape.weights_bytes,
        kv_cache_bytes=kv_bytes,
        gpu_bytes=gpu_bytes,
        system_bytes=system_bytes,
        system_weights_bytes=system_weights,
        gpu_budget_bytes=gpu_budget,
        system_budget_bytes=system_budget,
        verdict=verdict,
        allowed=verdict != "insufficient_memory" or settings.allow_overcommit,
        notes=tuple(notes),
        args=tuple(args),
        estimated=True,
        settings=settings,
    )


def reduced_for_retry(settings: RuntimeSettings, plan: LaunchPlan) -> RuntimeSettings | None:
    """Settings one step smaller after an out-of-memory start, or ``None``.

    GPU layers come down first (by a quarter, then to zero), because a slower
    model beats one that will not start; context is halved only once nothing
    is left on the GPU.
    """
    if plan.gpu_layers > 0:
        fewer = (plan.gpu_layers * 3) // 4 if plan.gpu_layers > 4 else 0
        return replace(settings, gpu_layers=fewer)
    if plan.context_size > AUTO_CONTEXT_FLOOR:
        return replace(settings, gpu_layers=0, context_size=max(AUTO_CONTEXT_FLOOR, plan.context_size // 2))
    return None
