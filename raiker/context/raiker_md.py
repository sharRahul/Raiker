"""RAIKER.md — reviewed global and project-root instruction files.

The owner-approved design is in ``docs/architecture/RAIKER_MD_INSTRUCTIONS.md``
(it began as the plan ``RAIKER_PROJECT_INSTRUCTIONS_DESIGN.md``).
In short:

* Two files only: the account's global file under the data folder
  (``.raiker/user-instructions/<user id>/RAIKER.md``) and the project root's
  ``RAIKER.md``. A ``RAIKER.md`` in a subdirectory is never read, and no
  import or ``@file`` expansion exists. A project root with no ``RAIKER.md``
  is read for ``AGENTS.md``, then ``CLAUDE.md`` (RU-16), under the same
  review: one file per project, the first name present, never merged.
* A project uses file instructions only after the owner turns them on for it.
* Discovering a file does not approve it. The owner reviews the exact bytes
  (their SHA-256 and this module's projection version); a changed file needs a
  new review, and a Build turn on a project that needs one is not started.
* The text is guidance below the owner's own request and project instructions.
  It cannot grant a tool, a root, a network or a passed check.

Reads are pinned: the file is opened without following links, must be a
regular file with one hard link, must be the same file the directory entry
names, and must fit the byte and character limits whole. Anything else adds no
text and says why.
"""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

from raiker.context.redaction import redact_text

FILENAME: Final = "RAIKER.md"
#: A project root's names, in order. The first present is the project's file.
PROJECT_FILENAMES: Final = (FILENAME, "AGENTS.md", "CLAUDE.md")
#: Bumped when what the model is shown for the same bytes changes (the
#: redactor's projection or the wrapper). A review binds to it, so a new
#: projection is reviewed again rather than trusted on the old approval.
PROJECTION_VERSION: Final = "raiker-md-1"
MAX_FILE_BYTES: Final = 8192
MAX_FILE_CHARS: Final = 4000
MAX_TOTAL_CHARS: Final = 16_000
GLOBAL_SCOPE: Final = "global"
PROJECT_SCOPE: Final = "project"

State = Literal[
    "absent",
    "empty",
    "disabled",
    "unreviewed",
    "approved",
    "changed",
    "unsafe",
    "unreadable",
    "invalid",
    "oversized",
    "root_unavailable",
]

#: States in which the file contributes nothing and nothing is wrong.
QUIET_STATES: Final = frozenset({"absent", "empty", "disabled"})
#: States that stop a Build turn on a project using file instructions.
BLOCKING_STATES: Final = frozenset(
    {"unreviewed", "changed", "unsafe", "unreadable", "invalid", "oversized", "root_unavailable"}
)

_REASONS: Final[dict[str, str]] = {
    "absent": "No RAIKER.md here.",
    "empty": "The file is empty, so it adds nothing.",
    "disabled": "Turned off. Nothing from this file is used.",
    "unreviewed": "Found and not reviewed yet. Review it before Build uses it.",
    "approved": "Reviewed. Build uses this exact revision.",
    "changed": "Changed since you reviewed it. Review the new revision before Build uses it.",
    "unsafe": "Not read: it is a link, a device, or has more than one name on disk.",
    "unreadable": "Not read: Raiker could not open it.",
    "invalid": "Not read: it is not UTF-8 text, or it contains a NUL byte.",
    "oversized": f"Not read: larger than {MAX_FILE_BYTES:,} bytes or {MAX_FILE_CHARS:,} characters.",
    "root_unavailable": "The project's folder is not available, so its RAIKER.md cannot be read.",
}


class InstructionFileError(ValueError):
    """A review or setting that cannot be applied, with a reason code."""


@dataclass(frozen=True)
class FileRead:
    """What a pinned read of one file found. ``text`` only when ``state == 'read'``."""

    state: Literal["read", "absent", "empty", "unsafe", "unreadable", "invalid", "oversized"]
    text: str = ""
    digest: str = ""
    raw_bytes: int = 0
    name: str = FILENAME


