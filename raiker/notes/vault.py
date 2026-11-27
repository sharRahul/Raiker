"""The notes vault: a folder of Markdown, with Obsidian's links and Raiker's care.

Obsidian's model, kept: a vault is a plain folder; a note is a ``.md`` file; a
link names a note by its name and resolves case-insensitively to the shortest
path; renaming a note rewrites every link to it; a deleted note goes to the
vault's ``.trash``; backlinks are linked mentions plus unlinked mentions (the
note's name or an alias in plain words); the graph is notes and links; a daily
note is ``YYYY-MM-DD``; search understands ``file:``, ``path:``, ``tag:``,
``line:``, ``task:``, ``[property:value]``, quotes and ``-exclusion``.

What Raiker adds:

* **Safe by construction.** Every path is resolved inside the vault — no
  ``..``, no absolute paths, no link leaving it — and only Markdown is written.
* **No lost work.** A save names the version it edited (``expected_mtime``);
  a note changed underneath (by Obsidian, another agent, a sync) is refused
  as a conflict instead of overwritten.
* **One step to link.** An unlinked mention becomes a link on its own line,
  without opening the other note.
* **Raiker can read it.** The same index answers the agent's ``note_search``
  and ``note_read`` tools, so a question in Chat can be answered from notes.
"""

from __future__ import annotations

import os
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from raiker.notes.parse import ParsedNote, parse_note

TRASH = ".trash"
MAX_NOTE_BYTES = 2_000_000
_WIKILINK_BODY = re.compile(r"(!?)\[\[([^\[\]\n]+?)\]\]")


class NotesError(ValueError):
    """A refused notes operation, with a stable reason code."""


@dataclass(frozen=True)
class NoteFile:
    path: str
    name: str
    mtime: float
    size: int


def _norm(name: str) -> str:
    return name.strip().lower()


