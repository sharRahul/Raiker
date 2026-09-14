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
from raiker.runtime.executors.sandbox import SandboxError, post_json, post_multipart
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

#: Providers whose governed request actually carries the size.
#:
#: REM-DESIGN-01 — a control unsupported by the selected endpoint should not be
#: drawn as though it decided anything. OpenAI's images endpoints take `size`;
#: the Gemini call below sends prompt parts and a candidate count and no size at
#: all, so a size chosen for a Gemini generation was accepted by the form,
#: validated against the list above, recorded on the row, and never sent. The
#: gallery then printed it beside the picture as though it were the picture's
#: size. Named here, beside the code that does or does not send it, so the page
#: reads the fact from the runtime rather than keeping its own copy of it.
SIZED_PROVIDERS = ("openai",)

def declared_image_models(profile: dict[str, Any]) -> tuple[str, ...]:
    """Every image model this profile offers, default first.

    `image_model` is the one a generation uses when the owner does not choose;
    `image_models` is the set they may choose from. Kept as two keys because the
    default is a decision (which model an unattended call gets) and the list is
    an inventory, and collapsing them would make "first in the list" load-bearing.
    """
    listed = profile.get("image_models")
    models = [str(name) for name in listed] if isinstance(listed, list) else []
    default = str(profile.get("image_model") or "")
    if default and default not in models:
        models.insert(0, default)
    return tuple(models)