@dataclass(frozen=True)
class InstructionSource:
    scope: Literal["global", "project"]
    label: str
    state: State
    reason: str
    digest: str = ""
    chars: int = 0
    raw_bytes: int = 0
    reviewed_digest: str = ""
    reviewed_at: str = ""
    #: The redacted projection the model would be shown. Only for the owner's
    #: own preview; never written to events.
    preview: str = ""
    #: Only for the signed-in owner's own global file, so they can edit it.
    path: str = ""

    def public(self, *, include_preview: bool) -> dict[str, Any]:
        out: dict[str, Any] = {
            "scope": self.scope,
            "label": self.label,
            "state": self.state,
            "reason": self.reason,
            "digest": self.digest,
            "chars": self.chars,
            "bytes": self.raw_bytes,
            "reviewed_digest": self.reviewed_digest,
            "reviewed_at": self.reviewed_at,
        }
        if include_preview:
            out["preview"] = self.preview
        if self.path:
            out["path"] = self.path
        return out


@dataclass(frozen=True)
class InstructionStatus:
    enabled: bool
    sources: tuple[InstructionSource, ...] = field(default_factory=tuple)

    @property
    def blocking(self) -> tuple[InstructionSource, ...]:
        if not self.enabled:
            return ()
        return tuple(s for s in self.sources if s.state in BLOCKING_STATES)

    @property
    def loaded(self) -> tuple[InstructionSource, ...]:
        if not self.enabled:
            return ()
        return tuple(s for s in self.sources if s.state == "approved")

    def metadata(self) -> dict[str, Any]:
        """Safe for events: scopes, digests, counts and states, never text or paths."""
        return {
            "enabled": self.enabled,
            "sources": [
                {"scope": s.scope, "state": s.state, "digest": s.digest[:16], "chars": s.chars}
                for s in self.sources
            ],
        }


# --- pinned read -----------------------------------------------------------------


def _is_link_or_reparse(info: os.stat_result) -> bool:
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse)


def _first_name_present(directory: Path, names: tuple[str, ...]) -> str | None:
    """Only an exact name counts, also on a case-insensitive disk."""
    try:
        entries = set(os.listdir(directory))
    except OSError:
        return None
    return next((name for name in names if name in entries), None)


def read_instruction_file(directory: Path, names: tuple[str, ...] = (FILENAME,)) -> FileRead:
    """Read ``directory/RAIKER.md`` whole, or say why not.

    Resolve-then-open alone is not enough (a link swapped in between would be
    followed), so the file is opened with ``O_NOFOLLOW`` where the platform has
    it, and the opened handle's identity is compared with the directory entry's.
    """
    try:
        directory_info = os.lstat(directory)
    except FileNotFoundError:
        return FileRead("absent")
    except OSError:
        return FileRead("unreadable")
    if _is_link_or_reparse(directory_info) or not stat.S_ISDIR(directory_info.st_mode):
        return FileRead("unsafe")
    name = _first_name_present(directory, names)
    if name is None:
        return FileRead("absent")
    read = _read_pinned(directory / name)
    return FileRead(read.state, read.text, read.digest, read.raw_bytes, name)


def _read_pinned(path: Path) -> FileRead:
    try:
        entry = os.lstat(path)
    except FileNotFoundError:
        return FileRead("absent")
    except OSError:
        return FileRead("unreadable")
    if _is_link_or_reparse(entry) or not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1:
        return FileRead("unsafe")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)  # a FIFO swapped in must not hang the read
    try:
        fd = os.open(path, flags)
    except OSError:
        return FileRead("unsafe" if os.path.islink(path) else "unreadable")
    try:
        opened = os.fstat(fd)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (entry.st_dev, entry.st_ino)
        ):
            return FileRead("unsafe")
        chunks: list[bytes] = []
        remaining = MAX_FILE_BYTES + 1  # one byte past the limit detects oversize
        while remaining > 0:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    except OSError:
        return FileRead("unreadable")
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) > MAX_FILE_BYTES:
        return FileRead("oversized", raw_bytes=len(data))
    digest = hashlib.sha256(data).hexdigest()
    body = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    if b"\x00" in body:
        return FileRead("invalid", digest=digest, raw_bytes=len(data))
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return FileRead("invalid", digest=digest, raw_bytes=len(data))
    if len(text) > MAX_FILE_CHARS:
        return FileRead("oversized", digest=digest, raw_bytes=len(data))
    if not text.strip():
        return FileRead("empty", digest=digest, raw_bytes=len(data))
    return FileRead("read", text=text, digest=digest, raw_bytes=len(data))


