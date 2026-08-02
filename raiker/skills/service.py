"""Owner-scoped skill management: install, rename, activate, download, delete.

A skill is instruction text. Installing one adds guidance to the turns the owner
allows it on — it grants no capability, opens no gate, and Raiker never executes
anything a skill ships. Every mutation here is human-only and owner-scoped, and
every stored document was validated by :mod:`raiker.skills.package` first.

The one path that touches the network is :meth:`SkillsService.import_from_url`.
It reads a single document over HTTPS through the existing sandbox egress
boundary, so it fails closed unless the owner has allowlisted the host, and the
fetched bytes are validated as a skill before anything is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from raiker.cli.principal_resolver import resolve_local_principal
from raiker.contracts.ids import new_id
from raiker.control.dtos import ControlResult
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import PrincipalType
from raiker.skills.package import (
    SkillPackage,
    SkillValidationError,
    build_bundle,
    bundle_from_directory,
    read_package,
    read_skill_bundle,
    read_skill_md,
)
from raiker.storage.sqlite import SQLiteStore

BUILTIN_ROOT = Path(__file__).resolve().parent / "builtin"

# Hosts a skill may be imported from. GitHub raw content and the release/blob
# hosts are the two places a published skill actually lives; anything else is
# refused by name rather than silently attempted, so the owner sees why.
IMPORT_HOSTS: frozenset[str] = frozenset(
    {"raw.githubusercontent.com", "github.com", "gist.githubusercontent.com"}
)

MAX_IMPORT_BYTES = 512 * 1024


@dataclass(frozen=True)
class SkillView:
    """One installed skill as the Skills tab reads it. Never carries the bundle."""

    skill_id: str
    name: str
    description: str
    version: str | None
    source: str
    source_ref: str | None
    checksum: str
    active: bool
    files: tuple[str, ...]
    byte_size: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "source": self.source,
            "source_ref": self.source_ref,
            "checksum": self.checksum,
            "active": self.active,
            "files": list(self.files),
            "file_count": len(self.files),
            "byte_size": self.byte_size,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _view(row: dict[str, Any]) -> SkillView:
    return SkillView(
        skill_id=str(row["skill_id"]),
        name=str(row["name"]),
        description=str(row.get("description", "")),
        version=row.get("version"),
        source=str(row.get("source", "upload")),
        source_ref=row.get("source_ref"),
        checksum=str(row.get("checksum", "")),
        active=bool(row.get("active", False)),
        files=tuple(str(f) for f in row.get("files", [])),
        byte_size=int(row.get("byte_size", 0) or 0),
        created_at=str(row.get("created_at", "")),
        updated_at=str(row.get("updated_at", "")),
    )


def normalize_import_url(url: str) -> str | None:
    """Return the raw-content URL for a supported skill link, or None.

    A GitHub *blob* URL renders a page, not a document, so it is rewritten to
    its ``raw.githubusercontent.com`` equivalent. Anything off the import host
    list returns None and is refused by the caller — the rewrite never invents a
    host that was not already allowed.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.hostname not in IMPORT_HOSTS:
        return None
    if parsed.hostname == "github.com":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 5 or parts[2] != "blob":
            return None
        owner, repo, _, *rest = parts
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{'/'.join(rest)}"
    return f"https://{parsed.hostname}{parsed.path}"


