from __future__ import annotations

import fnmatch
import json
import re
from collections.abc import Callable, Mapping
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


def resolve_workspace_path(
    workspace_root: str | Path, requested_path: str | Path, *, authority: Any = None
) -> Path:
    """Resolve *requested_path* for **reading**, refusing anything out of scope.

    ``authority`` carries the roots this scope may reach. Omitted -- which is
    every caller that has not been given a project's roots -- it is built
    workspace-only, so the answer is exactly what it was before roots existed.
    """
    return _authority_for(workspace_root, authority).resolve_read(requested_path).path


def resolve_writable_workspace_path(
    workspace_root: str | Path, requested_path: str | Path, *, authority: Any = None
) -> Path:
    """Resolve *requested_path* for **writing**, refusing protected directories.

    Every mutating filesystem path goes through here rather than through
    :func:`resolve_workspace_path`, so confinement and the protected-directory
    refusal can never drift apart.
    """
    return _authority_for(workspace_root, authority).resolve_write(requested_path).path


def _authority_for(workspace_root: str | Path, authority: Any) -> Any:
    """The caller's authority, or a workspace-only one built on the spot.

    Imported lazily because ``path_authority`` reads this module's protected
    directory set, and importing it at module scope would be circular.
    """
    if authority is not None:
        return authority
    from raiker.tools.path_authority import PathAuthority

    return PathAuthority(workspace_root)


def _is_binary_bytes(data: bytes) -> bool:
    return b"\x00" in data


#: TOOL-02 — the largest file `read_file` will open to serve a line range.
MAX_LINE_RANGE_SOURCE_BYTES = 5_000_000
#: TOOL-02 — the most PDF pages one `read_file` call extracts.
MAX_READ_PDF_PAGES = 20
#: The largest PDF `read_file` will open; the reader holds the whole file.
MAX_READ_PDF_BYTES = 50_000_000
_PAGE_SPEC = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$")


def _page_range(spec: str) -> tuple[int, int] | None:
    match = _PAGE_SPEC.match(spec)
    if not match:
        return None
    first = int(match.group(1))
    last = int(match.group(2) or first)
    if first < 1 or last < first:
        return None
    return first, last


def _read_pdf(
    workspace_root: str | Path, resolved: Path, pages: str | None, *, max_bytes: int,
    authority: Any,
) -> dict[str, Any]:
    """Text of a workspace PDF's pages, extracted locally (TOOL-02).

    Uses the same pypdf reader uploaded attachments use; nothing leaves the
    machine. At most :data:`MAX_READ_PDF_PAGES` pages per call, so a long PDF
    is read in parts rather than folded into the context whole.
    """
    import io

    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError:
        return _failure("pdf_extraction_unavailable")
    if resolved.stat().st_size > MAX_READ_PDF_BYTES:
        return _failure("pdf_too_large", limit=MAX_READ_PDF_BYTES)
    try:
        reader = PdfReader(io.BytesIO(resolved.read_bytes()))
        page_count = len(reader.pages)
    except (PyPdfError, ValueError, OSError):
        return _failure("pdf_unreadable")
    if pages:
        span = _page_range(pages)
        if span is None:
            return _failure("pages_invalid")
        first, last = span
    else:
        first, last = 1, min(page_count, MAX_READ_PDF_PAGES)
    if first > page_count:
        return _failure("pages_out_of_range", page_count=page_count)
    if last - first + 1 > MAX_READ_PDF_PAGES:
        return _failure("pages_too_many", limit=MAX_READ_PDF_PAGES)
    last = min(last, page_count)
    parts: list[str] = []
    for number in range(first, last + 1):
        try:
            text = reader.pages[number - 1].extract_text() or ""
        except Exception:  # noqa: BLE001 — one bad page must not abort the read
            text = ""
        parts.append(f"--- Page {number} ---\n{text}")
    joined = "\n".join(parts)
    return {
        "status": "success",
        "path": _relative_path(workspace_root, resolved, authority=authority),
        "text": joined[:max_bytes],
        "truncated": len(joined) > max_bytes or (last < page_count and not pages),
        "pages": f"{first}-{last}",
        "page_count": page_count,
    }


