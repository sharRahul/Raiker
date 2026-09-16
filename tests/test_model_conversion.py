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


class TestTheSourceFingerprintFingerprintsTheSource:
    """GCR-26 — the provenance record is a content-integrity claim, or it is not one.

    It used to hash the declared revision, each relative filename and each
    file's byte *size*. A path and a length are not an identity: edit a weights
    file in place without changing its length and the value was unchanged, so
    two different models were recorded under one fingerprint.
    """

    def _fingerprint(self, source: Path) -> str:
        from raiker.models.conversion import _source_fingerprint

        return _source_fingerprint(source, "a" * 40)

    def test_editing_a_file_without_changing_its_length_changes_the_fingerprint(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "snapshot"
        source.mkdir()
        weights = source / "model.safetensors"
        weights.write_bytes(b"original-weights")

        before = self._fingerprint(source)
        weights.write_bytes(b"tampered-weights")  # same length, different bytes

        assert weights.stat().st_size == len(b"original-weights")
        assert self._fingerprint(source) != before

    def test_the_same_tree_fingerprints_the_same_way_twice(self, tmp_path: Path) -> None:
        source = tmp_path / "snapshot"
        (source / "nested").mkdir(parents=True)
        (source / "config.json").write_text("{}", encoding="utf-8")
        (source / "nested" / "model.safetensors").write_bytes(b"weights")

        assert self._fingerprint(source) == self._fingerprint(source)

    def test_moving_a_file_changes_the_fingerprint(self, tmp_path: Path) -> None:
        source = tmp_path / "snapshot"
        (source / "nested").mkdir(parents=True)
        (source / "nested" / "model.safetensors").write_bytes(b"weights")

        before = self._fingerprint(source)
        (source / "nested" / "model.safetensors").rename(source / "model.safetensors")

        assert self._fingerprint(source) != before

    def test_a_filename_cannot_be_rearranged_into_another_tree(self, tmp_path: Path) -> None:
        """Each field is length-prefixed, so the concatenation is unambiguous.

        Without that, "ab" + "c" and "a" + "bc" are the same byte stream, and
        two different trees could be made to agree.
        """
        first = tmp_path / "first"
        first.mkdir()
        (first / "ab").write_bytes(b"x")
        (first / "c").write_bytes(b"y")

        second = tmp_path / "second"
        second.mkdir()
        (second / "a").write_bytes(b"x")
        (second / "bc").write_bytes(b"y")

        assert self._fingerprint(first) != self._fingerprint(second)

    def test_the_revision_still_participates(self, tmp_path: Path) -> None:
        from raiker.models.conversion import _source_fingerprint

        source = tmp_path / "snapshot"
        source.mkdir()
        (source / "model.safetensors").write_bytes(b"weights")

        assert _source_fingerprint(source, "a" * 40) != _source_fingerprint(source, "b" * 40)