#: How many pictures one variation request may ask for. Bounded for the same
#: reason `MAX_IMAGE_BYTES` is: a count is an action argument, and an action
#: argument is a thing a model can propose. Four is a 2x2 compare grid, which is
#: what VIS2-19 asks the canvas to draw.
MAX_VARIATIONS = 4

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
        source_generation_id: str | None = None,
        kind: str = "create",
        project_id: str | None = None,
    ) -> ExecutionResult:
        # Recorded, not just returned. An owner who pressed Generate and got
        # nothing should find out why from the page rather than the audit log.
        #
        # BUG-277 — the subject is recorded on a refusal too. An edit that was
        # denied is still a thing the owner asked of a particular image, and a
        # refusal with no subject cannot be shown beside the asset it was about.
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
            source_generation_id=source_generation_id,
            kind=kind,
            project_id=project_id,
        )
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=reason,
            summary=summary,
        )

    def _subject(
        self, principal: Principal, source_generation_id: str
    ) -> tuple[dict[str, Any] | None, bytes | None, str]:
        """The owner's own prior generation, its bytes, and a reason if neither.

        BUG-277 — this is the one new piece of *authority* reasoning in the file,
        and it is the reason the resolution happens here rather than in the
        route. `source_generation_id` arrives as an action argument, and an
        action argument is a thing a model can propose: a generation id is short,
        guessable in shape, and names bytes belonging to somebody. So the lookup
        is owner-scoped at the store, and nothing about the answer is taken on
        trust afterwards.

        Three refusals, each named, and none of them distinguishes "does not
        exist" from "is not yours": an id that belongs to another owner answers
        exactly as an id that was never issued, because telling those apart is
        telling a caller that somebody else's generation exists.
        """
        owner = self._owner(principal)
        if not owner:
            return None, None, "image_source_owner_unresolved"
        row = self._store.get_image_generation(
            source_generation_id, owner_principal_id=owner
        )
        if row is None:
            return None, None, "image_source_not_found"
        if str(row.get("status")) != "ok" or not row.get("attachment_id"):
            # A refused generation has no picture, so there is nothing to edit.
            return None, None, "image_source_has_no_image"
        blob = self._store.load_attachment(
            str(row["attachment_id"]), owner_principal_id=owner
        )
        data = (blob or {}).get("data") if isinstance(blob, dict) else None
        if not isinstance(data, bytes) or not data:
            return None, None, "image_source_bytes_missing"
        return row, data, ""

    # ── execute ──

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        prompt = str(action.arguments.get("prompt", "")).strip()
        profile_id = str(action.arguments.get("profile_id", "")).strip()
        size = str(action.arguments.get("size", "") or SUPPORTED_SIZES[0]).strip()
        # BUG-277 — the three requests this executor now understands, and the
        # arguments that tell them apart. A request naming a subject is an edit;
        # one asking for more than one picture is a variation; one doing neither
        # is what this executor has always done.
        source_id = str(action.arguments.get("source_generation_id", "") or "").strip()
        project_id = str(action.arguments.get("project_id", "") or "").strip() or None
        # `or 1` here would swallow an explicit zero, because zero is falsy —
        # found live on 2026-09-12, where asking for no images quietly produced
        # one. Absent and zero are different requests: one named no count, the
        # other named a count this executor will not serve.
        asked = action.arguments.get("variations", 1)
        try:
            variations = 1 if asked is None else int(asked)
        except (TypeError, ValueError):
            variations = 0  # refused below rather than silently treated as one
        kind = "edit" if source_id else ("variation" if variations > 1 else "create")

        if variations < 1 or variations > MAX_VARIATIONS:
            return self._fail(
                action, principal, f"unsupported_variation_count:{variations}",
                f"Image generation denied: ask for between 1 and {MAX_VARIATIONS} images.",
                profile_id=profile_id, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )
        if not prompt:
            return self._fail(
                action, principal, "missing_argument:prompt",
                "Image generation denied: a prompt is required.",
                profile_id=profile_id, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )
        if len(prompt) > MAX_PROMPT_CHARS:
            return self._fail(
                action, principal, "prompt_too_long",
                f"Image generation denied: the prompt is over {MAX_PROMPT_CHARS} characters.",
                profile_id=profile_id, size=size, prompt=prompt[:MAX_PROMPT_CHARS],
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )
        if size not in SUPPORTED_SIZES:
            return self._fail(
                action, principal, f"unsupported_size:{size}",
                f"Image generation denied: size must be one of {', '.join(SUPPORTED_SIZES)}.",
                profile_id=profile_id, prompt=prompt, size=SUPPORTED_SIZES[0],
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )
        if not profile_id:
            return self._fail(
                action, principal, "missing_argument:profile_id",
                "Image generation denied: choose a configured provider first.",
                prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )

        profile = self._profile(profile_id)
        if profile is None:
            return self._fail(
                action, principal, f"unknown_profile:{profile_id}",
                "Image generation denied: that model profile is not configured.",
                profile_id=profile_id, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )
        provider = str(profile.get("provider", ""))
        declared = declared_image_models(profile)
        requested = str(action.arguments.get("model") or "")
        model = requested or str(profile.get("image_model") or "")
        # An action argument is a thing a model can propose, and this one names
        # what gets posted to the provider. The URL is built from the profile so
        # a prompt cannot redirect the request, but an undeclared model would
        # still be a free-text string this runtime forwards without
        # understanding it — the same objection that bounds `SUPPORTED_SIZES`.
        if requested and requested not in declared:
            return self._fail(
                action, principal, f"image_model_not_declared:{requested}",
                "Image generation denied: that model is not one this provider "
                "declares for images.",
                profile_id=profile_id, provider=provider, model=requested,
                prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )
        if provider not in SUPPORTED_PROVIDERS:
            return self._fail(
                action, principal, f"image_provider_unsupported:{provider or 'unknown'}",
                f"Image generation denied: {provider or 'that provider'} has no governed "
                "image endpoint in this build.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )
        if not model:
            return self._fail(
                action, principal, "image_model_missing",
                "Image generation denied: no image model is named for this provider.",
                profile_id=profile_id, provider=provider, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )

        allowlist = model_egress_allowlist()
        if not allowlist:
            return self._fail(
                action, principal, "egress_denied:no_allowlist",
                "Image generation denied: RAIKER_MODEL_EGRESS_ALLOWLIST is empty, so no "
                "provider host may be reached.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )

        api_key = self._api_key(principal, profile_id, profile)
        if not api_key:
            return self._fail(
                action, principal, "image_provider_credential_missing",
                f"Image generation denied: no credential is saved for {provider}. Connect it "
                "on the Models page, or set its environment variable.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )

        # BUG-277 — the subject, if one was named. Resolved *after* policy and
        # the credential, so a request that was never going to reach a provider
        # does not read somebody's bytes on the way to being refused.
        subject_bytes: bytes | None = None
        if source_id:
            _, subject_bytes, refusal = self._subject(principal, source_id)
            if refusal:
                return self._fail(
                    action, principal, refusal,
                    "Image editing denied: that image is not one this account can edit.",
                    profile_id=profile_id, provider=provider, model=model,
                    prompt=prompt, size=size,
                    source_generation_id=source_id, kind=kind, project_id=project_id,
                )

        try:
            response = _call_provider(
                provider,
                model,
                prompt,
                size,
                api_key,
                allowlist,
                subject=subject_bytes,
                count=variations,
            )
        except _UnsupportedRequest as exc:
            return self._fail(
                action, principal, str(exc),
                f"Image editing denied: {provider} has no governed edit endpoint in this build.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )
        except SandboxError as exc:
            return self._fail(
                action, principal, str(exc),
                "Image generation could not reach the provider.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )

        try:
            pictures = _decode_images(provider, response, count=variations)
        except _ProviderShapeError as exc:
            return self._fail(
                action, principal, str(exc),
                "The provider answered, but not with an image this build understands.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )

        oversized = next((len(p) for p in pictures if len(p) > MAX_IMAGE_BYTES), 0)
        if oversized:
            return self._fail(
                action, principal, "image_too_large",
                f"The provider returned {oversized} bytes, over the {MAX_IMAGE_BYTES} limit.",
                profile_id=profile_id, provider=provider, model=model, prompt=prompt, size=size,
                source_generation_id=source_id or None, kind=kind, project_id=project_id,
            )

        # One row per picture. A variation request that returned four images is
        # four assets an owner can pin, compare and edit separately — collapsing
        # them into one row with four attachments would make the second, third
        # and fourth unaddressable, and an edit has to be able to name exactly
        # one subject.
        ids: list[str] = []
        total = 0
        for picture in pictures:
            generation_id = new_id("img_")
            attachment_id = new_id("att_")
            self._store.save_attachment(
                attachment_id=attachment_id,
                kind="generated_image",
                filename=f"{generation_id}.png",
                media_type="image/png",
                sha256=hashlib.sha256(picture).hexdigest(),
                data=picture,
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
                byte_size=len(picture),
                source_generation_id=source_id or None,
                kind=kind,
                project_id=project_id,
            )
            ids.append(generation_id)
            total += len(picture)

        made = "image" if len(ids) == 1 else "images"
        verb = {"edit": "Edited", "variation": "Generated", "create": "Generated"}[kind]
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"{verb} {len(ids)} {size} {made} with {model} ({total} bytes).",
            # Metadata only. Never the prompt, never the credential, never the
            # bytes — an event carries what happened, not what was made.
            artifacts={
                "generation_id": ids[0],
                "generation_ids": ids,
                "provider": provider,
                "model": model,
                "size": size,
                "kind": kind,
                "source_generation_id": source_id or None,
                "byte_size": total,
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


class _UnsupportedRequest(Exception):
    """This provider has no governed path for the request that was asked for."""


def _call_provider(
    provider: str,
    model: str,
    prompt: str,
    size: str,
    api_key: str,
    allowlist: frozenset[str],
    *,
    subject: bytes | None,
    count: int,
) -> dict[str, Any]:
    """Make the one request this generation needs, through the governed egress.

    The URL is built here from the provider, never taken from the request, for
    the same reason the channel adapter builds Telegram's: a model-proposed URL
    is untrusted, and a credential must only ever be sent to the host it belongs
    to. That rule is unchanged by BUG-277 — an edit names a *subject*, and the
    subject is bytes this runtime already holds, never an address.

    The two providers reach an edit by different routes, and neither route is a
    new boundary:

    * **OpenAI** takes the image as a file part at ``/v1/images/edits``, so an
      edit goes through :func:`post_multipart`, which enforces the same
      allowlist, in the same order, with the same reason codes as
      :func:`post_json`.
    * **Gemini** takes the image as inline base64 in the same
      ``generateContent`` body it already uses, so an edit is the ordinary JSON
      call with one more part.
    """
    if provider == "openai":
        headers = {"Authorization": f"Bearer {api_key}"}
        if subject is None:
            return post_json(
                "https://api.openai.com/v1/images/generations",
                {"model": model, "prompt": prompt, "size": size, "n": count},
                egress_allowlist=allowlist,
                headers=headers,
                timeout=120.0,
            )
        return post_multipart(
            "https://api.openai.com/v1/images/edits",
            {"model": model, "prompt": prompt, "size": size, "n": str(count)},
            {"image": ("source.png", "image/png", subject)},
            egress_allowlist=allowlist,
            headers=headers,
            timeout=180.0,
        )

    if provider == "gemini":
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if subject is not None:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(subject).decode("ascii"),
                    }
                }
            )
        if count > 1:
            # Gemini returns whatever candidates it chooses; asking for a count
            # is a candidate-count request rather than an `n`.
            body: dict[str, Any] = {
                "contents": [{"parts": parts}],
                "generationConfig": {"candidateCount": count},
            }
        else:
            body = {"contents": [{"parts": parts}]}
        return post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            body,
            egress_allowlist=allowlist,
            headers={"x-goog-api-key": api_key},
            timeout=180.0,
        )

    # Unreachable through `execute`, which checks SUPPORTED_PROVIDERS first.
    # Stated anyway: a provider added to that tuple without a path here should
    # fail with a name rather than fall through to whichever branch is last.
    raise _UnsupportedRequest(f"image_provider_unsupported:{provider or 'unknown'}")


def _decode_images(
    provider: str, response: dict[str, Any], *, count: int = 1
) -> list[bytes]:
    """Every image the provider returned, or a named refusal.

    Every branch here is a shape this build has been told to expect. A provider
    that answers with something else gets a reason code rather than a traceback,
    because "the provider changed its response" is an ordinary event and an
    owner needs to be able to read it.

    BUG-277 — a list rather than one picture, because a variation request asks
    for several and each of them is an asset in its own right. A provider that
    returns fewer than `count` is not an error: the count is what was asked for,
    and what came back is what there is.
    """
    payload = response.get("result") if isinstance(response.get("result"), dict) else response
    if not isinstance(payload, dict):
        raise _ProviderShapeError("image_response_unreadable")

    encoded: list[str] = []
    if provider == "openai":
        data = payload.get("data")
        for entry in data if isinstance(data, list) else []:
            candidate = entry.get("b64_json") if isinstance(entry, dict) else None
            if isinstance(candidate, str) and candidate:
                encoded.append(candidate)
    else:
        candidates = payload.get("candidates")
        for candidate in candidates if isinstance(candidates, list) else []:
            content = candidate.get("content") if isinstance(candidate, dict) else None
            parts = content.get("parts") if isinstance(content, dict) else None
            for part in parts if isinstance(parts, list) else []:
                if not isinstance(part, dict):
                    continue
                # Gemini answers camelCase; the request sends snake_case. Both
                # spellings are read because the one that arrives is the
                # provider's choice, not this runtime's.
                inline = part.get("inlineData") or part.get("inline_data")
                if isinstance(inline, dict) and isinstance(inline.get("data"), str):
                    encoded.append(str(inline["data"]))

    if not encoded:
        # A refusal from the provider is the common case here, and it is not the
        # same thing as a broken response.
        if _looks_like_refusal(payload):
            raise _ProviderShapeError("image_refused_by_provider")
        raise _ProviderShapeError("image_response_missing_data")

    pictures: list[bytes] = []
    for blob in encoded[: max(1, count)]:
        try:
            pictures.append(base64.b64decode(blob, validate=True))
        except (binascii.Error, ValueError):
            raise _ProviderShapeError("image_response_not_base64") from None
    return pictures


def _looks_like_refusal(payload: dict[str, Any]) -> bool:
    blob = json.dumps(payload).lower()
    return any(
        marker in blob
        for marker in ("content_policy", "safety", "blocked", "refus", "moderation")
    )
