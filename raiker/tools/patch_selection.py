"""Accepting part of a proposed change (GAP-BUILD B14).

An approval used to govern a whole change set: the owner read a diff and pressed
Accept or Reject on all of it. Reviewing code is not that. The reviewer who wants
two of five hunks had to reject everything and ask again, which is the one
interaction a coding agent's review surface exists to support.

**A selection narrows; it never edits.** That distinction is the whole security
argument, and this module is written so it cannot be violated:

* Ids are *positions* in the approved diff — ``"<file index>:<hunk index>"`` —
  not content. There is nothing in an id for a caller to smuggle a change
  through, and an id that names no hunk in the approved patch is rejected rather
  than ignored.
* :func:`select_hunks` only ever *removes* hunks from the patch it was given. It
  cannot add a line, reorder a hunk, or reach a file the approved patch did not
  name, because it copies bytes out of that patch and copies nothing else in.

So the immutable-intent hash the relay checks (A1) still covers the entire
approved change set, and what actually runs is a subset of it that the owner
chose. Rejecting a hunk is not applying it — never applying an inverse of it.

The applier this feeds (:func:`raiker.tools.filesystem.apply_patch_content`)
matches hunks by context with offset tolerance rather than by the line numbers in
the hunk header, which is what makes dropping a hunk safe: the hunks that remain
still find their own context in the file, and the header's ``old_start`` was only
ever a hint about where to look first.
"""
from __future__ import annotations

import re

_FILE_HEADER = re.compile(r"^--- ")
_HUNK_HEADER = re.compile(r"^@@ ")


def _sections(patch: str) -> list[tuple[list[str], list[list[str]]]]:
    """Split a unified diff into ``(header lines, hunks)`` per file section.

    Anything before the first ``---``/``+++`` pair — a ``diff --git`` line, an
    index line, a mode change — travels with the section it introduces, so a
    round trip through here preserves the patch the approval carried.
    """
    lines = patch.splitlines(keepends=True)
    starts = [
        index
        for index in range(len(lines) - 1)
        if _FILE_HEADER.match(lines[index]) and lines[index + 1].startswith("+++ ")
    ]
    if not starts:
        return []
    # A preamble on the first section keeps whatever came before its `---`.
    bounds = [*starts, len(lines)]
    sections: list[tuple[list[str], list[list[str]]]] = []
    for position, start in enumerate(starts):
        begin = 0 if position == 0 else start
        end = bounds[position + 1]
        body = lines[begin:end]
        header: list[str] = []
        hunks: list[list[str]] = []
        current: list[str] | None = None
        for line in body:
            if _HUNK_HEADER.match(line):
                current = [line]
                hunks.append(current)
            elif current is None:
                header.append(line)
            else:
                current.append(line)
        sections.append((header, hunks))
    return sections


def hunk_ids(patch: str) -> list[str]:
    """Every hunk in *patch*, as the ids a selection may name.

    The browser derives the same ids from the same diff by the same rule, so a
    selection means one thing on both sides without either having to send the
    other a list first.
    """
    return [
        f"{file_index}:{hunk_index}"
        for file_index, (_header, hunks) in enumerate(_sections(patch))
        for hunk_index in range(len(hunks))
    ]


def unknown_hunk_ids(patch: str, selected: list[str]) -> list[str]:
    """Ids in *selected* that name no hunk in *patch*, in the order given.

    Callers refuse the whole decision when this is non-empty. An id that names
    nothing is not a harmless typo: silently dropping it would apply a different
    change from the one the owner pressed Accept on.
    """
    known = set(hunk_ids(patch))
    return [item for item in selected if item not in known]


def select_hunks(patch: str, selected: list[str]) -> str:
    """The same patch with only the named hunks kept.

    A file section whose hunks were all rejected is dropped entirely, so a file
    the owner declined is not opened, not rewritten, and not recorded as
    changed. Selecting nothing yields an empty patch, which the caller must
    treat as "the owner accepted no part of this" rather than as an apply.
    """
    wanted = set(selected)
    out: list[str] = []
    for file_index, (header, hunks) in enumerate(_sections(patch)):
        kept = [
            hunk for hunk_index, hunk in enumerate(hunks) if f"{file_index}:{hunk_index}" in wanted
        ]
        if not kept:
            continue
        out.extend(header)
        for hunk in kept:
            out.extend(hunk)
    return "".join(out)


def patch_target_paths(patch: str) -> list[str]:
    """The `+++` targets of every file section, in order, `b/` prefix removed.

    Used by the edit-then-propose path (BUG-271) to answer one question about a
    patch the owner typed: does it change the same files the one they were
    reading did? An edit is a *different action* and gets its own approval, so
    this is not the authority boundary — it is the check that keeps a correction
    a correction rather than an unrelated change wearing a review's clothes.
    """
    targets: list[str] = []
    for header, _hunks in _sections(patch):
        for line in header:
            if not line.startswith("+++ "):
                continue
            value = line[4:].strip()
            # Strip a trailing tab-separated timestamp, which some diff writers
            # append, then the `b/` prefix `git diff` adds.
            value = value.split("\t", 1)[0].strip()
            if value.startswith("b/"):
                value = value[2:]
            targets.append(value)
            break
    return targets
