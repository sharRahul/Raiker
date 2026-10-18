"""Is this local or custom server set up for Raiker? — Hermes Agent's local-server checks.

Two facts decide whether a self-hosted model can do agent work:

* **Tool calling.** Raiker sends tools on every turn. A server that refuses them
  (Ollama for a model without tool support, vLLM without
  ``--enable-auto-tool-choice``, llama.cpp without ``--jinja``) or returns the
  call as plain text (no tool-call parser) leaves the model unable to act. The
  probe sends one request with one harmless tool through the same governed
  provider path a turn uses, and reports which of those it saw.
* **Serving context.** A server may serve far less context than the model
  supports (Ollama's default, llama.cpp's ``-c``), and Raiker's instructions and
  tool list need room. The serving size is read only from a loopback server's
  own status endpoint, so this check never reaches anything off the machine
  outside the governed provider path.

The verdict names the server setting that fixes it. Nothing is changed.
"""

from __future__ import annotations

import contextlib
from typing import Any

import httpx

from raiker.models.contracts import ModelMessage, ModelRequest, ToolSpec
from raiker.models.exceptions import (
    ModelProviderError,
    ProviderUnsupportedCapabilityError,
    provider_error_code,
)

PING = ToolSpec(
    "raiker_ping",
    "Confirms that tool calling works. Takes no arguments.",
    {"type": "object", "properties": {}},
)

#: Below this, Raiker's instructions and tool list crowd out the conversation.
MIN_CONTEXT_TOKENS = 32_768

_REFUSED_ADVICE = {
    "ollama": "Ollama says this model does not support tools. Choose a model Ollama lists with tools.",
    "llama.cpp": "Start llama-server with --jinja so it accepts tools.",
    "lm-studio": "Load a model whose chat template supports tools in LM Studio.",
}
_GENERIC_REFUSED = (
    "The server refused tools. vLLM needs --enable-auto-tool-choice and --tool-call-parser <family>; "
    "llama.cpp needs --jinja; SGLang needs --tool-call-parser."
)
_AS_TEXT_ADVICE = (
    "The server returned the call as plain text, not as a tool call: its tool-call parser is off "
    "(vLLM or SGLang --tool-call-parser, llama.cpp --jinja). Raiker can still read a JSON call from "
    "text for this model, but native tool calls are more reliable."
)
_NOT_CALLED_ADVICE = (
    "The model answered without calling the tool. Small models often do; a larger model, or one "
    "trained for tool use, will act more reliably."
)


def _classify(response: Any) -> str:
    calls = getattr(response, "tool_calls", None) or ()
    if any(getattr(call, "tool_name", "") == PING.name for call in calls):
        return "native"
    if PING.name in (getattr(response, "text", "") or ""):
        return "as_text"
    return "not_called"


async def probe_tool_calling(router: Any, provider: str, model: str) -> tuple[str, str | None]:
    """``(verdict, reason_code)``: native, as_text, not_called, refused or unavailable."""
    profile = router._profile(provider, model)  # noqa: SLF001 — the router's own resolution
    model_provider = router._factory(profile).create(profile)  # noqa: SLF001
    # Native parsing only: Raiker's text-JSON fallback would turn a server that
    # returns the call as text into one that looks like it calls tools.
    if hasattr(model_provider, "tool_call_mode"):
        model_provider.tool_call_mode = "native"
    request = ModelRequest(
        profile.profile_id,
        model_provider.provider,
        model_provider.model,
        [
            ModelMessage("system", "You are checking that tool calling works. Call the raiker_ping tool now."),
            ModelMessage("user", "Call raiker_ping."),
        ],
        [PING],
        max_tokens=128,
        stream=False,
    )
    try:
        response = await model_provider.chat(request)
    except ProviderUnsupportedCapabilityError as exc:
        return ("refused", provider_error_code(exc))
    except ModelProviderError as exc:
        return ("unavailable", provider_error_code(exc))
    finally:
        await model_provider.aclose()
    return (_classify(response), None)


def serving_context(provider: str, endpoint: str, model: str, *, timeout: float = 3.0) -> int | None:
    """The context a *loopback* server is serving ``model`` with, when it says."""
    from raiker.models.local_service import service_root

    root = service_root(endpoint)
    if root is None:
        return None
    with contextlib.suppress(httpx.HTTPError, ValueError, TypeError, KeyError), httpx.Client(
        timeout=timeout, trust_env=False, follow_redirects=False
    ) as client:
        if provider == "ollama":
            loaded = client.get(f"{root}/api/ps").json().get("models", [])
            for entry in loaded:
                if entry.get("name") == model or entry.get("model") == model:
                    value = entry.get("context_length")
                    return int(value) if value else None
            return None
        if provider == "llama.cpp":
            props = client.get(f"{root}/props").json()
            value = (props.get("default_generation_settings") or {}).get("n_ctx")
            return int(value) if value else None
        if provider == "lm-studio":
            info = client.get(f"{root}/api/v0/models/{model}").json()
            value = info.get("loaded_context_length")
            return int(value) if value else None
        # vLLM and other OpenAI-compatible servers publish max_model_len.
        for entry in client.get(f"{root}/v1/models").json().get("data", []):
            if entry.get("id") == model and entry.get("max_model_len"):
                return int(entry["max_model_len"])
    return None


def advice(provider: str, verdict: str, context: int | None) -> list[str]:
    notes: list[str] = []
    if verdict == "refused":
        notes.append(_REFUSED_ADVICE.get(provider, _GENERIC_REFUSED))
    elif verdict == "as_text":
        notes.append(
            "This model's Ollama template returns tool calls as plain text. Raiker can still read a "
            "JSON call from text, but a model Ollama lists with native tool support acts more reliably."
            if provider == "ollama"
            else _AS_TEXT_ADVICE
        )
    elif verdict == "not_called":
        notes.append(_NOT_CALLED_ADVICE)
    if context is not None and context < MIN_CONTEXT_TOKENS:
        setting = {
            "ollama": "set OLLAMA_CONTEXT_LENGTH (or num_ctx in a Modelfile)",
            "llama.cpp": "start llama-server with a larger -c",
            "lm-studio": "load the model with a larger context length",
        }.get(provider, "start the server with a larger --max-model-len")
        notes.append(
            f"The server is serving {context:,} tokens of context; Raiker's instructions and tools "
            f"need room, so {setting} — at least {MIN_CONTEXT_TOKENS:,}."
        )
    return notes
