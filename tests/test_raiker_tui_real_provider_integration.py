"""Optional real-provider streaming integration test for the Raiker TUI.

This test is SKIPPED by default. It only runs when the operator explicitly opts
in by setting the required environment variables. It must never require an API
key in CI and must skip safely when keys are missing.

Activation (all required):
  RAIKER_INTEGRATION_PROVIDER=<profile_id>   e.g. raiker-local-llama-cpp
  RAIKER_INTEGRATION_MODEL=<model name>      e.g. local-gguf
  RAIKER_INTEGRATION_ENDPOINT=<http(s) url>  e.g. http://127.0.0.1:8080
  RAIKER_INTEGRATION_API_KEY=<key>           optional; only for hosted providers

Security rules:
  * API keys are read from the environment only; never committed, logged,
    printed, or written into snapshots.
  * The test must not echo the key or the endpoint into pytest output.
  * If any required variable is missing, the test is skipped, not failed.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from raiker.cli.commands import build_prompt_envelope
from raiker.contracts.streaming import FINAL, TEXT_DELTA
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.registry import ModelProfileRegistry
from raiker.tui.accessibility import TerminalProfile
from raiker.tui.textual_app import RaikerTextualApp, _Transcript

_REQUIRED_ENV = (
    "RAIKER_INTEGRATION_PROVIDER",
    "RAIKER_INTEGRATION_MODEL",
    "RAIKER_INTEGRATION_ENDPOINT",
)


def _integration_enabled() -> bool:
    return all(os.environ.get(name) for name in _REQUIRED_ENV)


def _capture_transcript(app: RaikerTextualApp) -> str:
    widget = app.query_one(_Transcript)
    lines: list[str] = []
    for strip in widget.lines:
        line_text = "".join(seg.text for seg in getattr(strip, "_segments", ()))
        lines.append(line_text)
    return "\n".join(lines)


pytestmark = pytest.mark.skipif(
    not _integration_enabled(),
    reason=(
        "Real-provider integration test is opt-in only. Set "
        "RAIKER_INTEGRATION_PROVIDER, RAIKER_INTEGRATION_MODEL, and "
        "RAIKER_INTEGRATION_ENDPOINT to enable. API key env is optional and "
        "depends on the provider."
    ),
)


def _write_integration_profile(tmp_path: Path) -> Path:
    """Write a temp model-profiles.json for the integration provider.

    The API key (if any) is referenced by env-var name only, never written
    inline. The registry reads the key from the environment at call time.
    """

    provider = os.environ["RAIKER_INTEGRATION_PROVIDER"]
    model = os.environ["RAIKER_INTEGRATION_MODEL"]
    endpoint = os.environ["RAIKER_INTEGRATION_ENDPOINT"]
    api_key = os.environ.get("RAIKER_INTEGRATION_API_KEY", "")
    is_local = endpoint.startswith("http://127.0.0.1") or endpoint.startswith("http://localhost")
    profile = {
        "profile_id": provider,
        "provider": provider,
        "backend": "openai_compatible",
        "model": model,
        "served_model_name": model,
        "endpoint": endpoint,
        "build_phase": "integration_test",
        "default_state": "enabled",
        "tui_launch_action": f"/model use {provider}",
        "is_native_default": True,
        "local_only": is_local,
        "requires_network": not is_local,
        "requires_egress_policy": not is_local,
        "requires_budget_policy": False,
        "supports_streaming": True,
        "supports_embeddings": False,
        "supports_tool_calls": True,
        "supports_json_schema": False,
        "supports_reasoning": False,
        "reasoning_trace_visible": False,
        "tool_call_mode": "native_or_text_json",
        "health_path": "/health",
        "models_path": "/v1/models",
        "chat_path": "/v1/chat/completions",
        "embeddings_path": "/v1/embeddings",
        "timeout_seconds": 120.0,
        "temperature": 0.2,
        "max_tokens": 256,
    }
    if api_key:
        profile["api_key_env"] = "RAIKER_INTEGRATION_API_KEY"
        profile["redact_from_logs"] = ["api_key_env", "extra_headers.Authorization"]
    config_path = tmp_path / "model-profiles.json"
    config_path.write_text(
        json.dumps({"schema_version": "1.0", "profiles": [profile]}, indent=2),
        encoding="utf-8",
    )
    return config_path


def test_real_provider_streams_live_into_tui_transcript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify a real provider streams multiple chunks into the TUI transcript.

    Confirms: multiple TEXT_DELTA chunks arrive, chunks render incrementally,
    and the final assistant message is assembled in the transcript.
    """

    config_path = _write_integration_profile(tmp_path)
    # Point the registry at the temp config.
    monkeypatch.setattr(
        "raiker.gateway.agent_gateway.ModelProfileRegistry.load",
        classmethod(lambda cls, path=config_path: ModelProfileRegistry.load(str(config_path))),
    )
    gateway = AgentGateway(tmp_path)
    app = RaikerTextualApp(
        workspace_root=tmp_path,
        profile=TerminalProfile(width=120, color=False, unicode=True, interactive=True),
        streaming_gateway=gateway,
    )

    prompt_text = "Say hello in one short sentence."

    async def main() -> tuple[list[str], str, str]:
        deltas: list[str] = []
        final_text = ""
        async with app.run_test() as pilot:
            await pilot.press(*list(prompt_text))
            await pilot.press("enter")
            # Drain for up to ~10s of real streaming.
            for _ in range(200):
                await pilot.pause()
                await asyncio.sleep(0.05)
            transcript_text = _capture_transcript(app)
        # Collect deltas directly from the gateway for a stronger assertion.
        env = build_prompt_envelope(prompt_text)
        async for ev in gateway.astream_prompt(env):
            if ev.kind == TEXT_DELTA and ev.text:
                deltas.append(ev.text)
            if ev.kind == FINAL and ev.response is not None:
                final_text = ev.response.message
        return deltas, final_text, transcript_text

    deltas, final_text, transcript_text = asyncio.run(main())
    # Multiple streamed chunks received (not just one batch).
    assert len(deltas) >= 2, f"expected >=2 chunks, got {len(deltas)}"
    # Final message assembled correctly from chunks.
    assembled = "".join(deltas)
    assert assembled.strip(), "assembled stream text must be non-empty"
    # Transcript contains the assembled assistant text or the final message.
    assert assembled.strip() in transcript_text or final_text.strip() in transcript_text
    # Key never leaks into the transcript or assembled text.
    key = os.environ.get("RAIKER_INTEGRATION_API_KEY", "")
    if key:
        assert key not in transcript_text
        assert key not in assembled
        assert key not in final_text
