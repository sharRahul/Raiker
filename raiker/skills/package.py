"""Skill packages: what a ``SKILL.md`` or ``*.skill`` file is, and how one is
validated before Raiker will store it.

A skill is instruction text, not code Raiker executes. Two shapes are accepted:

* **``SKILL.md``** — Markdown with a ``---`` frontmatter block carrying at least
  ``name`` and ``description``.
* **``*.skill``** — a zip archive holding ``<folder>/SKILL.md`` plus any
  supporting files that skill references.

Everything here is fail-closed and offline. The archive reader rejects absolute
members, parent-directory escapes, symlinks, oversized entries, and zip bombs
*before* any byte is written anywhere, and nothing in this module runs, imports,
or evaluates the content it reads. A stored skill only ever becomes prompt text.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# A skill name is a folder name and a prompt handle at once, so it is restricted
# to the same lowercase-slug shape the SKILL.md convention already uses.
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 8 * 1024 * 1024
MAX_MEMBERS = 200
MAX_SKILL_MD_BYTES = 512 * 1024
MAX_DESCRIPTION_CHARS = 2000

SKILL_MD_NAME = "SKILL.md"


class SkillValidationError(Exception):
    """A candidate package was refused. ``reason`` is a stable machine code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SkillPackage:
    """A validated package, ready to store. Metadata plus verbatim content."""

    name: str
    description: str
    skill_md: str
    files: tuple[str, ...] = field(default_factory=tuple)
    bundle: bytes | None = None
    version: str | None = None

    @property
    def checksum(self) -> str:
        payload = self.bundle if self.bundle is not None else self.skill_md.encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @property
    def byte_size(self) -> int:
        return len(self.bundle) if self.bundle is not None else len(self.skill_md.encode("utf-8"))


def parse_frontmatter(text: str) -> dict[str, str]:
    """Read the leading ``---`` block as flat ``key: value`` pairs.

    Deliberately not a YAML parser: a skill's frontmatter is a handful of scalar
    fields, and refusing to interpret anything richer keeps an uploaded document
    from reaching a real deserializer. Unknown keys are kept as strings; nested
    structures are ignored rather than guessed at.
    """
    stripped = text.lstrip("﻿")
    if not stripped.startswith("---"):
        return {}
    lines = stripped.splitlines()
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
            cleaned = cleaned[1:-1]
        fields[key.strip().lower()] = cleaned
    return fields


def _validated_name(raw: str) -> str:
    name = raw.strip().lower()
    if not _NAME_RE.match(name):
        raise SkillValidationError("skill_invalid_name")
    return name


def read_skill_md(text: str, *, fallback_name: str | None = None) -> SkillPackage:
    """Validate one ``SKILL.md`` document and return it as a package.

    ``fallback_name`` is used only when the frontmatter omits ``name`` — an
    uploaded ``my-skill.md`` can name itself from its filename, but a document
    with neither a frontmatter name nor a usable filename is refused rather than
    stored under an invented one.
    """
    if len(text.encode("utf-8")) > MAX_SKILL_MD_BYTES:
        raise SkillValidationError("skill_too_large")
    if not text.strip():
        raise SkillValidationError("skill_empty")
    fields = parse_frontmatter(text)
    raw_name = fields.get("name") or (fallback_name or "")
    name = _validated_name(raw_name)
    description = fields.get("description", "").strip()[:MAX_DESCRIPTION_CHARS]
    if not description:
        raise SkillValidationError("skill_missing_description")
    return SkillPackage(
        name=name,
        description=description,
        skill_md=text,
        files=(f"{name}/{SKILL_MD_NAME}",),
        bundle=None,
        version=fields.get("version") or None,
    )


def _safe_member_name(raw: str) -> str:
    """Reject anything that would escape the archive's own directory."""
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise SkillValidationError("skill_unsafe_member_path")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise SkillValidationError("skill_unsafe_member_path")
    return "/".join(parts)


