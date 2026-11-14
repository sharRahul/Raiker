# SPDX-License-Identifier: Apache-2.0
"""BUG-351 — the terminal's /model commands read the owner's saved connections."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from raiker.cli import commands
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.exceptions import ProviderPolicyError
from raiker.models.router import ModelRouter


def test_the_terminal_router_is_bound_to_the_local_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    seen: list[str] = []

    def fake_runtime(store: Any, principal_id: str, writer: Any) -> tuple[str, tuple[str, str]]:
        seen.append(principal_id)
        return "owner-router", ("ollama", "llama3")

    monkeypatch.setattr("raiker.models.owner_runtime.owner_model_runtime", fake_runtime)
    assert commands._owner_router(tmp_path) == "owner-router"
    assert seen and seen[0].startswith("principal_")


def test_without_an_owner_the_terminal_keeps_the_ownerless_router(tmp_path: Path) -> None:
    router = commands._owner_router(tmp_path)
    assert isinstance(router, ModelRouter)


def test_an_unconnected_hosted_provider_says_where_to_connect_it(tmp_path: Path) -> None:
    class Refusing:
        async def alist_models_for_profile(self, profile: Any) -> list[Any]:
            raise ProviderPolicyError("model_connection_required")

    out = asyncio.run(commands.render_models_async(workspace_root=tmp_path, router=Refusing()))  # type: ignore[arg-type]
    assert "reason: model_connection_required" in out
    assert commands.CONNECT_IN_MODELS in out
    assert "RAIKER_MODEL_EGRESS_ALLOWLIST" not in out
