"""GPU layer allocation, context sizing and the memory guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.models.llama_cpp.planner import (
    AUTO_CONTEXT_FLOOR,
    MemoryBudget,
    ModelShape,
    RuntimeSettings,
    inspect_model,
    model_files,
    model_shape,
    plan_launch,
    read_model_metadata,
    reduced_for_retry,
)
from tests.fixtures.llama_cpp.gguf_writer import llama_metadata, write_gguf

GIB = 1024**3


def _shape(weights_gib: float = 4.7, layers: int = 32) -> ModelShape:
    # Llama-3-8B-like: 8 KV heads x 128 wide, K and V, per layer.
    return ModelShape("llama", layers, 131072, 4096, layers * 8 * 256, int(weights_gib * GIB))


def _budget(
    backend: str = "cuda", gpu_gib: float | None = 12, ram_gib: float = 24, total_gib: float = 32,
    committed: int = 0, unified: bool = False,
) -> MemoryBudget:
    return MemoryBudget(
        backend=backend,
        gpu_free_bytes=int(gpu_gib * GIB) if gpu_gib is not None else None,
        unified=unified,
        available_memory_bytes=int(ram_gib * GIB),
        total_memory_bytes=int(total_gib * GIB),
        committed_bytes=committed,
    )


def test_model_that_fits_is_fully_offloaded_with_auto_context() -> None:
    plan = plan_launch(_shape(), _budget(), RuntimeSettings())
    assert plan.full_offload and plan.gpu_layers == 33
    assert plan.context_size == 8192  # auto target, below the 128K trained context
    assert plan.verdict == "fits" and plan.allowed
    assert plan.args[:5] == ("--jinja", "-ngl", "33", "-c", "8192")
    assert plan.system_weights_bytes == 0


def test_small_gpu_gets_a_partial_offload() -> None:
    plan = plan_launch(_shape(), _budget(gpu_gib=4), RuntimeSettings())
    assert 0 < plan.gpu_layers < 32
    assert plan.gpu_bytes <= plan.gpu_budget_bytes  # type: ignore[operator]
    assert any("layers run on the GPU" in note for note in plan.notes)
    assert plan.system_weights_bytes > 0


def test_cpu_backend_offloads_nothing() -> None:
    plan = plan_launch(_shape(), _budget(backend="cpu", gpu_gib=None), RuntimeSettings())
    assert plan.gpu_layers == 0 and plan.gpu_bytes == 0
    assert plan.system_bytes > _shape().weights_bytes


def test_unknown_gpu_size_is_not_filled_blind() -> None:
    plan = plan_launch(_shape(), _budget(backend="vulkan", gpu_gib=None), RuntimeSettings())
    assert plan.gpu_layers == 0
    assert any("could not be measured" in note for note in plan.notes)


def test_explicit_gpu_layers_are_honoured_and_clamped() -> None:
    assert plan_launch(_shape(), _budget(), RuntimeSettings(gpu_layers=10)).gpu_layers == 10
    assert plan_launch(_shape(), _budget(), RuntimeSettings(gpu_layers=999)).gpu_layers == 33


def test_explicit_layers_that_overflow_the_gpu_are_insufficient() -> None:
    plan = plan_launch(_shape(), _budget(gpu_gib=2), RuntimeSettings(gpu_layers=33))
    assert plan.verdict == "insufficient_memory" and not plan.allowed


def test_auto_context_shrinks_to_fit_but_not_below_the_floor() -> None:
    # 8 GB laptop, CPU only, 4.7 GB model: 8K context does not fit; smaller does.
    plan = plan_launch(_shape(), _budget(backend="cpu", gpu_gib=None, ram_gib=6.2, total_gib=8), RuntimeSettings())
    assert AUTO_CONTEXT_FLOOR <= plan.context_size < 8192
    assert any("Context reduced" in note for note in plan.notes)


def test_auto_context_never_exceeds_trained_context() -> None:
    shape = ModelShape("llama", 22, 2048, 2048, 22 * 4 * 128, GIB)
    assert plan_launch(shape, _budget(), RuntimeSettings()).context_size == 2048


def test_model_too_large_for_memory_is_refused_unless_overcommit() -> None:
    shape = _shape(weights_gib=40, layers=80)
    budget = _budget(backend="cpu", gpu_gib=None, ram_gib=12, total_gib=16)
    refused = plan_launch(shape, budget, RuntimeSettings())
    assert refused.verdict == "insufficient_memory" and not refused.allowed
    assert any("more memory than is free" in note for note in refused.notes)
    allowed = plan_launch(shape, budget, RuntimeSettings(allow_overcommit=True))
    assert allowed.verdict == "insufficient_memory" and allowed.allowed


def test_other_served_models_reduce_what_is_available() -> None:
    shape = _shape(weights_gib=6)
    alone = plan_launch(shape, _budget(backend="cpu", gpu_gib=None, ram_gib=12, total_gib=16), RuntimeSettings())
    crowded = plan_launch(
        shape, _budget(backend="cpu", gpu_gib=None, ram_gib=12, total_gib=16, committed=5 * GIB), RuntimeSettings()
    )
    assert alone.allowed and not crowded.allowed


def test_long_requested_context_grows_the_kv_cache_and_warns() -> None:
    plan = plan_launch(_shape(), _budget(gpu_gib=24, ram_gib=60, total_gib=64), RuntimeSettings(context_size=200_000))
    assert plan.context_size == 200_000
    assert plan.kv_cache_bytes == 200_000 * 32 * 8 * 256 * 2
    assert any("trained on" in note for note in plan.notes)


def test_quantised_kv_cache_halves_it_and_passes_flags() -> None:
    f16 = plan_launch(_shape(), _budget(), RuntimeSettings(context_size=32768))
    q8 = plan_launch(_shape(), _budget(), RuntimeSettings(context_size=32768, kv_cache_type="q8_0", flash_attention="on"))
    assert q8.kv_cache_bytes < f16.kv_cache_bytes * 0.6
    assert "--cache-type-k" in q8.args and "--flash-attn" in q8.args


def test_metal_offloads_everything_and_counts_it_as_system_memory() -> None:
    plan = plan_launch(_shape(), _budget(backend="metal", gpu_gib=10.7, ram_gib=12, total_gib=16, unified=True), RuntimeSettings())
    assert plan.full_offload
    assert plan.system_bytes >= plan.gpu_bytes


@pytest.mark.parametrize(
    ("data", "code"),
    [
        ({"gpu_layers": -1}, "runtime_settings_invalid_gpu_layers"),
        ({"gpu_layers": True}, "runtime_settings_invalid_gpu_layers"),
        ({"context_size": 100}, "runtime_settings_invalid_context_size"),
        ({"threads": 0}, "runtime_settings_invalid_threads"),
        ({"flash_attention": "maybe"}, "runtime_settings_invalid_flash_attention"),
        ({"kv_cache_type": "q2"}, "runtime_settings_invalid_kv_cache_type"),
        ({"kv_cache_type": "q8_0", "flash_attention": "off"}, "runtime_settings_kv_cache_needs_flash_attention"),
        ({"surprise": 1}, "runtime_settings_unknown_field"),
        ({"allow_overcommit": "yes"}, "runtime_settings_invalid_allow_overcommit"),
    ],
)
def test_invalid_settings_are_refused(data: dict[str, object], code: str) -> None:
    with pytest.raises(ValueError, match=code):
        RuntimeSettings.from_mapping(data)


def test_settings_round_trip() -> None:
    settings = RuntimeSettings(gpu_layers=20, context_size=4096, threads=6, flash_attention="on", kv_cache_type="q8_0")
    assert RuntimeSettings.from_mapping(settings.to_dict()) == settings
    assert RuntimeSettings.from_mapping(None) == RuntimeSettings()


def test_reduced_for_retry_steps_layers_then_context() -> None:
    plan = plan_launch(_shape(), _budget(), RuntimeSettings())
    first = reduced_for_retry(RuntimeSettings(), plan)
    assert first is not None and first.gpu_layers == (33 * 3) // 4
    cpu_plan = plan_launch(_shape(), _budget(backend="cpu", gpu_gib=None), RuntimeSettings(context_size=8192))
    second = reduced_for_retry(RuntimeSettings(context_size=8192), cpu_plan)
    assert second is not None and second.gpu_layers == 0 and second.context_size == 4096
    floor = plan_launch(_shape(), _budget(backend="cpu", gpu_gib=None), RuntimeSettings(context_size=2048))
    assert reduced_for_retry(RuntimeSettings(context_size=2048), floor) is None


def test_real_gguf_header_is_read_and_tokenizer_skipped(tmp_path: Path) -> None:
    path = write_gguf(tmp_path / "m.gguf", llama_metadata(vocab=50_000), pad_bytes=1024)
    metadata = read_model_metadata(path)
    assert metadata["llama.block_count"] == 32
    assert not any(key.startswith("tokenizer.") for key in metadata)
    shape = inspect_model(path)
    assert shape.layers == 32 and shape.trained_context == 131072
    assert shape.kv_width_total == 32 * 8 * (128 + 128)
    assert shape.weights_bytes == path.stat().st_size and not shape.estimated


def test_per_layer_kv_head_arrays_are_summed() -> None:
    metadata = llama_metadata(layers=4) | {"llama.attention.head_count_kv": [8, 8, 4, 0]}
    shape = model_shape(metadata, GIB)
    assert shape.kv_width_total == (8 + 8 + 4 + 0) * 256


def test_unreadable_file_still_plans_roughly(tmp_path: Path) -> None:
    path = tmp_path / "junk.gguf"
    path.write_bytes(b"not gguf" * 100)
    shape = inspect_model(path)
    assert shape.estimated and shape.weights_bytes == 800
    plan = plan_launch(shape, _budget(), RuntimeSettings())
    assert any("rough" in note for note in plan.notes)


def test_split_models_count_every_shard(tmp_path: Path) -> None:
    first = write_gguf(tmp_path / "big-00001-of-00002.gguf", llama_metadata(), pad_bytes=1000)
    (tmp_path / "big-00002-of-00002.gguf").write_bytes(b"\0" * 5000)
    assert len(model_files(first)) == 2
    assert inspect_model(first).weights_bytes == first.stat().st_size + 5000