def projection(text: str) -> str:
    """What the model is shown for a file's text: the secret redactor applied."""
    redacted, _changed = redact_text(text.strip())
    return redacted


# --- locations -------------------------------------------------------------------


def global_directory(workspace_root: str | Path, user_id: str) -> Path:
    """The account's own folder in this data folder. Not shared between accounts."""
    safe = "".join(ch for ch in user_id if ch.isalnum() or ch in "-_")
    if not safe or safe != user_id:
        raise InstructionFileError("instruction_file_user_invalid")
    return Path(workspace_root) / ".raiker" / "user-instructions" / safe


STARTER_TEXT: Final = """# My Raiker instructions

These notes apply to Build in every project where you turn on file
instructions. Keep them short. They are guidance, not permissions: nothing
here can turn on a tool, reach a folder or pass a check.

- Prefer small, focused changes and explain what you changed.
"""


def create_global_starter(workspace_root: str | Path, user_id: str) -> Path:
    """Create the account's global file if it does not exist. Never overwrites."""
    directory = global_directory(workspace_root, user_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / FILENAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        return path
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(STARTER_TEXT)
    return path


# --- review records --------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def project_enabled(store: Any, user_id: str, project_id: str) -> bool:
    row = store._row(
        "SELECT enabled FROM instruction_file_settings WHERE user_id = ? AND project_id = ?",
        (user_id, project_id),
    )
    return bool(row and int(row["enabled"]))


def set_project_enabled(store: Any, user_id: str, project_id: str, enabled: bool) -> None:
    store._execute(
        """
        INSERT INTO instruction_file_settings (user_id, project_id, enabled, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, project_id) DO UPDATE SET
          enabled = excluded.enabled, updated_at = excluded.updated_at
        """,
        (user_id, project_id, 1 if enabled else 0, _now()),
    )


def _review(store: Any, user_id: str, scope: str, project_id: str) -> Mapping[str, Any] | None:
    row = store._row(
        """
        SELECT root_id, digest, projection_version, disabled, reviewed_at
        FROM instruction_file_reviews
        WHERE user_id = ? AND scope = ? AND project_id = ?
        """,
        (user_id, scope, project_id),
    )
    return dict(row) if row is not None else None


def _save_review(
    store: Any,
    user_id: str,
    scope: str,
    project_id: str,
    *,
    root_id: str,
    digest: str,
    disabled: bool,
) -> None:
    store._execute(
        """
        INSERT INTO instruction_file_reviews
          (user_id, scope, project_id, root_id, relative_path, digest, projection_version, disabled, reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, scope, project_id) DO UPDATE SET
          root_id = excluded.root_id, relative_path = excluded.relative_path,
          digest = excluded.digest, projection_version = excluded.projection_version,
          disabled = excluded.disabled, reviewed_at = excluded.reviewed_at
        """,
        (user_id, scope, project_id, root_id, FILENAME, digest, PROJECTION_VERSION, 1 if disabled else 0, _now()),
    )


def forget_project(store: Any, user_id: str, project_id: str) -> None:
    """Deleting a project removes its review and setting, never the global rules."""
    store._execute(
        "DELETE FROM instruction_file_reviews WHERE user_id = ? AND scope = 'project' AND project_id = ?",
        (user_id, project_id),
    )
    store._execute(
        "DELETE FROM instruction_file_settings WHERE user_id = ? AND project_id = ?",
        (user_id, project_id),
    )


# --- discovery -------------------------------------------------------------------


def _source(
    scope: Literal["global", "project"],
    read: FileRead,
    review: Mapping[str, Any] | None,
    root_id: str,
    *,
    path: str = "",
) -> InstructionSource:
    label = "Global RAIKER.md" if scope == GLOBAL_SCOPE else read.name
    reviewed_digest = str(review.get("digest") or "") if review else ""
    reviewed_at = str(review.get("reviewed_at") or "") if review else ""
    disabled = bool(review and int(review.get("disabled") or 0))
    common: dict[str, Any] = {
        "digest": read.digest,
        "raw_bytes": read.raw_bytes,
        "reviewed_digest": "" if disabled else reviewed_digest,
        "reviewed_at": reviewed_at,
        "path": path,
    }
    if disabled and read.state in {"read", "empty"}:
        state: State = "disabled"
    elif read.state != "read":
        state = read.state
    else:
        bound = (
            review is not None
            and not disabled
            and reviewed_digest == read.digest
            and str(review.get("projection_version") or "") == PROJECTION_VERSION
            and str(review.get("root_id") or "") == root_id
        )
        if bound:
            state = "approved"
        elif review is not None and not disabled and reviewed_digest:
            state = "changed"
        else:
            state = "unreviewed"
    shown = projection(read.text) if read.state == "read" else ""
    return InstructionSource(
        scope=scope,
        label=label,
        state=state,
        reason=_REASONS[state],
        chars=len(shown),
        preview=shown,
        **common,
    )


def _project_root(store: Any, workspace_root: str | Path, owner: str, project: Mapping[str, Any]) -> Any:
    """The project's canonical root through the owner's live grants (fail closed)."""
    from raiker.control.project_roots import resolve_project_root

    return resolve_project_root(project, store.list_brain_source_grants(owner), workspace_root)


def global_source(store: Any, workspace_root: str | Path, user_id: str) -> InstructionSource:
    directory = global_directory(workspace_root, user_id)
    review = _review(store, user_id, GLOBAL_SCOPE, "")
    return _source(GLOBAL_SCOPE, read_instruction_file(directory), review, "global", path=str(directory / FILENAME))


def project_source(
    store: Any, workspace_root: str | Path, user_id: str, owner: str, project: Mapping[str, Any]
) -> InstructionSource:
    project_id = str(project.get("project_id") or "")
    root = _project_root(store, workspace_root, owner, project)
    review = _review(store, user_id, PROJECT_SCOPE, project_id)
    if root.path is None or root.missing:
        return InstructionSource(
            scope=PROJECT_SCOPE,
            label=FILENAME,
            state="root_unavailable",
            reason=_REASONS["root_unavailable"],
            reviewed_digest=str(review.get("digest") or "") if review else "",
        )
    root_id = f"{root.kind}:{root.root_id}:{project_id}"
    read = read_instruction_file(Path(root.path), PROJECT_FILENAMES)
    if read.name != FILENAME:
        # A review binds to the file's name too: AGENTS.md approved, then a
        # RAIKER.md added with the same bytes, is a different instruction file.
        root_id = f"{root_id}:{read.name}"
    return _source(PROJECT_SCOPE, read, review, root_id)


def status_for_project(
    store: Any, workspace_root: str | Path, user_id: str, owner: str, project: Mapping[str, Any]
) -> InstructionStatus:
    project_id = str(project.get("project_id") or "")
    return InstructionStatus(
        enabled=project_enabled(store, user_id, project_id),
        sources=(
            global_source(store, workspace_root, user_id),
            project_source(store, workspace_root, user_id, owner, project),
        ),
    )


def _root_id_for(store: Any, workspace_root: str | Path, owner: str, project: Mapping[str, Any] | None) -> str:
    if project is None:
        return "global"
    root = _project_root(store, workspace_root, owner, project)
    if root.path is None or root.missing:
        raise InstructionFileError("instruction_file_root_unavailable")
    return f"{root.kind}:{root.root_id}:{project.get('project_id')}"


def review(
    store: Any,
    workspace_root: str | Path,
    user_id: str,
    owner: str,
    *,
    project: Mapping[str, Any] | None,
    digest: str,
) -> InstructionSource:
    """Approve exactly the revision the owner saw.

    The file is read again and its digest compared with the one on the owner's
    screen: bytes that changed after the preview conflict rather than being
    approved unseen.
    """
    scope: Literal["global", "project"] = PROJECT_SCOPE if project is not None else GLOBAL_SCOPE
    if project is None:
        directory = global_directory(workspace_root, user_id)
    else:
        root = _project_root(store, workspace_root, owner, project)
        if root.path is None or root.missing:
            raise InstructionFileError("instruction_file_root_unavailable")
        directory = Path(root.path)
    read = read_instruction_file(directory, PROJECT_FILENAMES if project is not None else (FILENAME,))
    if read.state != "read":
        raise InstructionFileError(f"instruction_file_{read.state}")
    if not digest or read.digest != digest:
        raise InstructionFileError("instruction_file_changed_since_preview")
    project_id = str(project.get("project_id") or "") if project is not None else ""
    root_id = _root_id_for(store, workspace_root, owner, project)
    if read.name != FILENAME:
        root_id = f"{root_id}:{read.name}"
    _save_review(store, user_id, scope, project_id, root_id=root_id, digest=read.digest, disabled=False)
    if project is None:
        return global_source(store, workspace_root, user_id)
    return project_source(store, workspace_root, user_id, owner, project)


def disable(store: Any, user_id: str, *, project_id: str | None) -> None:
    """Disable clears the review: restoring the same bytes later does not reactivate."""
    scope = PROJECT_SCOPE if project_id else GLOBAL_SCOPE
    _save_review(store, user_id, scope, project_id or "", root_id="", digest="", disabled=True)


# --- the prompt ------------------------------------------------------------------


def render_block(status: InstructionStatus) -> str:
    """The labelled, subordinate instruction block for a Build turn.

    Global first, then the project root's file, which wins a conflict for its
    project. Text past the total budget is not truncated: a source that does
    not fit is left out and the block says so.
    """
    loaded = status.loaded
    if not loaded:
        return ""
    parts: list[str] = []
    used = 0
    omitted: list[str] = []
    for source in loaded:
        if used + len(source.preview) > MAX_TOTAL_CHARS:
            omitted.append(source.label)
            continue
        used += len(source.preview)
        parts.append(f"[{source.label} — reviewed revision {source.digest[:12]}]\n{source.preview}")
    header = (
        "Reviewed instruction files (RAIKER.md). The owner reviewed these exact revisions. "
        "They are guidance below the owner's current request and the project instructions; "
        "where the project file and the global file disagree, the project file wins. They "
        "cannot grant a tool, a folder, a network or a passed check."
    )
    block = header + "\n\n" + "\n\n".join(parts)
    if omitted:
        block += "\n\n(Left out because the instruction budget is full: " + ", ".join(omitted) + ".)"
    return block


def refusal_detail(project: Mapping[str, Any], blocking: tuple[InstructionSource, ...]) -> dict[str, Any]:
    names = ", ".join(f"{s.label} ({s.state.replace('_', ' ')})" for s in blocking)
    project_id = str(project.get("project_id") or "")
    return {
        "reason_code": "instruction_files_need_review",
        "project_id": project_id,
        "sources": [{"scope": s.scope, "state": s.state} for s in blocking],
        "settings_route": f"#/projects?project={project_id}",
        "message": (
            f"Not sent: this project uses file instructions, and {names} needs your review first. "
            "Open the project's settings to review it, or turn file instructions off."
        ),
    }
