"""Governed image generation — the executor behind the Design surface.

Tier 2 for the reason every Tier-2 capability is: it leaves the machine. An
image model is a hosted model, so this answers to the *same* boundaries a chat
completion answers to and adds none of its own:

* the ``image_generation`` capability gate, checked by
  :class:`~raiker.runtime.authority.router.RuntimeAuthority` before an executor
  is reached at all;
* ``RAIKER_MODEL_EGRESS_ALLOWLIST``, which must already name the provider's
  host — an API key is not authorisation to reach the network, and the two
  decisions stay separate here as everywhere else;
* the owner's saved provider connection, or an owner environment variable.
  A credential never arrives in an action argument, because an action argument
  is a thing a model can propose.

What it deliberately does *not* do is invent a second way to reach a provider.
The endpoint is built from the profile the owner configured on the Models page,
never from the request, so a prompt cannot redirect a generation at a host the
owner did not name.

The bytes land in ``attachments``, which is already the one owner-scoped,
sha256-addressed binary store in this product; ``image_generations`` records the
attempt beside them, including the attempts that were refused.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id
from raiker.models.connections import get_model_connection
from raiker.models.endpoint_policy import model_egress_allowlist
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, post_json
from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction

#: Providers with a governed image endpoint. Anything else fails closed rather
#: than being attempted hopefully — an unsupported provider is a refusal with a
#: name, not a request that quietly goes nowhere.
SUPPORTED_PROVIDERS = ("openai", "gemini")

#: What the owner may ask for. A free-text size would be a string this runtime
#: forwards to a provider without understanding it.
SUPPORTED_SIZES = ("1024x1024", "1536x1024", "1024x1536")

MAX_PROMPT_CHARS = 4_000
#: Above this an image is refused rather than stored. The bytes go in the same
#: table as user attachments and a generation is not a licence to fill it.
MAX_IMAGE_BYTES = 8_000_000


class ImageGenerationExecutor:
    """Real executor for ``image_generation``."""

    capability = "image_generation"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store

    # ── helpers ──

    def _owner(self, principal: Principal) -> str | None:
        return getattr(principal, "principal_id", None)

    def _record(self, **kwargs: Any) -> None:
        self._store.record_image_generation(**kwargs)

    def _fail(
        self,
        action: GovernedAction,
        principal: Principal,
        reason: str,
        summary: str,
        *,
        profile_id: str = "",
        provider: str = "",
        model: str = "",
        prompt: str = "",
        size: str = "",
    ) -> ExecutionResult:
        # Recorded, not just returned. An owner who pressed Generate and got
        # nothing should find out why from the page rather than the audit log.
        self._record(
            generation_id=new_id("img_"),
            owner_principal_id=self._owner(principal),
            profile_id=profile_id,
            provider=provider,
            model=model,
            prompt=prompt,
            size=size or SUPPORTED_SIZES[0],
            status="refused",
            reason_code=reason,
        )
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=reason,
            summary=summary,
        )

    # ── execute ──

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        prompt = str(action.arguments.get("prompt", "")).strip()
        profile_id = str(action.arguments.get("profile_id", "")).strip()
        size = str(action.arguments.get("size", "") or SUPPORTED_SIZES[0]).strip()

        if not prompt:
            return self._fail(
                action, principal, "missing_argument:prompt",
                "Image generation denied: a prompt is required.",
                profile_id=profile_id, size=size,
            )
        if len(prompt) > MAX_PROMPT_CHARS:
            return self._fail(
                action, principal, "prompt_too_long",
                f"Image generation denied: the prompt is over {MAX_PROMPT_CHARS} characters.",
                profile_id=profile_id, size=size, prompt=prompt[:MAX_PROMPT_CHARS],
            )
        if size not in SUPPORTED_SIZES:
            return self._fail(
                action, principal, f"unsupported_size:{size}",
                f"Image generation denied: size must be one of {', '.join(SUPPORTED_SIZES)}.",
                profile_id=profile_id, prompt=prompt, size=SUPPORTED_SIZES[0],
            )
        if not profile_id:
            return self._fail(
                action, principal, "missing_argument:profile_id",
                "Image generation denied: choose a configured provider first.",
                prompt=prompt, size=size,
            )

        profile = self._profile(profile_id)
        if profile is None:
            return self._fail(
                action, principal, f"unknown_profile:{profile_id}",
                "Image generation denied: that model profile is not configured.",
                profile_id=profile_id, prompt=prompt, size=size,
            )
        provider = str(profile.get("provider", ""))
        model = str(action.arguments.get("model") or profile.get("image_model") or "")
        if provider not in SUPPORTED_PROVIDERS:
            return self._fail(
                action, principal, f"image_provider_unsupported:{provider or 'unknown'}",
                f"Image generation denied: {provider or 'that provider'} has no governed "
                "image endpoint in this build.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
            )
        if not model:
            return self._fail(
                action, principal, "image_model_missing",
                "Image generation denied: no image model is named for this provider.",
                profile_id=profile_id, provider=provider, prompt=prompt, size=size,
            )

        allowlist = model_egress_allowlist()
        if not allowlist:
            return self._fail(
                action, principal, "egress_denied:no_allowlist",
                "Image generation denied: RAIKER_MODEL_EGRESS_ALLOWLIST is empty, so no "
                "provider host may be reached.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
            )

        api_key = self._api_key(principal, profile_id, profile)
        if not api_key:
            return self._fail(
                action, principal, "image_provider_credential_missing",
                f"Image generation denied: no credential is saved for {provider}. Connect it "
                "on the Models page, or set its environment variable.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
            )

        url, body, headers = _request_for(provider, model, prompt, size, api_key)
        try:
            response = post_json(
                url,
                body,
                egress_allowlist=allowlist,
                headers=headers,
                timeout=120.0,
            )
        except SandboxError as exc:
            return self._fail(
                action, principal, str(exc),
                "Image generation could not reach the provider.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
            )

        try:
            raw = _decode_image(provider, response)
        except _ProviderShapeError as exc:
            return self._fail(
                action, principal, str(exc),
                "The provider answered, but not with an image this build understands.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
            )

        if len(raw) > MAX_IMAGE_BYTES:
            return self._fail(
                action, principal, "image_too_large",
                f"The provider returned {len(raw)} bytes, over the {MAX_IMAGE_BYTES} limit.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
            )

        generation_id = new_id("img_")
        attachment_id = new_id("att_")
        self._store.save_attachment(
            attachment_id=attachment_id,
            kind="generated_image",
            filename=f"{generation_id}.png",
            media_type="image/png",
            sha256=hashlib.sha256(raw).hexdigest(),
            data=raw,
            owner_principal_id=self._owner(principal),
        )
        self._record(
            generation_id=generation_id,
            owner_principal_id=self._owner(principal),
            profile_id=profile_id,
            provider=provider,
            model=model,
            prompt=prompt,
            size=size,
            status="ok",
            attachment_id=attachment_id,
            media_type="image/png",
            byte_size=len(raw),
        )
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"Generated one {size} image with {model} ({len(raw)} bytes).",
            # Metadata only. Never the prompt, never the credential, never the
            # bytes — an event carries what happened, not what was made.
            artifacts={
                "generation_id": generation_id,
                "attachment_id": attachment_id,
                "provider": provider,
                "model": model,
                "size": size,
                "byte_size": len(raw),
            },
        )

    # ── provider plumbing ──

    def _profile(self, profile_id: str) -> dict[str, Any] | None:
        from raiker.models.registry import ModelProfileRegistry

        try:
            registry = ModelProfileRegistry.load()
        except Exception:
            return None
        for profile in registry.list_profiles():
            raw = getattr(profile, "raw", None)
            if isinstance(raw, dict) and raw.get("profile_id") == profile_id:
                return raw
        return None

    def _api_key(
        self, principal: Principal, profile_id: str, profile: dict[str, Any]
    ) -> str:
        """The owner's credential, from the vault or their environment.

        Never from the action: an argument is something a model can propose, and
        a proposed credential is a credential somebody else chose.
        """
        import os

        owner = self._owner(principal)
        if owner:
            saved = get_model_connection(self._store, owner, profile_id) or {}
            key = str(saved.get("api_key", "")).strip()
            if key:
                return key
        env_name = profile.get("api_key_env")
        if isinstance(env_name, str) and env_name:
            return os.environ.get(env_name, "").strip()
        return ""


class _ProviderShapeError(Exception):
    """The provider answered with something this build cannot read as an image."""


def _request_for(
    provider: str, model: str, prompt: str, size: str, api_key: str
) -> tuple[str, dict[str, object], dict[str, str]]:
    """``(url, body, headers)`` for one generation.

    The URL is built here from the provider, never taken from the request, for
    the same reason the channel adapter builds Telegram's: a model-proposed URL
    is untrusted, and a credential must only ever be sent to the host it belongs
    to.
    """
    if provider == "openai":
        return (
            "https://api.openai.com/v1/images/generations",
            {"model": model, "prompt": prompt, "size": size, "n": 1},
            {"Authorization": f"Bearer {api_key}"},
        )
    # Gemini takes its key in a header rather than a bearer token, and returns
    # inline base64 parts rather than a data list.
    return (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"contents": [{"parts": [{"text": prompt}]}]},
        {"x-goog-api-key": api_key},
    )


def _decode_image(provider: str, response: dict[str, Any]) -> bytes:
    """The image bytes, or a named refusal.

    Every branch here is a shape this build has been told to expect. A provider
    that answers with something else gets a reason code rather than a traceback,
    because "the provider changed its response" is an ordinary event and an
    owner needs to be able to read it.
    """
    payload = response.get("result") if isinstance(response.get("result"), dict) else response
    if not isinstance(payload, dict):
        raise _ProviderShapeError("image_response_unreadable")

    encoded: str | None = None
    if provider == "openai":
        data = payload.get("data")
        if isinstance(data, list) and data and isinstance(data[0], dict):
            candidate = data[0].get("b64_json")
            if isinstance(candidate, str):
                encoded = candidate
    else:
        candidates = payload.get("candidates")
        if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
            content = candidates[0].get("content")
            parts = content.get("parts") if isinstance(content, dict) else None
            for part in parts if isinstance(parts, list) else []:
                inline = part.get("inlineData") if isinstance(part, dict) else None
                if isinstance(inline, dict) and isinstance(inline.get("data"), str):
                    encoded = str(inline["data"])
                    break

    if not encoded:
        # A refusal from the provider is the common case here, and it is not the
        # same thing as a broken response.
        if _looks_like_refusal(payload):
            raise _ProviderShapeError("image_refused_by_provider")
        raise _ProviderShapeError("image_response_missing_data")
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise _ProviderShapeError("image_response_not_base64") from None


def _looks_like_refusal(payload: dict[str, Any]) -> bool:
    blob = json.dumps(payload).lower()
    return any(
        marker in blob
        for marker in ("content_policy", "safety", "blocked", "refus", "moderation")
    )
