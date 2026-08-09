from __future__ import annotations

from raiker.models.runtime_installers import RuntimeInstallerRegistry


def test_lm_studio_desktop_is_never_downloaded_or_redistributed() -> None:
    plan = RuntimeInstallerRegistry().preview("lm-studio-desktop", platform="windows")
    assert plan.redistribution is False
    assert plan.action == "open_vendor_download"
    assert plan.source_url.startswith("https://lmstudio.ai/")
    assert plan.argv == ()


def test_official_runtime_plans_never_put_tokens_or_piped_scripts_on_argv() -> None:
    registry = RuntimeInstallerRegistry()
    for runtime in ("ollama", "llmster", "llama.cpp"):
        plan = registry.preview(runtime, platform="windows")
        joined = " ".join(plan.argv).lower()
        assert plan.source_url.startswith("https://")
        assert "token" not in joined
        assert "iex" not in joined
        assert "|" not in joined


def test_unknown_runtime_is_rejected() -> None:
    try:
        RuntimeInstallerRegistry().preview("mystery", platform="windows")
    except ValueError as exc:
        assert str(exc) == "unsupported_runtime"
    else:
        raise AssertionError("unknown runtime was accepted")
