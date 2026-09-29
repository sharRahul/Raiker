"""OPT-14 — a provider's owner-facing name is declared once, beside its profiles.

Readiness carried its own ``_provider_label`` table, and the web app carries
``PROVIDER_NAMES``. The backend table now lives in ``model-profiles.json``;
these tests make every shipped provider declare a name there and keep the web
table saying the same thing, apart from the one place it deliberately differs.
"""

from __future__ import annotations

import re
from pathlib import Path

from raiker.models.registry import ModelProfileRegistry

WEB_FORMAT = Path(__file__).resolve().parents[1] / "web" / "src" / "lib" / "format.ts"

# Pickers name what the owner chose — a GGUF file — rather than the llama.cpp
# server Raiker runs over it (see the comment on PROVIDER_NAMES).
_WEB_ONLY_DIFFERENCES = {"llama.cpp": "GGUF"}


def _web_provider_names() -> dict[str, str]:
    source = WEB_FORMAT.read_text(encoding="utf-8")
    block = source.split("const PROVIDER_NAMES: Record<string, string> = {", 1)[1].split("};", 1)[0]
    return {
        key.strip('"'): value
        for key, value in re.findall(r'^\s*("?[\w.\-]+"?):\s*"([^"]+)"', block, re.M)
    }


def test_every_shipped_provider_declares_its_display_name() -> None:
    registry = ModelProfileRegistry.load()
    providers = {profile.provider for profile in registry.list_profiles()}
    assert sorted(providers - set(registry.provider_display_names)) == []


def test_readiness_names_a_provider_as_the_registry_does() -> None:
    registry = ModelProfileRegistry.load()
    assert registry.provider_display_name("chatgpt-codex") == "ChatGPT subscription"
    assert registry.provider_display_name("lm-studio") == "LM Studio"
    # An owner-added provider nobody declared still reads as words.
    assert registry.provider_display_name("my-home-lab") == "My Home Lab"


def test_the_web_table_agrees_with_the_registry() -> None:
    registry = ModelProfileRegistry.load()
    web = _web_provider_names()
    assert len(web) >= len(registry.provider_display_names)
    disagreements = {
        provider: (name, web.get(provider))
        for provider, name in registry.provider_display_names.items()
        if web.get(provider) != _WEB_ONLY_DIFFERENCES.get(provider, name)
    }
    assert disagreements == {}
