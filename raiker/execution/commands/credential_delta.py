from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from raiker.context.redaction import redact_text


class DeltaState(StrEnum):
    SCANNING = "scanning"
    CLEAN = "clean"
    QUARANTINED = "quarantined"
    RESOLVING = "resolving"
    MERGED = "merged"
    DISCARDED = "discarded"
    CLEANUP_FAILED = "cleanup_failed"


@dataclass(frozen=True)
class CredentialDeltaScan:
    state: DeltaState
    match_count: int
    safe_manifest_json: str
    delta_digest: str
    scan_digest: str
    scan_rule_version: str = "raiker-redaction-v1"


class CredentialDeltaScanner:
    def __init__(
        self,
        *,
        registered: Iterable[str] = (),
        max_files: int = 25_000,
        max_bytes: int = 512_000_000,
    ) -> None:
        self.registered = tuple(value.encode() for value in registered if value)
        self.max_files = max_files
        self.max_bytes = max_bytes

    def scan(self, root: Path) -> CredentialDeltaScan:
        root = root.resolve()
        if not root.is_dir() or root.is_symlink():
            raise ValueError("credential_delta_root_invalid")
        manifest: list[dict[str, object]] = []
        delta_hash = hashlib.sha256()
        scan_hash = hashlib.sha256()
        matches = 0
        files = 0
        total = 0
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            info = path.lstat()
            kind = "directory" if stat.S_ISDIR(info.st_mode) else "file"
            unsafe = stat.S_ISLNK(info.st_mode) or not (
                stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
            )
            if unsafe:
                matches += 1
                kind = "unsafe"
            name_bytes = relative.encode("utf-8", errors="replace")
            matches += self._matches(name_bytes)
            delta_hash.update(name_bytes)
            entry: dict[str, object] = {"path": relative, "kind": kind}
            if stat.S_ISREG(info.st_mode):
                files += 1
                total += info.st_size
                if files > self.max_files or total > self.max_bytes:
                    raise ValueError("credential_delta_scan_limit")
                data = path.read_bytes()
                content_digest = hashlib.sha256(data).hexdigest()
                entry.update(size=len(data), sha256=content_digest)
                delta_hash.update(data)
                matches += self._matches(data)
            manifest.append(entry)
        safe_manifest = json.dumps({"files": manifest}, sort_keys=True, separators=(",", ":"))
        scan_hash.update(delta_hash.digest())
        scan_hash.update(str(matches).encode())
        scan_hash.update(b"raiker-redaction-v1")
        return CredentialDeltaScan(
            DeltaState.QUARANTINED if matches else DeltaState.CLEAN,
            matches,
            safe_manifest,
            delta_hash.hexdigest(),
            scan_hash.hexdigest(),
        )

    def _matches(self, data: bytes) -> int:
        count = sum(data.count(secret) for secret in self.registered)
        text = data.decode("utf-8", errors="replace")
        redacted, changed = redact_text(text)
        if changed:
            placeholders = re.findall(r"\[REDACTED_[A-Z_]+\]", redacted)
            count += max(1, len(placeholders))
        return count
