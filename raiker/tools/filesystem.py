from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class FilesystemSafetyError(ValueError):
    pass


# Top-level workspace directories a governed file mutation may never target.
#
# Confinement to the workspace is not sufficient once an approved write really
# executes (BUG-06): the workspace *contains* the substrate that makes owner
# authority meaningful. `.raiker/` holds the encrypted store and its audit log,
# the vault key, the hook definitions (which run commands), and the MCP server
# scripts; `.git/` holds hooks that run on the next commit. A write to either is
# not "the owner's legitimate choice" being blocked — it is the agent rewriting
# the machinery that records and constrains it, so this is one of the last-resort
# hard preventions HANDOFF reserves.
#
# Reads are untouched: the agent may still read anything inside the workspace.
PROTECTED_WORKSPACE_DIRS: frozenset[str] = frozenset({".raiker", ".git"})


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


def resolve_writable_workspace_path(
    workspace_root: str | Path, requested_path: str | Path
) -> Path:
    """Resolve *requested_path* for **writing**, refusing protected directories.

    Every mutating filesystem path goes through here rather than through
    :func:`resolve_workspace_path`, so confinement and the protected-directory
    refusal can never drift apart.
    """
    root = Path(workspace_root).resolve()
    resolved = resolve_workspace_path(root, requested_path)
    if resolved == root:
        raise FilesystemSafetyError("protected_workspace_path")
    parts = resolved.relative_to(root).parts
    if parts and parts[0] in PROTECTED_WORKSPACE_DIRS:
        raise FilesystemSafetyError("protected_workspace_path")
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
    # Refused here as well as at execution time, so a proposal the runtime could
    # never carry out is rejected while the model can still react to it, rather
    # than sitting in the Approvals inbox looking actionable.
    resolved = resolve_writable_workspace_path(workspace_root, path)
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