class SkillsService:
    """Owner-scoped CRUD over installed skills, plus the governed import path."""

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root)
        self._store = SQLiteStore(workspace_root)
        self._writer = EventLogWriter(self._store)

    # ── principal resolution ────────────────────────────────────────────────
    def _human(self, acting_principal_id: str | None) -> tuple[str | None, str | None]:
        principal, err = resolve_local_principal(self._workspace_root, acting_principal_id)
        if principal is None:
            return None, err or "principal_not_resolved"
        if principal.principal_type != PrincipalType.HUMAN:
            return None, "not_authorized_human"
        return principal.principal_id, None

    # ── read ────────────────────────────────────────────────────────────────
    def list_skills(self, principal_id: str) -> list[SkillView]:
        """Every skill this owner has, newest first, after seeding the built-ins."""
        self.seed_builtins(principal_id)
        return [_view(row) for row in self._store.list_skills(principal_id)]

    def active_skill_documents(self, principal_id: str) -> list[tuple[str, str]]:
        """``(name, description)`` for the owner's active skills.

        This is the only shape the runtime needs to advertise what is installed;
        the full document is loaded on demand, not pushed into every turn.
        """
        return [
            (str(row["name"]), str(row.get("description", "")))
            for row in self._store.list_skills(principal_id)
            if row.get("active")
        ]

    def seed_builtins(self, principal_id: str) -> int:
        """Install the skills Raiker ships with, once per owner.

        Each built-in is offered exactly once and the offer is recorded, so one
        the owner deleted, renamed, or replaced is never silently restored on the
        next visit to the Skills tab.
        """
        if not BUILTIN_ROOT.is_dir():
            return 0
        already = self._store.seeded_skill_names(principal_id)
        existing = {str(row["name"]) for row in self._store.list_skills(principal_id)}
        seeded = 0
        for folder in sorted(BUILTIN_ROOT.iterdir()):
            document = folder / "SKILL.md"
            if not document.is_file() or folder.name in already:
                continue
            self._store.record_skill_seed(principal_id, folder.name)
            if folder.name in existing:
                continue
            try:
                # Packed as a bundle rather than read as a lone document, so a
                # shipped skill's references and templates install with it.
                package = read_skill_bundle(bundle_from_directory(folder))
            except SkillValidationError:
                continue
            self._persist(principal_id, package, source="builtin", source_ref=folder.name)
            seeded += 1
        return seeded

    def get_download(self, principal_id: str, skill_id: str) -> tuple[str, bytes] | None:
        """``(filename, archive bytes)`` for one skill, or None when not the
        owner's. An uploaded archive comes back byte-for-byte; a skill that
        arrived as a bare document is packed on demand."""
        row = self._store.get_skill(skill_id, principal_id)
        if row is None:
            return None
        package = SkillPackage(
            name=str(row["name"]),
            description=str(row.get("description", "")),
            skill_md=str(row.get("skill_md", "")),
            files=tuple(str(f) for f in row.get("files", [])),
            bundle=row.get("bundle"),
            version=row.get("version"),
        )
        return f"{package.name}.skill", build_bundle(package)

    # ── write ───────────────────────────────────────────────────────────────
    def _persist(
        self,
        principal_id: str,
        package: SkillPackage,
        *,
        source: str,
        source_ref: str | None,
    ) -> str:
        return self._store.upsert_skill(
            skill_id=new_id("skl_"),
            principal_id=principal_id,
            name=package.name,
            description=package.description,
            checksum=package.checksum,
            skill_md=package.skill_md,
            source=source,
            source_ref=source_ref,
            version=package.version,
            bundle=package.bundle,
            files=list(package.files),
            byte_size=package.byte_size,
        )

    def _installed(
        self,
        principal_id: str,
        package: SkillPackage,
        *,
        source: str,
        source_ref: str | None,
        event_type: str,
    ) -> ControlResult:
        skill_id = self._persist(principal_id, package, source=source, source_ref=source_ref)
        self._writer.append(
            make_event(
                session_id="skills",
                turn_id=None,
                event_type=event_type,
                actor="skills_service",
                # Metadata only — the document itself is never written to the log.
                payload={
                    "skill_id": skill_id,
                    "name": package.name,
                    "source": source,
                    "checksum": package.checksum,
                    "byte_size": package.byte_size,
                    "file_count": len(package.files),
                },
            )
        )
        row = self._store.get_skill(skill_id, principal_id)
        return ControlResult(
            ok=True,
            data={"skill_id": skill_id, "skill": _view(row).to_dict() if row else None},
        )

    def install_upload(
        self, acting_principal_id: str | None, filename: str, data: bytes
    ) -> ControlResult:
        """Store one uploaded ``SKILL.md`` or ``*.skill`` after validating it."""
        principal_id, err = self._human(acting_principal_id)
        if principal_id is None:
            return ControlResult(ok=False, reason_code=err)
        try:
            package = read_package(filename, data)
        except SkillValidationError as exc:
            return ControlResult(ok=False, reason_code=exc.reason)
        return self._installed(
            principal_id,
            package,
            source="upload",
            source_ref=(filename or "").strip()[:200] or None,
            event_type="skill_installed",
        )

    def verify_url(self, acting_principal_id: str | None, url: str) -> ControlResult:
        """Fetch and validate a linked skill **without** storing it.

        This is what the Chat and Build composers call when a skill link is
        pasted: it answers "is this really a skill, and what does it say it is"
        so the owner decides against facts rather than a URL.
        """
        return self._fetch(acting_principal_id, url, store=False)

    def import_from_url(self, acting_principal_id: str | None, url: str) -> ControlResult:
        """Verify a linked skill and, if it is one, install it."""
        return self._fetch(acting_principal_id, url, store=True)

    def _fetch(
        self, acting_principal_id: str | None, url: str, *, store: bool
    ) -> ControlResult:
        from raiker.runtime.executors.sandbox import SandboxError, get_url

        principal_id, err = self._human(acting_principal_id)
        if principal_id is None:
            return ControlResult(ok=False, reason_code=err)
        raw_url = normalize_import_url(url)
        if raw_url is None:
            return ControlResult(ok=False, reason_code="skill_unsupported_source")
        filename = raw_url.rsplit("/", 1)[-1]
        if filename.lower().endswith((".skill", ".zip")):
            # A binary archive cannot survive the text-only read boundary this
            # path deliberately uses. Refused before egress rather than fetched
            # and then corrupted — download it and upload the file instead.
            return ControlResult(ok=False, reason_code="skill_archive_url_unsupported")
        try:
            # The egress allowlist is this module's own, not a model-supplied
            # one: an import can only ever reach the published-skill hosts.
            response = get_url(raw_url, egress_allowlist=IMPORT_HOSTS, max_bytes=MAX_IMPORT_BYTES)
        except SandboxError as exc:
            return ControlResult(ok=False, reason_code=f"skill_fetch_failed:{exc}")
        if response.get("truncated"):
            return ControlResult(ok=False, reason_code="skill_too_large")
        body = str(response.get("body_text", ""))
        try:
            package = read_package(filename or "SKILL.md", body.encode("utf-8"))
        except SkillValidationError as exc:
            return ControlResult(ok=False, reason_code=exc.reason)
        if not store:
            return ControlResult(
                ok=True,
                data={
                    "verified": True,
                    "name": package.name,
                    "description": package.description,
                    "version": package.version,
                    "checksum": package.checksum,
                    "byte_size": package.byte_size,
                    "source_url": raw_url,
                    "already_installed": self._store.get_skill_by_name(
                        principal_id, package.name
                    )
                    is not None,
                },
            )
        return self._installed(
            principal_id,
            package,
            source="url",
            source_ref=raw_url,
            event_type="skill_imported",
        )

    def build_skill(
        self, acting_principal_id: str | None, name: str, description: str, body: str
    ) -> ControlResult:
        """Install a skill Raiker authored, from a name, a description, and a body.

        The document is assembled here and validated by the same reader an upload
        goes through, so a built skill is held to the identical contract.
        """
        principal_id, err = self._human(acting_principal_id)
        if principal_id is None:
            return ControlResult(ok=False, reason_code=err)
        clean_name = name.strip().lower()
        clean_description = " ".join(description.split())
        document = (
            "---\n"
            f"name: {clean_name}\n"
            f"description: {clean_description}\n"
            "---\n\n"
            f"{body.strip()}\n"
        )
        try:
            package = read_skill_md(document, fallback_name=clean_name)
        except SkillValidationError as exc:
            return ControlResult(ok=False, reason_code=exc.reason)
        return self._installed(
            principal_id,
            package,
            source="built",
            source_ref=None,
            event_type="skill_built",
        )

    def rename(
        self, acting_principal_id: str | None, skill_id: str, name: str
    ) -> ControlResult:
        principal_id, err = self._human(acting_principal_id)
        if principal_id is None:
            return ControlResult(ok=False, reason_code=err)
        try:
            # Reuse the document reader's own name rule so a renamed skill stays
            # a legal prompt handle and a legal bundle folder.
            clean = read_skill_md(
                f"---\nname: {name.strip().lower()}\ndescription: rename\n---\nx"
            ).name
        except SkillValidationError as exc:
            return ControlResult(ok=False, reason_code=exc.reason)
        if not self._store.rename_skill(skill_id, principal_id, clean):
            return ControlResult(ok=False, reason_code="skill_rename_failed")
        self._writer.append(
            make_event(
                session_id="skills",
                turn_id=None,
                event_type="skill_renamed",
                actor="skills_service",
                payload={"skill_id": skill_id, "name": clean},
            )
        )
        return ControlResult(ok=True, data={"skill_id": skill_id, "name": clean})

    def set_active(
        self, acting_principal_id: str | None, skill_id: str, active: bool
    ) -> ControlResult:
        principal_id, err = self._human(acting_principal_id)
        if principal_id is None:
            return ControlResult(ok=False, reason_code=err)
        if not self._store.set_skill_active(skill_id, principal_id, active):
            return ControlResult(ok=False, reason_code="unknown_skill")
        self._writer.append(
            make_event(
                session_id="skills",
                turn_id=None,
                event_type="skill_activated" if active else "skill_deactivated",
                actor="skills_service",
                payload={"skill_id": skill_id, "active": active},
            )
        )
        return ControlResult(ok=True, data={"skill_id": skill_id, "active": active})

    def delete(self, acting_principal_id: str | None, skill_id: str) -> ControlResult:
        principal_id, err = self._human(acting_principal_id)
        if principal_id is None:
            return ControlResult(ok=False, reason_code=err)
        if not self._store.delete_skill(skill_id, principal_id):
            return ControlResult(ok=False, reason_code="unknown_skill")
        self._writer.append(
            make_event(
                session_id="skills",
                turn_id=None,
                event_type="skill_deleted",
                actor="skills_service",
                payload={"skill_id": skill_id},
            )
        )
        return ControlResult(ok=True, data={"skill_id": skill_id, "deleted": True})