def read_skill_bundle(data: bytes) -> SkillPackage:
    """Validate a ``*.skill`` archive and return it as a package.

    The archive is read entirely in memory and never extracted to disk. Only the
    single ``SKILL.md`` is decoded; every other member is checked for a safe name
    and a sane size and otherwise left as opaque bytes inside the stored bundle.
    """
    if len(data) > MAX_BUNDLE_BYTES:
        raise SkillValidationError("skill_too_large")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SkillValidationError("skill_not_an_archive") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise SkillValidationError("skill_too_many_files")
        total = 0
        names: list[str] = []
        skill_md_info: zipfile.ZipInfo | None = None
        for info in infos:
            # High bits of external_attr carry the Unix mode; 0xA000 is a symlink.
            if (info.external_attr >> 16) & 0xF000 == 0xA000:
                raise SkillValidationError("skill_unsafe_member_path")
            safe = _safe_member_name(info.filename)
            if not safe or info.is_dir():
                continue
            total += info.file_size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise SkillValidationError("skill_too_large")
            names.append(safe)
            if safe.rsplit("/", 1)[-1] == SKILL_MD_NAME and (
                skill_md_info is None or safe.count("/") < skill_md_info.filename.count("/")
            ):
                skill_md_info = info
        if skill_md_info is None:
            raise SkillValidationError("skill_missing_skill_md")
        if skill_md_info.file_size > MAX_SKILL_MD_BYTES:
            raise SkillValidationError("skill_too_large")
        skill_md = archive.read(skill_md_info).decode("utf-8", errors="replace")
    folder = _safe_member_name(skill_md_info.filename).rsplit("/", 1)
    fallback = folder[0] if len(folder) > 1 else None
    document = read_skill_md(skill_md, fallback_name=fallback)
    return SkillPackage(
        name=document.name,
        description=document.description,
        skill_md=document.skill_md,
        files=tuple(sorted(names)),
        bundle=data,
        version=document.version,
    )


def read_package(filename: str, data: bytes) -> SkillPackage:
    """Validate an upload by shape, choosing the reader from its extension."""
    lowered = (filename or "").strip().lower()
    if lowered.endswith(".skill") or lowered.endswith(".zip"):
        return read_skill_bundle(data)
    if lowered.endswith(".md") or lowered.endswith(".markdown") or lowered == "":
        stem = lowered.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        # A bare `SKILL.md` names the document, not the skill, so it is never a
        # fallback name — that file has to say who it is in its frontmatter.
        fallback = None if stem in ("", "skill") else stem
        return read_skill_md(data.decode("utf-8", errors="replace"), fallback_name=fallback)
    raise SkillValidationError("skill_unsupported_file_type")


# Files a working tree accumulates that are not part of the skill. Running a
# bundled script leaves a `__pycache__` beside it; shipping that would put a
# machine-specific binary in the archive and change the checksum for no reason.
_ARTIFACT_DIRS = frozenset({"__pycache__", ".git", ".pytest_cache", ".ruff_cache", "node_modules"})
_ARTIFACT_SUFFIXES = (".pyc", ".pyo")
_ARTIFACT_NAMES = frozenset({".DS_Store", "Thumbs.db"})


def _is_build_artifact(relative: Path) -> bool:
    return (
        bool(_ARTIFACT_DIRS & set(relative.parts))
        or relative.suffix in _ARTIFACT_SUFFIXES
        or relative.name in _ARTIFACT_NAMES
    )


def bundle_from_directory(folder: Path) -> bytes:
    """Pack a skill folder on disk into a ``*.skill`` archive.

    Used for the skills Raiker ships: they live as ordinary directories in the
    source tree so they are reviewable in a diff, and are packed at install time
    so a bundled reference or template travels with the skill rather than being
    lost to a single-document import.

    The archive is written with fixed timestamps so packing the same folder
    twice produces identical bytes — that is what lets the stored checksum mean
    "this content", not "this moment".
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or _is_build_artifact(path.relative_to(folder)):
                continue
            member = f"{folder.name}/{path.relative_to(folder).as_posix()}"
            info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return buffer.getvalue()


def read_bundle_member(bundle: bytes, member: str) -> str:
    """Return one text file from a stored archive.

    The requested name is normalised and re-checked against the archive's own
    listing rather than trusted, so a caller — including a model naming a file
    from a skill's own index — cannot reach outside the bundle.
    """
    wanted = _safe_member_name(member)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            safe = _safe_member_name(info.filename)
            # Accept either the full `<folder>/path` member or the path within
            # the skill's folder, since the index shows the former and a body
            # links the latter.
            if safe == wanted or safe.split("/", 1)[-1] == wanted:
                if info.file_size > MAX_SKILL_MD_BYTES:
                    raise SkillValidationError("skill_too_large")
                return archive.read(info).decode("utf-8", errors="replace")
    raise SkillValidationError("skill_member_not_found")


def build_bundle(package: SkillPackage) -> bytes:
    """Return the archive to hand back on download.

    An uploaded ``*.skill`` is returned byte-for-byte, so what comes out is what
    went in. A skill that arrived as a bare ``SKILL.md`` is packed on demand into
    the same ``<name>/SKILL.md`` layout every other reader expects.
    """
    if package.bundle is not None:
        return package.bundle
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{package.name}/{SKILL_MD_NAME}", package.skill_md)
    return buffer.getvalue()
