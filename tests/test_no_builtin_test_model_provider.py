from __future__ import annotations

from pathlib import Path

_TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".ts", ".svelte", ".yaml", ".yml"}
_FORBIDDEN = (
    "".join(("mock", "-test")),
    "".join(("mock", "-deterministic")),
    "".join(("deterministic", "-test")),
    "".join(("deterministic", "-test-model")),
    "".join(("Deterministic", "TestProvider")),
    "".join(("RAIKER", "_TEST_MODE")),
    "".join(("allow", "_test_provider")),
)
_SKIP_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tmp", "node_modules"}


def test_builtin_test_model_provider_is_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES:
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in _FORBIDDEN:
            if marker in text:
                hits.append(f"{path.relative_to(root)}: {marker}")
    assert not hits, "Built-in test model provider references remain:\n" + "\n".join(hits)