def _notebook_cells_text(text: str) -> str | None:
    """TOOL-03 — a notebook as its numbered cells, so an edit can name one.

    Outputs are summarised by type rather than shown: they are the bulk of most
    notebooks and nothing an edit changes. ``None`` when the file is not a
    notebook after all, and the caller reads it as text.
    """
    try:
        notebook = json.loads(text)
    except json.JSONDecodeError:
        return None
    cells = notebook.get("cells") if isinstance(notebook, dict) else None
    if not isinstance(cells, list):
        return None
    parts: list[str] = [f"Jupyter notebook, {len(cells)} cells. Edit one with edit_file and cell."]
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            continue
        raw = cell.get("source", "")
        source = "".join(raw) if isinstance(raw, list) else str(raw)
        label = f"[cell {index} · {cell.get('cell_type', 'unknown')}" + (f" · id {cell['id']}" if cell.get("id") else "") + "]"
        raw_outputs = cell.get("outputs")
        outputs: list[Any] = raw_outputs if isinstance(raw_outputs, list) else []
        kinds = sorted({str(item.get("output_type", "output")) for item in outputs if isinstance(item, dict)})
        tail = f"\n(outputs: {len(outputs)} — {', '.join(kinds)})" if outputs else ""
        parts.append(f"{label}\n{source}{tail}")
    return "\n\n".join(parts)


def read_file(
    workspace_root: str | Path, path: str | Path, *, max_bytes: int = 200_000,
    offset: int | None = None, limit: int | None = None, pages: str | None = None,
    authority: Any = None,
) -> dict[str, Any]:
    """Read a workspace file: UTF-8 text, a line range of one, or a PDF's pages.

    TOOL-02 added ``offset`` (first line, 1-based) and ``limit`` (number of
    lines) for reading a long file in parts, and PDF text by ``pages``
    (``"3"`` or ``"1-5"``). Without them a call returns what it always did.
    """
    resolved = resolve_workspace_path(workspace_root, path, authority=authority)
    if not resolved.exists():
        return {"status": "failed", "error": {"type": "not_found", "path": str(path)}}
    if not resolved.is_file():
        return {"status": "failed", "error": {"type": "not_file", "path": str(path)}}
    with resolved.open("rb") as handle:
        head = handle.read(5)
    if head == b"%PDF-":
        return _read_pdf(workspace_root, resolved, pages, max_bytes=max_bytes, authority=authority)
    if pages:
        return _failure("pages_only_for_pdf")
    ranged = offset is not None or limit is not None
    if ranged and resolved.stat().st_size > MAX_LINE_RANGE_SOURCE_BYTES:
        return _failure("file_too_large_for_line_range", limit=MAX_LINE_RANGE_SOURCE_BYTES)
    data = resolved.read_bytes() if ranged else resolved.read_bytes()[: max_bytes + 1]
    if _is_binary_bytes(data):
        return {"status": "failed", "error": {"type": "binary_file", "path": str(path)}}
    try:
        text = (data if ranged else data[:max_bytes]).decode("utf-8")
    except UnicodeDecodeError:
        return {"status": "failed", "error": {"type": "binary_file", "path": str(path)}}
    relative = _relative_path(workspace_root, resolved, authority=authority)
    if not ranged and resolved.suffix.lower() == ".ipynb" and len(data) <= max_bytes:
        cells = _notebook_cells_text(text)
        if cells is not None:
            return {"status": "success", "path": relative, "text": cells, "truncated": False, "notebook": True}
    if not ranged:
        return {"status": "success", "path": relative, "text": text, "truncated": len(data) > max_bytes}
    lines = text.splitlines(keepends=True)
    start = max(1, offset or 1)
    if start > max(len(lines), 1):
        return _failure("offset_out_of_range", line_count=len(lines))
    end = len(lines) if limit is None else min(len(lines), start - 1 + max(1, limit))
    chunk = "".join(lines[start - 1:end])
    return {
        "status": "success",
        "path": relative,
        "text": chunk[:max_bytes],
        "truncated": len(chunk) > max_bytes or end < len(lines),
        "line_start": start,
        "line_end": end,
        "line_count": len(lines),
    }


