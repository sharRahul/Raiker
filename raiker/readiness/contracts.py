from __future__ import annotations

import hashlib
import json
from typing import Any

_JSON_SAFE_TYPES = (str, int, float, bool, type(None))


def validate_non_empty_strings(name: str, values: tuple[str, ...]) -> None:
    if (
        not isinstance(values, tuple)
        or not values
        or any(not isinstance(value, str) or not value for value in values)
    ):
        raise ValueError(f"{name} must be a tuple of non-empty strings")


def validate_json_safe_metadata(metadata: Any) -> None:
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if not isinstance(key, str):
                raise ValueError("metadata keys must be strings")
            validate_json_safe_metadata(value)
        return
    if isinstance(metadata, list | tuple):
        for value in metadata:
            validate_json_safe_metadata(value)
        return
    if not isinstance(metadata, _JSON_SAFE_TYPES):
        raise ValueError("metadata must contain only JSON-safe values")


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def deterministic_hash_id(prefix: str, payload: Any) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def sorted_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(values))


def deterministic_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {key: data[key] for key in sorted(data)}