def write_file_content(workspace_root: str | Path, path: str | Path, text: str) -> dict[str, Any]:
    resolved = resolve_writable_workspace_path(workspace_root, path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(text, encoding="utf-8")
    return {
        "status": "success",
        "path": str(resolved.relative_to(Path(workspace_root).resolve())),
        "size_bytes": resolved.stat().st_size,
    }


def _failure(error_type: str, **details: Any) -> dict[str, Any]:
    rejected_hunks = details.pop("rejected_hunks", None)
    result: dict[str, Any] = {
        "status": "failed",
        "error": {"type": error_type, **details},
    }
    if rejected_hunks is not None:
        result["rejected_hunks"] = rejected_hunks
    return result


def _existing_text_target(
    workspace_root: str | Path, path: str | Path
) -> tuple[Path, str] | dict[str, Any]:
    resolved = resolve_writable_workspace_path(workspace_root, path)
    if not resolved.exists() or not resolved.is_file():
        return _failure("not_found")
    if not is_text_file(resolved):
        return _failure("binary_file")
    try:
        return resolved, resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return _failure("binary_file")
    except OSError as exc:
        return _failure("read_failed", message=str(exc))


def _relative_path(workspace_root: str | Path, resolved: Path) -> str:
    return str(resolved.relative_to(Path(workspace_root).resolve()))


def _same_line(left: str, right: str) -> bool:
    """Two source lines that differ only in whitespace.

    Trailing whitespace and the indentation *style* are the two things a model
    reliably gets wrong when it quotes a line back: an editor stripped the
    trailing space, or the file uses tabs where the model wrote spaces. Neither
    changes which line is meant. Interior spacing is **not** normalized — `a + b`
    and `a+b` are different text and must stay a mismatch.
    """
    if left == right:
        return True
    left, right = left.rstrip(), right.rstrip()
    return left == right or (
        left.lstrip() == right.lstrip()
        and left.lstrip() != ""
        and left[: len(left) - len(left.lstrip())].replace("\t", " ").strip() == ""
        and right[: len(right) - len(right.lstrip())].replace("\t", " ").strip() == ""
    )


def _whitespace_tolerant_spans(text: str, old_text: str) -> list[tuple[int, int]]:
    """Character spans of *text* matching *old_text* up to line whitespace.

    Whole lines only. A fragment inside a line never reaches here, because the
    exact search already ran and this comparison is line-for-line — so relaxing
    whitespace can never make a *narrower* match than the strict one.
    """
    needle = old_text.splitlines()
    if not needle:
        return []
    lines = text.splitlines(keepends=True)
    offsets, position = [], 0
    for line in lines:
        offsets.append(position)
        position += len(line)
    offsets.append(position)
    stripped = [line.rstrip("\r\n") for line in lines]
    width = len(needle)
    return [
        (offsets[index], offsets[index + width])
        for index in range(len(lines) - width + 1)
        if all(_same_line(stripped[index + offset], needle[offset]) for offset in range(width))
    ]


def _unique_match(text: str, old_text: str) -> tuple[int, int] | dict[str, Any]:
    """The one span *old_text* identifies, as ``(start, end)`` character offsets.

    Exact first. When that finds nothing, the same search runs again ignoring
    trailing whitespace and indentation style — which is the difference between
    an edit failing because the model mis-transcribed a tab and an edit failing
    because it named the wrong code. What does **not** relax is uniqueness: a
    relaxed search matching two places is still refused, so the tolerance can
    never make an edit land somewhere it was not meant to.
    """
    if not old_text:
        return _failure("old_text_empty")
    first = text.find(old_text)
    if first >= 0:
        if text.find(old_text, first + 1) >= 0:
            return _failure("old_text_not_unique")
        return first, first + len(old_text)
    spans = _whitespace_tolerant_spans(text, old_text)
    if not spans:
        return _failure("old_text_not_found")
    if len(spans) > 1:
        return _failure("old_text_not_unique")
    return spans[0]


def _replace_candidate(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str
) -> tuple[Path, str, str] | dict[str, Any]:
    target = _existing_text_target(workspace_root, path)
    if isinstance(target, dict):
        return target
    resolved, before = target
    match = _unique_match(before, old_text)
    if isinstance(match, dict):
        return match
    start, end = match
    replacement = new_text
    if before[start:end] != old_text:
        # The match was whitespace-tolerant, so the file and the quote disagree
        # about indentation. The file is right about its own indentation — an
        # edit that adopted the quote's would silently de-indent a method into
        # module scope. Shift the replacement by the difference instead.
        replacement = _reindented(replacement, _indent_delta(before[start:end], old_text))
        # A tolerant span covers whole lines, so the replacement has to end the
        # way the text it replaces did or the following line joins it.
        if before[start:end].endswith("\n") and not replacement.endswith("\n"):
            replacement += "\n"
    return resolved, before, before[:start] + replacement + before[end:]


def _leading_whitespace(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _indent_delta(matched: str, quoted: str) -> str:
    """The indentation the file has and the quote lacks, if it is a clean prefix."""
    matched_lines = [line for line in matched.splitlines() if line.strip()]
    quoted_lines = [line for line in quoted.splitlines() if line.strip()]
    if not matched_lines or not quoted_lines:
        return ""
    file_indent = _leading_whitespace(matched_lines[0])
    quote_indent = _leading_whitespace(quoted_lines[0])
    return file_indent[len(quote_indent):] if file_indent.startswith(quote_indent) else ""


def _reindented(text: str, delta: str) -> str:
    if not delta:
        return text
    return "".join(
        delta + line if line.strip() else line for line in text.splitlines(keepends=True)
    )


_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")


@dataclass(frozen=True)
class _PatchHunk:
    old_start: int
    old_lines: list[str]
    new_lines: list[str]


@dataclass(frozen=True)
class _PatchCandidate:
    path: Path
    before: str
    proposed_text: str
    operation: str = "update"


def _normalized_patch_path(value: str) -> str:
    path = value.split("\t", 1)[0].strip().replace("\\", "/")
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def _parse_unified_patch(
    patch: str, expected_path: str
) -> tuple[str, list[_PatchHunk]] | dict[str, Any]:
    lines = patch.splitlines(keepends=True)
    if len(lines) < 3 or not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
        return _failure("malformed_patch", message="expected unified diff file headers")
    old_path = _normalized_patch_path(lines[0][4:])
    new_path = _normalized_patch_path(lines[1][4:])
    operation = "create" if old_path == "/dev/null" else "delete" if new_path == "/dev/null" else "update"
    target_path = new_path if operation == "create" else old_path
    if target_path != expected_path or (operation == "update" and new_path != expected_path):
        return _failure("patch_path_mismatch", old_path=old_path, new_path=new_path)

    hunks: list[_PatchHunk] = []
    index = 2
    while index < len(lines):
        header = lines[index].rstrip("\r\n")
        match = _HUNK_HEADER.match(header)
        if match is None:
            return _failure("malformed_patch", message=f"invalid hunk header at line {index + 1}")
        old_start = int(match.group(1))
        old_count = int(match.group(2) or "1")
        new_count = int(match.group(4) or "1")
        index += 1
        old_lines: list[str] = []
        new_lines: list[str] = []
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if line.startswith(("--- ", "+++ ")):
                return _failure("malformed_patch", message="multiple file targets are not supported")
            if line.startswith("\\ No newline at end of file"):
                target = old_lines if index > 0 and lines[index - 1].startswith("-") else new_lines
                if target:
                    target[-1] = target[-1].rstrip("\r\n")
                index += 1
                continue
            if not line or line[0] not in {" ", "+", "-"}:
                return _failure("malformed_patch", message=f"invalid hunk line at line {index + 1}")
            if line[0] in {" ", "-"}:
                old_lines.append(line[1:])
            if line[0] in {" ", "+"}:
                new_lines.append(line[1:])
            index += 1
        if len(old_lines) != old_count or len(new_lines) != new_count:
            return _failure("malformed_patch", message="invalid hunk line counts")
        hunks.append(_PatchHunk(old_start=old_start, old_lines=old_lines, new_lines=new_lines))
    return (operation, hunks) if hunks else _failure("malformed_patch", message="patch contains no hunks")


def _matching_starts(lines: list[str], needle: list[str]) -> list[int]:
    """Line indexes where a hunk's context sits.

    Exact first, then the same whitespace tolerance ``_unique_match`` applies:
    trailing whitespace and indentation style may differ, nothing else may. The
    relaxed pass runs only when the exact one found nothing, so a diff that
    already matches is unaffected, and ``_patch_candidate``'s ambiguity check
    still refuses a context that now matches two places.
    """
    width = len(needle)
    exact = [
        index for index in range(len(lines) - width + 1) if lines[index:index + width] == needle
    ]
    if exact:
        return exact
    return [
        index
        for index in range(len(lines) - width + 1)
        if all(
            _same_line(lines[index + offset].rstrip("\r\n"), needle[offset].rstrip("\r\n"))
            for offset in range(width)
        )
    ]


def _patch_candidate(workspace_root: str | Path, path: str | Path, patch: str) -> _PatchCandidate | dict[str, Any]:
    resolved = resolve_writable_workspace_path(workspace_root, path)
    expected_path = _relative_path(workspace_root, resolved).replace("\\", "/")
    parsed = _parse_unified_patch(patch, expected_path)
    if isinstance(parsed, dict):
        return parsed
    operation, hunks = parsed
    if operation == "create":
        if resolved.exists():
            return _failure("target_exists")
        before = ""
    else:
        target = _existing_text_target(workspace_root, path)
        if isinstance(target, dict):
            return target
        resolved, before = target

    candidate = before.splitlines(keepends=True)
    offset = 0
    for hunk_number, hunk in enumerate(hunks, start=1):
        expected = max(0, hunk.old_start - 1 + offset)
        if not hunk.old_lines:
            start = min(expected, len(candidate))
        else:
            starts = _matching_starts(candidate, hunk.old_lines)
            if not starts:
                return _failure("hunk_context_mismatch", rejected_hunks=[hunk_number])
            distances = [(abs(item - expected), item) for item in starts]
            nearest = min(distance for distance, _item in distances)
            nearest_starts = [item for distance, item in distances if distance == nearest]
            if len(nearest_starts) > 1:
                return _failure("hunk_context_not_unique", rejected_hunks=[hunk_number])
            start = nearest_starts[0]
        candidate[start:start + len(hunk.old_lines)] = hunk.new_lines
        offset += len(hunk.new_lines) - len(hunk.old_lines)
    proposed = "".join(candidate)
    if operation == "delete" and proposed:
        return _failure("delete_patch_not_empty")
    return _PatchCandidate(resolved, before, proposed, operation)


def _split_unified_patch(patch: str) -> list[str] | dict[str, Any]:
    """Split a git-style unified diff into file sections without interpreting hunks."""
    lines = patch.splitlines(keepends=True)
    starts = [
        index for index in range(len(lines) - 1)
        if lines[index].startswith("--- ") and lines[index + 1].startswith("+++ ")
    ]
    if not starts or starts[0] != 0:
        return _failure("malformed_patch", message="expected unified diff file headers")
    return [
        "".join(lines[start:end])
        for start, end in zip(starts, starts[1:] + [len(lines)], strict=True)
    ]


def patch_target_paths(patch: str) -> list[str]:
    """Return normalized targets from a syntactically sectioned unified diff."""
    sections = _split_unified_patch(patch)
    if isinstance(sections, dict):
        return []
    targets: list[str] = []
    for section in sections:
        headers = section.splitlines()
        old_path = _normalized_patch_path(headers[0][4:])
        new_path = _normalized_patch_path(headers[1][4:])
        targets.append(new_path if old_path == "/dev/null" else old_path)
    return targets


def _patch_candidates(
    workspace_root: str | Path, path: str | Path | None, patch: str
) -> list[_PatchCandidate] | dict[str, Any]:
    expected: str | None = None
    if path:
        expected = _relative_path(
            workspace_root, resolve_writable_workspace_path(workspace_root, path)
        ).replace("\\", "/")
    sections = _split_unified_patch(patch)
    if isinstance(sections, dict):
        return sections
    candidates: list[_PatchCandidate] = []
    seen: set[Path] = set()
    for index, section in enumerate(sections):
        header = section.splitlines()
        old_path = _normalized_patch_path(header[0][4:])
        new_path = _normalized_patch_path(header[1][4:])
        target = new_path if old_path == "/dev/null" else old_path
        if index == 0 and expected is not None and target != expected:
            return _failure("patch_path_mismatch", old_path=old_path, new_path=new_path)
        candidate = _patch_candidate(workspace_root, target, section)
        if isinstance(candidate, dict):
            candidate.setdefault("error", {})["path"] = target
            return candidate
        if candidate.path in seen:
            return _failure("duplicate_patch_target", path=target)
        seen.add(candidate.path)
        candidates.append(candidate)
    return candidates


def _proposal_from_candidate(
    workspace_root: str | Path, candidate: tuple[Path, str, str] | _PatchCandidate | dict[str, Any]
) -> dict[str, Any]:
    if isinstance(candidate, dict):
        return candidate
    if isinstance(candidate, _PatchCandidate):
        resolved, before, proposed_text = candidate.path, candidate.before, candidate.proposed_text
        operation = candidate.operation
    else:
        resolved, before, proposed_text = candidate
        operation = "update"
    return {
        "status": "proposal",
        "path": _relative_path(workspace_root, resolved),
        "before_snapshot": before,
        "proposed_text": proposed_text,
        "operation": operation,
        "requires_approval": True,
    }


def proposed_edit_snapshot(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str
) -> dict[str, Any]:
    return _proposal_from_candidate(
        workspace_root, _replace_candidate(workspace_root, path, old_text, new_text)
    )


def proposed_patch_snapshot(
    workspace_root: str | Path, path: str | Path | None, patch: str
) -> dict[str, Any]:
    candidates = _patch_candidates(workspace_root, path, patch)
    if isinstance(candidates, dict):
        return candidates
    changes = [
        {
            "path": _relative_path(workspace_root, item.path),
            "before_snapshot": item.before,
            "proposed_text": item.proposed_text,
            "operation": item.operation,
        }
        for item in candidates
    ]
    first = changes[0]
    return {
        "status": "proposal",
        **first,
        "paths": [item["path"] for item in changes],
        "changes": changes,
        "requires_approval": True,
    }


def _write_candidate(
    workspace_root: str | Path, candidate: tuple[Path, str, str] | _PatchCandidate | dict[str, Any]
) -> dict[str, Any]:
    if isinstance(candidate, dict):
        return candidate
    if isinstance(candidate, _PatchCandidate):
        resolved, proposed_text, operation = candidate.path, candidate.proposed_text, candidate.operation
    else:
        resolved, _before, proposed_text = candidate
        operation = "update"
    if operation == "delete":
        resolved.unlink()
        size_bytes = 0
    else:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(proposed_text, encoding="utf-8")
        size_bytes = resolved.stat().st_size
    return {
        "status": "success",
        "path": _relative_path(workspace_root, resolved),
        "size_bytes": size_bytes,
        "operation": operation,
    }


def replace_text_content(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str
) -> dict[str, Any]:
    return _write_candidate(
        workspace_root, _replace_candidate(workspace_root, path, old_text, new_text)
    )


def edit_file_content(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str
) -> dict[str, Any]:
    return replace_text_content(workspace_root, path, old_text, new_text)


def apply_patch_content(
    workspace_root: str | Path, path: str | Path | None, patch: str
) -> dict[str, Any]:
    """Apply every file section as one transaction, rolling back on any write failure."""
    candidates = _patch_candidates(workspace_root, path, patch)
    if isinstance(candidates, dict):
        return candidates
    completed: list[_PatchCandidate] = []
    try:
        for candidate in candidates:
            result = _write_candidate(workspace_root, candidate)
            if result["status"] != "success":
                raise OSError(str(result.get("error", {})))
            completed.append(candidate)
    except Exception as exc:
        for candidate in reversed(completed):
            if candidate.operation == "create":
                candidate.path.unlink(missing_ok=True)
            else:
                candidate.path.parent.mkdir(parents=True, exist_ok=True)
                candidate.path.write_text(candidate.before, encoding="utf-8")
        return _failure("transaction_write_failed", message=str(exc))
    changes = [
        {
            "path": _relative_path(workspace_root, item.path),
            "size_bytes": 0 if item.operation == "delete" else item.path.stat().st_size,
            "operation": item.operation,
        }
        for item in candidates
    ]
    return {
        "status": "success",
        "path": changes[0]["path"],
        "paths": [item["path"] for item in changes],
        "size_bytes": sum(
            0 if item.operation == "delete" else item.path.stat().st_size
            for item in candidates
        ),
        "operation": changes[0]["operation"],
        "changes": changes,
    }
