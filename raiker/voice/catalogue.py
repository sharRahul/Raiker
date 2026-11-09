# SPDX-License-Identifier: Apache-2.0
"""The voice catalogue: every downloadable voice component, and nothing else.

Voice spec §5.6. ``raiker/config/voice-catalogue.json`` lists engine builds,
Whisper models and speaking models and voices, each with its source, licence,
SHA-256 and size. The installer downloads only what this module says is
installable:

* the entry has a ``url``, a 64-hex ``sha256`` and a positive ``size_bytes``;
* its licence is on :data:`PERMISSIVE_LICENCES`;
* it carries no ``pending_reason``.

An entry that is missing any of those is still listed — so Settings can say
*why* a component is not offered yet — but :func:`require_installable` refuses
it with a reason code. Nothing is downloaded on a hope.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOGUE_PATH = Path(__file__).resolve().parents[1] / "config" / "voice-catalogue.json"

#: Licences a downloaded component may carry. Anything else (including
#: ``unreviewed``) needs sign-off under LICENSING_POLICY.md first.
PERMISSIVE_LICENCES = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0", "CC-BY-4.0"})

#: Hosts a voice download may come from, redirects included.
ALLOWED_DOWNLOAD_HOSTS = frozenset({
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.huggingface.co",
    "cas-bridge.xethub.hf.co",
    "us.aws.cdn.hf.co",
    "us.gcp.cdn.hf.co",
})

COMPONENTS = frozenset({
    "vad", "whisper_engine", "whisper_model", "kokoro_model", "kokoro_voices",
})

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CatalogueError(ValueError):
    """A catalogue that does not hold together, or a refused item. A reason code."""

    bounded_reason = True


@dataclass(frozen=True)
class CatalogueItem:
    item_id: str
    component: str
    name: str
    licence: str
    source_page: str
    url: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    approx_size_bytes: int | None = None
    platform: dict[str, str] | None = None
    executable: str | None = None
    languages: tuple[str, ...] = ()
    profiles: tuple[str, ...] = ()
    tier: str | None = None
    english_only: bool = False
    memory_bytes_cpu: int | None = None
    memory_bytes_gpu: int | None = None
    voices: tuple[str, ...] = ()
    bundled: bool = False
    pending_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def installable(self) -> bool:
        return self.refusal() is None

    def refusal(self) -> str | None:
        """Why this item is not installable, as a reason code, or ``None``."""
        if self.bundled:
            return "voice_item_bundled"
        if self.pending_reason:
            return "voice_item_pending"
        if self.licence not in PERMISSIVE_LICENCES:
            return "voice_item_licence_unreviewed"
        if not self.url or not self.sha256 or not _SHA256.fullmatch(self.sha256):
            return "voice_item_unverified"
        if not self.size_bytes or self.size_bytes <= 0:
            return "voice_item_unverified"
        return None

    @property
    def display_size(self) -> int | None:
        return self.size_bytes or self.approx_size_bytes

    def matches(self, os_name: str, arch: str) -> bool:
        if self.platform is None:
            return True
        return self.platform.get("os") == os_name and self.platform.get("arch") == arch


@dataclass(frozen=True)
class Profile:
    profile_id: str
    name: str
    audience: str
    listening: tuple[str, ...]
    speaking: str
    speaking_items: tuple[str, ...]


@dataclass(frozen=True)
class Catalogue:
    items: tuple[CatalogueItem, ...]
    profiles: dict[str, Profile]

    def get(self, item_id: str) -> CatalogueItem:
        for item in self.items:
            if item.item_id == item_id:
                return item
        raise CatalogueError("voice_item_unknown")

    def of(self, component: str) -> list[CatalogueItem]:
        return [item for item in self.items if item.component == component]

    def engine_for(self, component: str, os_name: str, arch: str, backends: tuple[str, ...] = ("cpu",)) -> CatalogueItem | None:
        """The engine build for this machine, preferring the first backend that has one.

        An installable build wins over a pending one, so a machine whose GPU
        build is pending still gets the processor build.
        """
        candidates = [item for item in self.of(component) if item.matches(os_name, arch)]
        for wanted_installable in (True, False):
            for backend in backends:
                for item in candidates:
                    if item.installable == wanted_installable and (item.platform or {}).get("backend") == backend:
                        return item
        return candidates[0] if candidates else None


def _item(entry: dict[str, Any]) -> CatalogueItem:
    for key in ("id", "component", "name", "licence", "source_page"):
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise CatalogueError("voice_catalogue_invalid")
    if entry["component"] not in COMPONENTS:
        raise CatalogueError("voice_catalogue_invalid")
    return CatalogueItem(
        item_id=entry["id"],
        component=entry["component"],
        name=entry["name"],
        licence=entry["licence"],
        source_page=entry["source_page"],
        url=entry.get("url"),
        sha256=entry.get("sha256"),
        size_bytes=entry.get("size_bytes"),
        approx_size_bytes=entry.get("approx_size_bytes"),
        platform=entry.get("platform"),
        executable=entry.get("executable"),
        languages=tuple(entry.get("languages") or ()),
        profiles=tuple(entry.get("profiles") or ()),
        tier=entry.get("tier"),
        english_only=bool(entry.get("english_only")),
        memory_bytes_cpu=entry.get("memory_bytes_cpu"),
        memory_bytes_gpu=entry.get("memory_bytes_gpu"),
        voices=tuple(entry.get("voices") or ()),
        bundled=bool(entry.get("bundled")),
        pending_reason=entry.get("pending_reason"),
        raw=entry,
    )


def parse(data: dict[str, Any]) -> Catalogue:
    if data.get("schema_version") != 1 or not isinstance(data.get("items"), list):
        raise CatalogueError("voice_catalogue_invalid")
    items = tuple(_item(entry) for entry in data["items"])
    ids = [item.item_id for item in items]
    if len(ids) != len(set(ids)):
        raise CatalogueError("voice_catalogue_duplicate_id")
    profiles: dict[str, Profile] = {}
    for profile_id, raw in dict(data.get("profiles") or {}).items():
        profile = Profile(
            profile_id=profile_id,
            name=str(raw["name"]),
            audience=str(raw.get("for") or ""),
            listening=tuple(raw.get("listening") or ()),
            speaking=str(raw["speaking"]),
            speaking_items=tuple(raw.get("speaking_items") or ()),
        )
        for item_id in (*profile.listening, *profile.speaking_items):
            if item_id not in ids:
                raise CatalogueError("voice_catalogue_profile_unknown_item")
        if profile.speaking not in {"kokoro", "system"}:
            raise CatalogueError("voice_catalogue_invalid")
        profiles[profile_id] = profile
    return Catalogue(items=items, profiles=profiles)


@lru_cache(maxsize=1)
def load(path: str | None = None) -> Catalogue:
    raw = json.loads((Path(path) if path else CATALOGUE_PATH).read_text(encoding="utf-8"))
    return parse(raw)


def require_installable(item: CatalogueItem) -> CatalogueItem:
    reason = item.refusal()
    if reason is not None:
        raise CatalogueError(reason)
    return item
