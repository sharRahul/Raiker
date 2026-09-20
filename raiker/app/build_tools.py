"""The external build tools a release is allowed to fetch, pinned by digest.

GCR-41. The Linux job used to fetch `appimagetool` from the AppImage project's
`continuous` release — a tag that is moved, by design, whenever that project
publishes. Two builds of the same Raiker commit, a week apart, therefore
contained different build-tool bytes while every other part of the release
process was careful to be deterministic: sorted zip members, one fixed
timestamp, normalised modes, `SOURCE_DATE_EPOCH`.

That is the difference between a build that is reproducible and one that merely
*looks* reproducible. So the tool is named by an immutable version tag and by
the SHA-256 of the exact file, the release job refuses anything else, and what
it used travels in the artifact's own provenance where an owner — or an auditor
asking what produced this binary — can read it back.

The pins live in ``raiker/config/build-tools.json`` rather than inside the
workflow so one file answers "what does a release download?", and so a test can
check it against the targets the release actually has.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

#: The pin file's shape, so a future change to it is a visible schema change.
BUILD_TOOLS_SCHEMA = 1


@dataclass(frozen=True)
class PinnedTool:
    """One external tool, for one architecture, at one exact set of bytes."""

    name: str
    version: str
    os_name: str
    purpose: str
    arch: str
    url: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "arch": self.arch,
            "url": self.url,
            "sha256": self.sha256,
        }


@lru_cache(maxsize=1)
def _raw() -> dict[str, Any]:
    text = files("raiker.config").joinpath("build-tools.json").read_text(encoding="utf-8")
    payload: dict[str, Any] = json.loads(text)
    if int(payload.get("schema", 0)) != BUILD_TOOLS_SCHEMA:
        raise ValueError("build_tools_schema_unknown")
    return payload


def pinned_tools() -> tuple[PinnedTool, ...]:
    """Every pinned tool, flattened to one entry per architecture."""
    entries: list[PinnedTool] = []
    for tool in _raw()["tools"]:
        for arch, artifact in sorted(tool["artifacts"].items()):
            digest = str(artifact["sha256"])
            if len(digest) != 64 or not all(c in "0123456789abcdef" for c in digest):
                raise ValueError("build_tool_digest_invalid")
            entries.append(
                PinnedTool(
                    name=str(tool["name"]),
                    version=str(tool["version"]),
                    os_name=str(tool["os"]),
                    purpose=str(tool["purpose"]),
                    arch=arch,
                    url=str(artifact["url"]),
                    sha256=digest,
                )
            )
    return tuple(entries)


def pinned_tool(name: str, arch: str) -> PinnedTool:
    """The one pin for *name* on *arch*, or a refusal naming what is missing.

    A refusal rather than a fallback: the whole point is that an unpinned tool
    never gets downloaded, so "no pin for this architecture" has to stop the
    release rather than quietly reach for whatever the project publishes today.
    """
    for tool in pinned_tools():
        if tool.name == name and tool.arch == arch:
            return tool
    raise ValueError(f"build_tool_not_pinned:{name}:{arch}")


def tools_for(os_name: str, arch: str) -> tuple[PinnedTool, ...]:
    """The pinned tools a build on this platform may fetch."""
    return tuple(
        tool for tool in pinned_tools() if tool.os_name == os_name and tool.arch == arch
    )
