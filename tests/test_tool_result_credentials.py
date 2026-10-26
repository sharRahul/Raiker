"""OWASP LLM02 / ASI03 — a credential in a tool result never reaches the model."""

from __future__ import annotations

import json

from raiker.runtime.orchestrator import _tool_content
from raiker.security.secret_shapes import strip_credentials

# Fixture shapes built at runtime, so the repository's own secret scan never sees one.
GITHUB = "ghp_" + "A" * 36
ANTHROPIC = "sk-ant-" + "b" * 30
_MARK = "PRIVATE " + "KEY-----"
PRIVATE = "-----BEGIN RSA " + _MARK + "\nMIIEow" + "x" * 40 + "\n-----END RSA " + _MARK


def test_each_shape_is_removed_and_counted() -> None:
    payload = {
        "status": "success",
        "text": f"GITHUB_TOKEN={GITHUB}\nANTHROPIC_API_KEY={ANTHROPIC}\n",
        "lines": [f"key: {PRIVATE}", "nothing here"],
        "size": 42,
    }
    cleaned, removed = strip_credentials(payload)
    flat = json.dumps(cleaned)
    assert GITHUB not in flat and ANTHROPIC not in flat and "MIIEow" not in flat
    assert "[credential removed: github_token]" in flat
    assert "[credential removed: private_key_block]" in flat
    assert removed == {"github_token": 1, "anthropic_key": 1, "private_key_block": 1}
    assert cleaned["size"] == 42 and cleaned["lines"][1] == "nothing here"


def test_the_message_the_model_reads_carries_no_key() -> None:
    content = _tool_content({"status": "success", "text": f"token {GITHUB} here"})
    assert GITHUB not in content and "credential removed: github_token" in content


def test_ordinary_text_is_left_alone() -> None:
    text = "sha256:" + "f" * 64 + " and a uuid 123e4567-e89b-12d3-a456-426614174000"
    cleaned, removed = strip_credentials(text)
    assert cleaned == text and removed == {}