def list_directory(
    workspace_root: str | Path, path: str | Path = ".", *, authority: Any = None
) -> dict[str, Any]:
    resolved = resolve_workspace_path(workspace_root, path, authority=authority)
    if not resolved.exists():
        return {"status": "failed", "error": {"type": "not_found", "path": str(path)}}
    if not resolved.is_dir():
        return {"status": "failed", "error": {"type": "not_directory", "path": str(path)}}
    entries = sorted(child.name + ("/" if child.is_dir() else "") for child in resolved.iterdir())
    return {"status": "success", "path": str(path), "entries": entries}


# `glob_paths` and `grep_files` enumerate a tree rather than resolve a named
# path, so they stay workspace-only. Walking an attached root is the reconcile
# pass's and the explorer's job, both of which already know which root they are
# in; teaching a glob to span roots would make one pattern mean two trees.
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


#: TOOL-02 — the most context lines either side of a match `grep` returns.
MAX_GREP_CONTEXT = 5
#: A model-written pattern is bounded before it is compiled.
MAX_GREP_PATTERN_CHARS = 500
#: Python's `re` has no time limit, so a pattern with a quantified group that
#: is itself quantified — `(a+)+`, `(\w*)*` — can backtrack for minutes on one
#: line and hold the host's thread. Such patterns are refused by shape rather
#: than run and timed out; the search they meant is always expressible without
#: the nesting.
_NESTED_QUANTIFIER = re.compile(r"\([^()]*[+*][^()]*\)\s*[+*{]")


def _grep_matcher(
    query: str, *, regex: bool, ignore_case: bool
) -> Callable[[str], bool] | dict[str, Any]:
    if not regex:
        if ignore_case:
            folded = query.casefold()
            return lambda line: folded in line.casefold()
        return lambda line: query in line
    if len(query) > MAX_GREP_PATTERN_CHARS:
        return _failure("pattern_too_long", limit=MAX_GREP_PATTERN_CHARS)
    if _NESTED_QUANTIFIER.search(query):
        return _failure("pattern_nested_quantifier")
    try:
        compiled = re.compile(query, re.IGNORECASE if ignore_case else 0)
    except re.error as exc:
        return _failure("pattern_invalid", message=str(exc))
    return lambda line: compiled.search(line) is not None


def grep_files(
    workspace_root: str | Path,
    query: str,
    path: str | Path = ".",
    *,
    include: str = "*",
    max_results: int = 100,
    regex: bool = False,
    ignore_case: bool = False,
    context: int = 0,
) -> dict[str, Any]:
    """Search file contents; literal by default, a regular expression on request.

    TOOL-02 added `regex`, `ignore_case` and `context` (lines either side, at
    most :data:`MAX_GREP_CONTEXT`). A match carries `before` and `after` only
    when context was asked for, so a plain search returns exactly what it did.
    """
    if not query:
        return _failure("query_empty")
    matcher = _grep_matcher(query, regex=regex, ignore_case=ignore_case)
    if isinstance(matcher, dict):
        return matcher
    span = max(0, min(int(context), MAX_GREP_CONTEXT))
    root = Path(workspace_root).resolve()
    base = resolve_workspace_path(root, path)
    if not base.exists():
        return {"status": "failed", "error": {"type": "not_found", "path": str(path)}}
    files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
    results: list[dict[str, Any]] = []
    for file_path in sorted(files):
        if not fnmatch.fnmatch(file_path.name, include) or not is_text_file(file_path):
            continue
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            if not matcher(line):
                continue
            match: dict[str, Any] = {
                "path": str(file_path.relative_to(root)),
                "line": index + 1,
                "text": line[:500],
            }
            if span:
                match["before"] = [item[:500] for item in lines[max(0, index - span):index]]
                match["after"] = [item[:500] for item in lines[index + 1:index + 1 + span]]
            results.append(match)
            if len(results) >= max_results:
                return {"status": "success", "matches": results, "truncated": True}
    return {"status": "success", "matches": results, "truncated": False}


