from __future__ import annotations

from pathlib import Path

REQUIRED_DOCS = [
    Path("README.md"),
    Path("docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md"),
    Path("docs/IMPLEMENTATION_STATUS.md"),
    Path("docs/EVENT_CATALOG.md"),
    Path("docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md"),
    Path("docs/UI_UX_DESIGN_SPEC.md"),
    Path("docs/API_AND_CONTRACT_SCHEMAS.md"),
    Path("docs/SECURITY_AND_POLICY.md"),
    Path("docs/RUNTIME_ORCHESTRATION_SPEC.md"),
    Path("docs/TOOLS_AND_PERMISSIONS_SPEC.md"),
    Path("docs/VERIFICATION_PLAN.md"),
]

STALE_CLAIMS = [
    "zero runtime dependencies",
    "zero_runtime_dependencies",
    "http.client",
    "LlamaCppServerProvider",
    "provider_not_wired",
    "mock fallback",
    "Ollama is intentionally not supported",
    "other providers raise",
    "default fallback when no server is reachable",
    "falls back to the deterministic",
    "binds to it automatically when",
]


def test_required_docs_do_not_contain_stale_model_runtime_claims() -> None:
    offenders: list[str] = []
    for path in REQUIRED_DOCS:
        text = path.read_text(encoding="utf-8")
        for claim in STALE_CLAIMS:
            if claim in text:
                offenders.append(f"{path}:{claim}")
    assert offenders == []
