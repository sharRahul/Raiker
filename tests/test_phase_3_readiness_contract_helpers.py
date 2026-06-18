from __future__ import annotations

import pytest

from raiker.approvals.readiness import create_approval_preview_persistence_readiness_contract
from raiker.channels.readiness import create_external_channels_notifications_readiness_contract
from raiker.graph.readiness import create_readiness_contract
from raiker.memory.readiness import create_semantic_memory_readiness_contract
from raiker.plugins.readiness import create_plugin_server_startup_readiness_contract
from raiker.readiness.contracts import (
    canonical_json,
    deterministic_hash_id,
    validate_json_safe_metadata,
    validate_non_empty_strings,
)
from raiker.storage.cleanup_readiness import create_storage_cleanup_execution_readiness_contract


def test_json_safe_metadata_accepts_primitives_lists_tuples_and_string_key_dicts() -> None:
    validate_json_safe_metadata(
        {
            "string": "value",
            "integer": 1,
            "float": 1.25,
            "boolean": False,
            "null": None,
            "list": ["nested", 2],
            "tuple": ("nested", {"key": "value"}),
        }
    )


def test_json_safe_metadata_rejects_non_string_dict_keys() -> None:
    with pytest.raises(ValueError, match="metadata keys must be strings"):
        validate_json_safe_metadata({1: "value"})


def test_json_safe_metadata_rejects_non_json_safe_objects() -> None:
    with pytest.raises(ValueError, match="metadata must contain only JSON-safe values"):
        validate_json_safe_metadata({"object": object()})


def test_non_empty_string_tuple_validation_rejects_empty_tuples() -> None:
    with pytest.raises(ValueError, match="gates must be a tuple of non-empty strings"):
        validate_non_empty_strings("gates", ())


def test_non_empty_string_tuple_validation_rejects_blank_strings() -> None:
    with pytest.raises(ValueError, match="gates must be a tuple of non-empty strings"):
        validate_non_empty_strings("gates", ("ready", ""))


def test_deterministic_hash_id_is_stable() -> None:
    payload = {"b": [2, 1], "a": {"z": False}}
    assert deterministic_hash_id("test", payload) == deterministic_hash_id("test", payload)
    assert deterministic_hash_id("test", payload) == "test_751a68e8426c5d3e"


def test_canonical_json_is_stable_across_ordering_differences() -> None:
    left = {"b": 2, "a": {"d": 4, "c": 3}}
    right = {"a": {"c": 3, "d": 4}, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_json(left) == '{"a":{"c":3,"d":4},"b":2}'


def test_shared_helpers_preserve_representative_slice_j_through_o_readiness_ids() -> None:
    assert create_readiness_contract().readiness_id == "gcr_a8c7e2005bca5bf5"
    assert create_semantic_memory_readiness_contract().readiness_id == "smr_550d2743806323d6"
    assert (
        create_approval_preview_persistence_readiness_contract().readiness_id
        == "appr_6c420bfba2e4b2b6"
    )
    assert (
        create_storage_cleanup_execution_readiness_contract().readiness_id
        == "scer_a8cf95528be599fc"
    )
    assert create_plugin_server_startup_readiness_contract().readiness_id == "pssr_8dffdf735ee2269a"
    assert (
        create_external_channels_notifications_readiness_contract().readiness_id
        == "ecnr_bb6ad4656a8bed49"
    )