class NotesVault:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[float, ParsedNote]] = {}

    # ── paths ──────────────────────────────────────────────────────────────
    def resolve_path(self, relative: str, *, must_exist: bool = False) -> Path:
        cleaned = relative.replace("\\", "/").strip().lstrip("/")
        if not cleaned or cleaned.startswith(".") or "/." in cleaned or ".." in cleaned.split("/"):
            raise NotesError("note_path_invalid")
        if not cleaned.lower().endswith(".md"):
            cleaned += ".md"
        path = (self.root / cleaned).resolve()
        if self.root not in path.parents:
            raise NotesError("note_path_outside_vault")
        if must_exist and not path.is_file():
            raise NotesError("note_not_found")
        return path

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    # ── listing and reading ────────────────────────────────────────────────
    def files(self) -> list[NoteFile]:
        found: list[NoteFile] = []
        for directory, folders, names in os.walk(self.root):
            folders[:] = sorted(folder for folder in folders if not folder.startswith("."))
            for name in sorted(names):
                if not name.lower().endswith(".md"):
                    continue
                path = Path(directory) / name
                stat = path.stat()
                found.append(NoteFile(self.relative(path), path.stem, stat.st_mtime, stat.st_size))
        return found

    def parsed(self, relative: str) -> ParsedNote:
        path = self.resolve_path(relative, must_exist=True)
        mtime = path.stat().st_mtime
        cached = self._cache.get(relative)
        if cached and cached[0] == mtime:
            return cached[1]
        note = parse_note(path.read_text(encoding="utf-8", errors="replace"))
        self._cache[relative] = (mtime, note)
        return note

    def read(self, relative: str) -> dict[str, Any]:
        path = self.resolve_path(relative, must_exist=True)
        content = path.read_text(encoding="utf-8", errors="replace")
        note = self.parsed(self.relative(path))
        return {
            "path": self.relative(path),
            "name": path.stem,
            "content": content,
            "mtime": path.stat().st_mtime,
            "properties": note.properties,
            "tags": note.tags,
            "aliases": note.aliases,
            "headings": [{"level": level, "text": text, "line": line} for level, text, line in note.headings],
            "tasks": [{"text": task.text, "done": task.done, "line": task.line} for task in note.tasks],
            "links": [self._link_view(relative, link) for link in note.links],
        }

    # ── writing ────────────────────────────────────────────────────────────
    def write(self, relative: str, content: str, *, expected_mtime: float | None) -> dict[str, Any]:
        if len(content.encode("utf-8")) > MAX_NOTE_BYTES:
            raise NotesError("note_too_large")
        path = self.resolve_path(relative)
        if path.exists():
            if expected_mtime is None or abs(path.stat().st_mtime - expected_mtime) > 1e-6:
                raise NotesError("note_changed_elsewhere")
        elif expected_mtime is not None:
            raise NotesError("note_not_found")
        self._atomic_write(path, content)
        return self.read(self.relative(path))

    def create(self, relative: str, content: str = "") -> dict[str, Any]:
        path = self.resolve_path(relative)
        if path.exists():
            raise NotesError("note_exists")
        self._atomic_write(path, content)
        return self.read(self.relative(path))

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(path)
        self._cache.pop(self.relative(path), None)

    def delete(self, relative: str) -> str:
        """Move to the vault's ``.trash``, as Obsidian does; returns where it went."""
        path = self.resolve_path(relative, must_exist=True)
        trash = self.root / TRASH / self.relative(path)
        if trash.exists():
            trash = trash.with_name(f"{trash.stem} {datetime.now():%Y%m%d%H%M%S}{trash.suffix}")
        trash.parent.mkdir(parents=True, exist_ok=True)
        path.replace(trash)
        self._cache.pop(relative, None)
        return trash.relative_to(self.root).as_posix()

    def rename(self, old: str, new: str) -> dict[str, Any]:
        """Rename a note and rewrite every link to it, keeping headings, blocks and aliases."""
        source = self.resolve_path(old, must_exist=True)
        target = self.resolve_path(new)
        if target.exists():
            raise NotesError("note_exists")
        old_rel, new_rel = self.relative(source), self.relative(target)
        referrers = [item for item in self.backlinks(old_rel)["linked"]]
        # Which link targets meant the old note, decided before the file moves.
        self._before: dict[tuple[str, str], bool] = {}
        for referrer in {item["path"] for item in referrers}:
            for link in self.parsed(referrer).links:
                self._before[(referrer, _norm(link.target))] = (
                    self.resolve(link.target, from_path=referrer) == old_rel
                )
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
        self._cache.pop(old_rel, None)
        new_name = target.stem
        # Link by name when the name is unique, by path otherwise.
        unique = sum(1 for item in self.files() if _norm(item.name) == _norm(new_name)) == 1
        replacement = new_name if unique else new_rel[:-3]
        updated = 0
        for referrer in {item["path"] for item in referrers}:
            path = self.resolve_path(new_rel if referrer == old_rel else referrer, must_exist=True)
            text = path.read_text(encoding="utf-8", errors="replace")

            def relink(match: re.Match[str], referrer: str = referrer) -> str:
                head, anchor = _split_target(match.group(2))
                if self._resolved_before_rename(head, old_rel, referrer):
                    return f"{match.group(1)}[[{replacement}{anchor}]]"
                return match.group(0)

            changed = _WIKILINK_BODY.sub(relink, text)
            if changed != text:
                self._atomic_write(path, changed)
                updated += 1
        return {**self.read(new_rel), "links_updated": updated}

    # ── links ──────────────────────────────────────────────────────────────
    def _names(self) -> dict[str, list[str]]:
        names: dict[str, list[str]] = {}
        for item in self.files():
            names.setdefault(_norm(item.name), []).append(item.path)
        return names

    def resolve(self, target: str, *, from_path: str = "") -> str | None:
        """Obsidian's rule: a path if it is one, else the shortest path with that name."""
        if not target.strip():
            return from_path or None
        cleaned = target.replace("\\", "/").strip()
        if cleaned.lower().endswith(".md"):
            cleaned = cleaned[:-3]
        if "/" in cleaned:
            for item in self.files():
                if _norm(item.path[:-3]) == _norm(cleaned):
                    return item.path
        candidates = self._names().get(_norm(cleaned.rsplit("/", 1)[-1]), [])
        if not candidates:
            for item in self.files():
                note = self.parsed(item.path)
                if any(_norm(alias) == _norm(cleaned) for alias in note.aliases):
                    return item.path
            return None
        here = str(Path(from_path).parent) if from_path else ""
        return sorted(candidates, key=lambda path: (str(Path(path).parent) != here, path.count("/"), path))[0]

    def _resolved_before_rename(self, target: str, old_rel: str, referrer: str) -> bool:
        return self._before.get((referrer, _norm(target)), False)

    def _link_view(self, from_path: str, link: Any) -> dict[str, Any]:
        resolved = self.resolve(link.target, from_path=from_path)
        return {
            "target": link.target, "heading": link.heading, "block": link.block,
            "alias": link.alias, "embed": link.embed, "line": link.line,
            "resolved": resolved,
        }

    def backlinks(self, relative: str) -> dict[str, Any]:
        """Linked mentions, and unlinked mentions of the name or an alias."""
        target = self.resolve_path(relative, must_exist=True)
        rel = self.relative(target)
        note = self.parsed(rel)
        names = [target.stem, *note.aliases]
        mention = re.compile(
            r"(?<![\[\w])(" + "|".join(re.escape(name) for name in names if name.strip()) + r")(?![\w\]])",
            re.IGNORECASE,
        )
        linked: list[dict[str, Any]] = []
        unlinked: list[dict[str, Any]] = []
        for item in self.files():
            other = self.parsed(item.path)
            lines = (self.root / item.path).read_text(encoding="utf-8", errors="replace").splitlines()
            linked_lines = set()
            for link in other.links:
                if self.resolve(link.target, from_path=item.path) == rel and item.path != rel:
                    linked_lines.add(link.line)
            for line in sorted(linked_lines):
                linked.append({"path": item.path, "name": item.name, "line": line, "context": lines[line] if line < len(lines) else "", "match": ""})
            if item.path == rel:
                continue
            for index, raw in enumerate(lines):
                if index < other.body_start_line:
                    continue
                plain = _WIKILINK_BODY.sub("", raw)
                found = mention.search(plain)
                if found:
                    unlinked.append({"path": item.path, "name": item.name, "line": index, "context": raw, "match": found.group(1)})
        return {"path": rel, "linked": linked, "unlinked": unlinked}

    def link_mention(self, source: str, line: int, target: str) -> dict[str, Any]:
        """Turn the first unlinked mention of *target* on one line into a wikilink."""
        target_path = self.resolve_path(target, must_exist=True)
        note = self.parsed(self.relative(target_path))
        path = self.resolve_path(source, must_exist=True)
        lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
        if not 0 <= line < len(lines):
            raise NotesError("note_line_out_of_range")
        name = target_path.stem
        for candidate in [name, *note.aliases]:
            pattern = re.compile(rf"(?<![\[\w]){re.escape(candidate)}(?![\w\]])", re.IGNORECASE)
            found = pattern.search(lines[line])
            if found:
                shown = found.group(0)
                link = f"[[{name}]]" if shown == name else f"[[{name}|{shown}]]"
                lines[line] = lines[line][: found.start()] + link + lines[line][found.end() :]
                self._atomic_write(path, "\n".join(lines))
                return self.read(self.relative(path))
        raise NotesError("note_mention_not_found")

    def graph(self, relative: str | None = None, depth: int = 1) -> dict[str, Any]:
        """Notes and links; around one note to *depth* when one is named (local graph)."""
        edges: set[tuple[str, str]] = set()
        unresolved: set[str] = set()
        files = self.files()
        for item in files:
            for link in self.parsed(item.path).links:
                resolved = self.resolve(link.target, from_path=item.path)
                if resolved and resolved != item.path:
                    edges.add((item.path, resolved))
                elif not resolved and link.target:
                    unresolved.add(link.target)
        nodes = {item.path for item in files}
        if relative is not None:
            start = self.relative(self.resolve_path(relative, must_exist=True))
            keep = {start}
            queue = deque([(start, 0)])
            while queue:
                node, level = queue.popleft()
                if level >= max(1, min(depth, 3)):
                    continue
                for a, b in edges:
                    other = b if a == node else a if b == node else None
                    if other and other not in keep:
                        keep.add(other)
                        queue.append((other, level + 1))
            nodes, edges = keep, {(a, b) for a, b in edges if a in keep and b in keep}
        incoming: dict[str, int] = {}
        for _, b in edges:
            incoming[b] = incoming.get(b, 0) + 1
        return {
            "nodes": [{"path": node, "name": Path(node).stem, "links_in": incoming.get(node, 0)} for node in sorted(nodes)],
            "edges": [{"source": a, "target": b} for a, b in sorted(edges)],
            "unresolved": sorted(unresolved) if relative is None else [],
        }

    def tags(self) -> list[dict[str, Any]]:
        counts: dict[str, tuple[str, int]] = {}
        for item in self.files():
            for tag in self.parsed(item.path).tags:
                shown, count = counts.get(tag.lower(), (tag, 0))
                counts[tag.lower()] = (shown, count + 1)
        return [{"tag": shown, "count": count} for shown, count in sorted(counts.values(), key=lambda pair: (-pair[1], pair[0].lower()))]

    # ── search ─────────────────────────────────────────────────────────────
    def search(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        terms = _parse_query(query)
        if not terms:
            return []
        results: list[dict[str, Any]] = []
        for item in self.files():
            note = self.parsed(item.path)
            content = (self.root / item.path).read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            hit_line: int | None = None
            ok = True
            for negate, op, value in terms:
                matched, line = _match(op, value, item, note, content, lines)
                if negate:
                    matched, line = not matched, None
                if not matched:
                    ok = False
                    break
                if hit_line is None and line is not None:
                    hit_line = line
            if ok:
                snippet = lines[hit_line] if hit_line is not None and hit_line < len(lines) else (lines[note.body_start_line] if note.body_start_line < len(lines) else "")
                results.append({"path": item.path, "name": item.name, "line": hit_line, "snippet": snippet[:240], "mtime": item.mtime})
            if len(results) >= limit:
                break
        results.sort(key=lambda row: (row["line"] is None, -row["mtime"]))
        return results

    # ── daily notes and templates ──────────────────────────────────────────
    def daily(self, when: datetime | None = None, *, folder: str = "Daily", template: str | None = None) -> dict[str, Any]:
        moment = when or datetime.now()
        relative = f"{folder.strip('/')}/{moment:%Y-%m-%d}.md" if folder else f"{moment:%Y-%m-%d}.md"
        path = self.resolve_path(relative)
        if not path.exists():
            body = template if template is not None else "# {{date}}\n\n"
            self._atomic_write(path, fill_template(body, title=path.stem, when=moment))
        return self.read(self.relative(path))


def _split_target(body: str) -> tuple[str, str]:
    """``Note#Heading|alias`` → (``Note``, ``#Heading|alias``)."""
    cut = min((body.find(mark) for mark in "#|" if mark in body), default=len(body))
    return body[:cut].strip(), body[cut:]


def fill_template(template: str, *, title: str, when: datetime) -> str:
    """Obsidian's ``{{title}}``, ``{{date}}``, ``{{time}}`` and ``{{date:FORMAT}}``."""

    def moment_format(fmt: str) -> str:
        table = {"YYYY": "%Y", "YY": "%y", "MMMM": "%B", "MMM": "%b", "MM": "%m", "DD": "%d",
                 "dddd": "%A", "ddd": "%a", "HH": "%H", "mm": "%M", "ss": "%S"}
        return re.sub("|".join(sorted(table, key=len, reverse=True)), lambda m: table[m.group(0)], fmt)

    def replace(match: re.Match[str]) -> str:
        key, _, fmt = match.group(1).partition(":")
        key = key.strip().lower()
        if key == "title":
            return title
        if key == "date":
            return when.strftime(moment_format(fmt or "YYYY-MM-DD"))
        if key == "time":
            return when.strftime(moment_format(fmt or "HH:mm"))
        return match.group(0)

    return re.sub(r"\{\{([^}]+)\}\}", replace, template)


def _parse_query(query: str) -> list[tuple[bool, str, str]]:
    tokens = re.findall(r'-?\[[^\]]+\]|-?\w[\w-]*:(?:"[^"]*"|\([^)]*\)|\S+)|-?"[^"]+"|\S+', query)
    terms: list[tuple[bool, str, str]] = []
    for token in tokens:
        negate = token.startswith("-") and len(token) > 1
        body = token[1:] if negate else token
        if body.upper() == "OR":
            continue
        if body.startswith("[") and body.endswith("]"):
            terms.append((negate, "property", body[1:-1]))
            continue
        op_match = re.match(r'^(file|path|tag|line|task|task-todo|task-done|content|section):(.*)$', body)
        if op_match:
            value = op_match.group(2).strip('"()')
            terms.append((negate, op_match.group(1), value))
        else:
            terms.append((negate, "content", body.strip('"')))
    return terms


def _match(op: str, value: str, item: NoteFile, note: ParsedNote, content: str, lines: list[str]) -> tuple[bool, int | None]:
    needle = value.lower()
    if op == "file":
        return needle in item.name.lower(), None
    if op == "path":
        return needle in item.path.lower(), None
    if op == "tag":
        wanted = needle.lstrip("#")
        return any(tag.lower() == wanted or tag.lower().startswith(wanted + "/") for tag in note.tags), None
    if op == "property":
        key, _, expected = value.partition(":")
        if key not in note.properties:
            return False, None
        if not expected:
            return True, None
        actual = note.properties[key]
        values = actual if isinstance(actual, list) else [actual]
        options = [option.strip().lower() for option in expected.split(" OR ")]
        return any(str(v).lower() in options for v in values) or (expected.lower() == "null" and actual in (None, [])), None
    if op in {"task", "task-todo", "task-done"}:
        for task in note.tasks:
            if needle in task.text.lower() and (op == "task" or task.done == (op == "task-done")):
                return True, task.line
        return False, None
    if op == "line":
        words = needle.split()
        for index, line in enumerate(lines):
            if all(word in line.lower() for word in words):
                return True, index
        return False, None
    for index, line in enumerate(lines):
        if needle in line.lower():
            return True, index
    return needle in item.name.lower(), None