def stat_path(
    workspace_root: str | Path, path: str | Path, *, authority: Any = None
) -> dict[str, Any]:
    resolved = resolve_workspace_path(workspace_root, path, authority=authority)
    if not resolved.exists():
        return {"status": "failed", "error": {"type": "not_found", "path": str(path)}}
    return {
        "status": "success",
        "path": _relative_path(workspace_root, resolved, authority=authority),
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
    authority: Any = None,
) -> dict[str, Any]:
    import difflib

    before = read_file(workspace_root, before_path, authority=authority)
    after = read_file(workspace_root, after_path, authority=authority)
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
    workspace_root: str | Path, path: str | Path, new_text: str, *, authority: Any = None
) -> dict[str, Any]:
    # Refused here as well as at execution time, so a proposal the runtime could
    # never carry out is rejected while the model can still react to it, rather
    # than sitting in the Approvals inbox looking actionable.
    resolved = resolve_writable_workspace_path(workspace_root, path, authority=authority)
    before = (
        resolved.read_text(encoding="utf-8")
        if resolved.exists() and resolved.is_file() and is_text_file(resolved)
        else None
    )
    return {
        "status": "proposal",
        "path": _relative_path(workspace_root, resolved, authority=authority),
        "before_snapshot": before,
        "proposed_text": new_text,
        "requires_approval": True,
    }


def write_file_content(
    workspace_root: str | Path, path: str | Path, text: str, *, authority: Any = None
) -> dict[str, Any]:
    resolved = resolve_writable_workspace_path(workspace_root, path, authority=authority)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(text, encoding="utf-8")
    return {
        "status": "success",
        "path": _relative_path(workspace_root, resolved, authority=authority),
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
    workspace_root: str | Path, path: str | Path, *, authority: Any = None
) -> tuple[Path, str] | dict[str, Any]:
    resolved = resolve_writable_workspace_path(workspace_root, path, authority=authority)
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


def _relative_path(workspace_root: str | Path, resolved: Path, *, authority: Any = None) -> str:
    """What to call a resolved path in a result, a proposal or a patch header.

    ``relative_to`` is only correct while every resolved path is inside the
    workspace. Once a project can be an attached folder that is no longer true,
    and the bare call raises ``ValueError`` — turning a *successful* write into
    a crash on the way out. The authority already knows what each root's files
    are called, so ask it, and keep the bare relative path for workspace files
    so no stored patch header or checkpoint key changes meaning.
    """
    return _authority_for(workspace_root, authority).resolve_read(resolved).display


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
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str,
    *, authority: Any = None,
) -> tuple[Path, str, str] | dict[str, Any]:
    target = _existing_text_target(workspace_root, path, authority=authority)
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


