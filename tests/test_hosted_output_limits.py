# SPDX-License-Identifier: Apache-2.0
"""FIXED-1435 — no shipped hosted profile falls back to a 1,024-token answer.

FIXED-1344 measured five providers with the owner's keys. The rest kept the
router's 1,024 fallback, which cuts a long answer off mid-sentence. Each now
declares a limit every model its provider currently serves accepts; the
per-model ceilings are higher, and a live key can raise them later.
"""

from __future__ import annotations

import json
from pathlib import Path

PROFILES = Path(__file__).resolve().parents[1] / "raiker" / "config" / "model-profiles.json"

#: Profiles whose server and model are the owner's choice, so no limit fits all.
OWNER_DEFINED = {"chatgpt-codex-subscription"}


def _profiles() -> list[dict[str, object]]:
    loaded = json.loads(PROFILES.read_text(encoding="utf-8"))
    return list(loaded["profiles"] if isinstance(loaded, dict) else loaded)


def test_every_hosted_profile_declares_an_output_limit() -> None:
    missing = [
        str(profile["profile_id"])
        for profile in _profiles()
        if profile.get("requires_network")
        and profile.get("provider") != "openai-compatible"
        and str(profile["profile_id"]) not in OWNER_DEFINED
        and not profile.get("max_tokens")
    ]
    assert missing == []


def test_declared_limits_are_above_the_fallback_and_within_reason() -> None:
    for profile in _profiles():
        limit = profile.get("max_tokens")
        if limit is None:
            continue
        assert isinstance(limit, int)
        assert 4096 <= limit <= 65536, profile["profile_id"]
