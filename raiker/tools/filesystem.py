from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any


class FilesystemSafetyError(ValueError):
    pass


def resolve_workspace_path(workspace_root: str | Path, requested_path: str | Path) -> Path:
    root = Path(workspace_root).resolve()
    candidate = Path(requested_path)
    resolved = (
        candidate.resolve(strict=False)
        if candidate.is_absolute()
        else (root / candidate).resolve(strict=False)
    )
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FilesystemSafetyError("outside_workspace") from exc
    return resolved


def _is_binary_bytes(data: bytes) -> bool:
    return b"\x00" in data


def read_file(
    workspace_root: str | Path, path: str | Path, *, max_bytes: int = 200_000
) -> dict[str, Any]:
    resolved = resolve_workspace_path(workspace_root, path)
    if not resolved.exists():
        return {"status": "failed", "error": {"type": "not_found", "path": str(path)}}
    if not resolved.is_file():
        return {"status": "failed", "error": {"type": "not_file", "path": str(path)}}
    data = resolved.read_bytes()[: max_bytes + 1]
    if _is_binary_bytes(data):
        return {"status": "failed", "error": {"type": "binary_file", "path": str(path)}}
    try:
        text = data[:max_bytes].decode("utf-8")
    except UnicodeDecodeError:
        return {"status": "failed", "error": {"type": "binary_file", "path": str(path)}}
    return {
        "status": "success",
        "path": str(resolved.relative_to(Path(workspace_root).resolve())),
        "text": text,
        "truncated": len(data) > max_bytes,
    }


def list_directory(workspace_root: str | Path, path: str | Path = ".") -> dict[str, Any]:
    resolved = resolve_workspace_path(workspace_root, path)
    if not resolved.exists():
        return {"status": "failed", "error": {"type": "not_found", "path": str(path)}}
    if not resolved.is_dir():
        return {"status": "failed", "error": {"type": "not_directory", "path": str(path)}}
    entries = sorted(child.name + ("/" if child.is_dir() else "") for child in resolved.iterdir())
    return {"status": "success", "path": str(path), "entries": entries}


def glob_paths(
    workspace_root: str | Path, pattern: str, *, max_results: int = 100
) -> dict[str, Any]:
    if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
        raise FilesystemSafetyError("outside_workspace")
    root = Path(workspace_root).resolve()
    matches = sorted(
        str(path.relative_to(root)) + ("/" if path.is_dir() else "")
        for path in root.glob(pattern)
        if resolve_workspace_path(root, path).exists()
    )
    return {
        "status": "success",
        "matches": matches[:max_results],
        "truncated": len(matches) > max_results,
    }


def is_text_file(path: Path, sample_size: int = 4096) -> bool:
    try:
        sample = path.read_bytes()[:sample_size]
    except OSError:
        return False
    if _is_binary_bytes(sample):
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def grep_files(
    workspace_root: str | Path,
    query: str,
    path: str | Path = ".",
    *,
    include: str = "*",
    max_results: int = 100,
) -> dict[str, Any]:
    root = Path(workspace_root).resolve()
    base = resolve_workspace_path(root, path)
    if not base.exists():
        return {"status": "failed", "error": {"type": "not_found", "path": str(path)}}
    files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
    results: list[dict[str, Any]] = []
    for file_path in sorted(files):
        if not fnmatch.fnmatch(file_path.name, include) or not is_text_file(file_path):
            continue
        for line_number, line in enumerate(
            file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            if query in line:
                results.append(
                    {
                        "path": str(file_path.relative_to(root)),
                        "line": line_number,
                        "text": line[:500],
                    }
                )
                if len(results) >= max_results:
                    return {"status": "success", "matches": results, "truncated": True}
    return {"status": "success", "matches": results, "truncated": False}


def stat_path(workspace_root: str | Path, path: str | Path) -> dict[str, Any]:
    resolved = resolve_workspace_path(workspace_root, path)
    if not resolved.exists():
        return {"status": "failed", "error": {"type": "not_found", "path": str(path)}}
    return {
        "status": "success",
        "path": str(resolved.relative_to(Path(workspace_root).resolve())),
        "is_file": resolved.is_file(),
        "is_dir": resolved.is_dir(),
        "size_bytes": resolved.stat().st_size,
    }


def diff_files(
    workspace_root: str | Path,
    before_path: str | Path,
    after_path: str | Path,
    *,
    max_lines: int = 200,
) -> dict[str, Any]:
    import difflib

    before = read_file(workspace_root, before_path)
    after = read_file(workspace_root, after_path)
    if before["status"] != "success":
        return {"status": "failed", "error": before.get("error")}
    if after["status"] != "success":
        return {"status": "failed", "error": after.get("error")}
    lines = list(
        difflib.unified_diff(
            str(before["text"]).splitlines(),
            str(after["text"]).splitlines(),
            fromfile=str(before_path),
            tofile=str(after_path),
            lineterm="",
        )
    )
    return {"status": "success", "diff": lines[:max_lines], "truncated": len(lines) > max_lines}


def proposed_write_snapshot(
    workspace_root: str | Path, path: str | Path, new_text: str
) -> dict[str, Any]:
    resolved = resolve_workspace_path(workspace_root, path)
    before = (
        resolved.read_text(encoding="utf-8")
        if resolved.exists() and resolved.is_file() and is_text_file(resolved)
        else None
    )
    return {
        "status": "proposal",
        "path": str(resolved.relative_to(Path(workspace_root).resolve())),
        "before_snapshot": before,
        "proposed_text": new_text,
        "requires_approval": True,
    }