def edit_options(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """The `edit_file` modes a call asked for, read the same way at every site.

    TOOL-02 added ``replace_all`` and TOOL-99 ``insert_line``. The preview, the
    approval diff and the executor all read a call through this, so the change
    the owner approves is the change that runs.
    """
    raw_line = arguments.get("insert_line")
    insert_line: int | None = None
    if raw_line is not None and raw_line != "" and not isinstance(raw_line, bool):
        try:
            insert_line = int(raw_line)
        except (TypeError, ValueError):
            insert_line = -1
    raw_cell = arguments.get("cell")
    cell = None if raw_cell is None or raw_cell == "" or isinstance(raw_cell, bool) else str(raw_cell).strip()
    return {
        "replace_all": arguments.get("replace_all") is True,
        "insert_line": insert_line,
        "cell": cell,
    }


def _edit_candidate(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str,
    *, replace_all: bool = False, insert_line: int | None = None, cell: str | None = None,
    authority: Any = None,
) -> tuple[Path, str, str] | dict[str, Any]:
    """One edit, in whichever of its three modes the call named.

    * the default: replace one unique match (whitespace-tolerant, never ambiguous);
    * ``replace_all``: replace every exact occurrence, at least one required;
    * ``insert_line``: insert ``new_text`` after that line (0 is the top), with
      ``old_text`` left empty so a call cannot mean two edits at once.

    TOOL-03 — ``cell`` makes it a notebook edit: the same three modes, applied
    to one cell's source in a ``.ipynb`` rather than to the file's JSON.
    """
    if cell is not None:
        return _notebook_candidate(
            workspace_root, path, old_text, new_text,
            replace_all=replace_all, insert_line=insert_line, cell=cell, authority=authority,
        )
    if insert_line is not None:
        if old_text:
            return _failure("insert_line_with_old_text")
        if replace_all:
            return _failure("insert_line_with_replace_all")
        target = _existing_text_target(workspace_root, path, authority=authority)
        if isinstance(target, dict):
            return target
        resolved, before = target
        lines = before.splitlines(keepends=True)
        if insert_line < 0 or insert_line > len(lines):
            return _failure("insert_line_out_of_range", line_count=len(lines))
        if insert_line and not lines[insert_line - 1].endswith("\n"):
            lines[insert_line - 1] += "\n"
        inserted = new_text if new_text.endswith("\n") or not new_text else new_text + "\n"
        return resolved, before, "".join([*lines[:insert_line], inserted, *lines[insert_line:]])
    if replace_all:
        if not old_text:
            return _failure("old_text_empty")
        target = _existing_text_target(workspace_root, path, authority=authority)
        if isinstance(target, dict):
            return target
        resolved, before = target
        if old_text not in before:
            return _failure("old_text_not_found")
        return resolved, before, before.replace(old_text, new_text)
    return _replace_candidate(workspace_root, path, old_text, new_text, authority=authority)


def _notebook_candidate(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str,
    *, replace_all: bool, insert_line: int | None, cell: str, authority: Any,
) -> tuple[Path, str, str] | dict[str, Any]:
    """One edit to one notebook cell, returned as the whole file before and after.

    The cell is named by its index or its ``id``. A plain edit needs exactly one
    match in that cell's source: a notebook cell is short, and guessing between
    two matches is the mistake the whitespace-tolerant file path exists to
    avoid. The file is written back with the indentation it had and its keys in
    the order they were read, so the diff the owner approves is the cell.
    """
    if not str(path).lower().endswith(".ipynb"):
        return _failure("cell_needs_a_notebook")
    target = _existing_text_target(workspace_root, path, authority=authority)
    if isinstance(target, dict):
        return target
    resolved, before = target
    try:
        notebook = json.loads(before)
    except json.JSONDecodeError:
        return _failure("notebook_not_json")
    cells = notebook.get("cells") if isinstance(notebook, dict) else None
    if not isinstance(cells, list):
        return _failure("notebook_has_no_cells")
    chosen: dict[str, Any] | None = None
    if cell.isdigit() and int(cell) < len(cells) and isinstance(cells[int(cell)], dict):
        chosen = cells[int(cell)]
    else:
        chosen = next((item for item in cells if isinstance(item, dict) and item.get("id") == cell), None)
    if chosen is None:
        return _failure("cell_not_found", cell_count=len(cells))
    raw = chosen.get("source", "")
    source = "".join(raw) if isinstance(raw, list) else str(raw)
    if insert_line is not None:
        if old_text:
            return _failure("insert_line_with_old_text")
        lines = source.splitlines(keepends=True)
        if insert_line < 0 or insert_line > len(lines):
            return _failure("insert_line_out_of_range", line_count=len(lines))
        if insert_line and not lines[insert_line - 1].endswith("\n"):
            lines[insert_line - 1] += "\n"
        tail = "" if insert_line == len(lines) or new_text.endswith("\n") else "\n"
        updated = "".join([*lines[:insert_line], new_text + tail, *lines[insert_line:]])
    elif not old_text:
        return _failure("old_text_empty")
    elif replace_all:
        if old_text not in source:
            return _failure("old_text_not_found")
        updated = source.replace(old_text, new_text)
    else:
        count = source.count(old_text)
        if count != 1:
            return _failure("old_text_not_found" if count == 0 else "old_text_ambiguous", matches=count)
        updated = source.replace(old_text, new_text, 1)
    chosen["source"] = updated.splitlines(keepends=True)
    indent_match = re.search(r"\n( +)\S", before)
    indent = len(indent_match.group(1)) if indent_match else 1
    after = json.dumps(notebook, indent=indent, ensure_ascii=False) + ("\n" if before.endswith("\n") else "")
    return resolved, before, after


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


def _patch_candidate(
    workspace_root: str | Path, path: str | Path, patch: str, *, authority: Any = None
) -> _PatchCandidate | dict[str, Any]:
    resolved = resolve_writable_workspace_path(workspace_root, path, authority=authority)
    expected_path = _relative_path(workspace_root, resolved, authority=authority).replace("\\", "/")
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
    workspace_root: str | Path, path: str | Path | None, patch: str, *, authority: Any = None
) -> list[_PatchCandidate] | dict[str, Any]:
    expected: str | None = None
    if path:
        expected = _relative_path(
            workspace_root,
            resolve_writable_workspace_path(workspace_root, path, authority=authority),
            authority=authority,
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
        candidate = _patch_candidate(workspace_root, target, section, authority=authority)
        if isinstance(candidate, dict):
            candidate.setdefault("error", {})["path"] = target
            return candidate
        if candidate.path in seen:
            return _failure("duplicate_patch_target", path=target)
        seen.add(candidate.path)
        candidates.append(candidate)
    return candidates


def _proposal_from_candidate(
    workspace_root: str | Path,
    candidate: tuple[Path, str, str] | _PatchCandidate | dict[str, Any],
    *, authority: Any = None,
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
        "path": _relative_path(workspace_root, resolved, authority=authority),
        "before_snapshot": before,
        "proposed_text": proposed_text,
        "operation": operation,
        "requires_approval": True,
    }


def proposed_edit_snapshot(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str,
    *, replace_all: bool = False, insert_line: int | None = None, cell: str | None = None,
    authority: Any = None,
) -> dict[str, Any]:
    return _proposal_from_candidate(
        workspace_root,
        _edit_candidate(
            workspace_root, path, old_text, new_text,
            replace_all=replace_all, insert_line=insert_line, cell=cell, authority=authority,
        ),
        authority=authority,
    )


def proposed_patch_snapshot(
    workspace_root: str | Path, path: str | Path | None, patch: str, *, authority: Any = None
) -> dict[str, Any]:
    candidates = _patch_candidates(workspace_root, path, patch, authority=authority)
    if isinstance(candidates, dict):
        return candidates
    changes = [
        {
            "path": _relative_path(workspace_root, item.path, authority=authority),
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
    workspace_root: str | Path,
    candidate: tuple[Path, str, str] | _PatchCandidate | dict[str, Any],
    *, authority: Any = None,
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
        "path": _relative_path(workspace_root, resolved, authority=authority),
        "size_bytes": size_bytes,
        "operation": operation,
    }


def replace_text_content(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str,
    *, replace_all: bool = False, insert_line: int | None = None, cell: str | None = None,
    authority: Any = None,
) -> dict[str, Any]:
    return _write_candidate(
        workspace_root,
        _edit_candidate(
            workspace_root, path, old_text, new_text,
            replace_all=replace_all, insert_line=insert_line, cell=cell, authority=authority,
        ),
        authority=authority,
    )


def edit_file_content(
    workspace_root: str | Path, path: str | Path, old_text: str, new_text: str,
    *, replace_all: bool = False, insert_line: int | None = None, cell: str | None = None,
    authority: Any = None,
) -> dict[str, Any]:
    return replace_text_content(
        workspace_root, path, old_text, new_text,
        replace_all=replace_all, insert_line=insert_line, cell=cell, authority=authority,
    )


def apply_patch_content(
    workspace_root: str | Path, path: str | Path | None, patch: str, *, authority: Any = None
) -> dict[str, Any]:
    """Apply every file section as one transaction, rolling back on any write failure."""
    candidates = _patch_candidates(workspace_root, path, patch, authority=authority)
    if isinstance(candidates, dict):
        return candidates
    completed: list[_PatchCandidate] = []
    try:
        for candidate in candidates:
            result = _write_candidate(workspace_root, candidate, authority=authority)
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
