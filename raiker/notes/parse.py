"""Reading one note the way Obsidian does.

The syntax is Obsidian's, so a folder written by Raiker opens in Obsidian and a
vault written in Obsidian opens in Raiker: YAML properties between ``---``
lines, ``[[wikilinks]]`` (with ``|alias``, ``#Heading`` and ``#^block``),
``![[embeds]]``, inline ``#tags`` (nested with ``/``), ``^block-ids`` and
``- [ ]`` tasks. Nothing here touches the disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_FENCE = re.compile(r"^(```|~~~)")
_WIKILINK = re.compile(r"(?P<embed>!?)\[\[(?P<body>[^\[\]\n]+?)\]\]")
_TAG = re.compile(r"(?<![\w/#&])#(?P<tag>[\w/-]*[^\W\d][\w/-]*)", re.UNICODE)
_HEADING = re.compile(r"^(?P<level>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")
_BLOCK = re.compile(r"\s\^(?P<id>[A-Za-z0-9-]+)\s*$")
_TASK = re.compile(r"^\s*[-*+]\s+\[(?P<mark>[ xX])\]\s+(?P<text>.*)$")
_INLINE_CODE = re.compile(r"`[^`\n]*`")


@dataclass(frozen=True)
class Link:
    target: str
    heading: str = ""
    block: str = ""
    alias: str = ""
    embed: bool = False
    line: int = 0


@dataclass(frozen=True)
class Task:
    text: str
    done: bool
    line: int


@dataclass
class ParsedNote:
    properties: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    body_start_line: int = 0
    links: list[Link] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    headings: list[tuple[int, str, int]] = field(default_factory=list)
    blocks: dict[str, int] = field(default_factory=dict)
    tasks: list[Task] = field(default_factory=list)


def _scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return None
    if (value[0] == value[-1]) and value[0] in "\"'" and len(value) >= 2:
        return value[1:-1]
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        return [_scalar(part) for part in value[1:-1].split(",") if part.strip()]
    try:
        return int(value) if re.fullmatch(r"-?\d+", value) else float(value) if re.fullmatch(r"-?\d+\.\d+", value) else value
    except ValueError:
        return value


def parse_properties(lines: list[str]) -> dict[str, Any]:
    """Obsidian's flat property YAML: ``key: value`` and ``key:`` + ``  - item`` lists."""
    properties: dict[str, Any] = {}
    current: str | None = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s*(.*)$", line)
        if item and current is not None:
            existing = properties.get(current)
            values = existing if isinstance(existing, list) else []
            values.append(_scalar(item.group(1)))
            properties[current] = values
            continue
        pair = re.match(r"^([^\s:][^:]*):(?:\s+(.*))?$", line)
        if pair:
            current = pair.group(1).strip()
            properties[current] = _scalar(pair.group(2) or "")
    return properties


def split_properties(text: str) -> tuple[dict[str, Any], str, int]:
    """(properties, body, line the body starts on)."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() in {"---", "..."}:
                return parse_properties(lines[1:index]), "\n".join(lines[index + 1 :]), index + 1
    return {}, text, 0


def parse_link(body: str, *, embed: bool = False, line: int = 0) -> Link:
    target, _, alias = body.partition("|")
    target, _, anchor = target.partition("#")
    heading = block = ""
    if anchor.startswith("^"):
        block = anchor[1:]
    else:
        heading = anchor
    return Link(target.strip(), heading.strip(), block.strip(), alias.strip(), embed, line)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def parse_note(text: str) -> ParsedNote:
    properties, body, start = split_properties(text)
    note = ParsedNote(properties=properties, body=body, body_start_line=start)
    note.aliases = _as_list(properties.get("aliases"))
    tags = [tag.lstrip("#") for tag in _as_list(properties.get("tags"))]
    for value in properties.values():
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str):
                for match in _WIKILINK.finditer(item):
                    note.links.append(parse_link(match["body"], line=0))
    fenced = False
    for offset, raw in enumerate(body.splitlines()):
        line = start + offset
        if _FENCE.match(raw.strip()):
            fenced = not fenced
            continue
        if fenced:
            continue
        visible = _INLINE_CODE.sub("", raw)
        heading = _HEADING.match(visible)
        if heading:
            note.headings.append((len(heading["level"]), heading["text"].strip(), line))
        else:
            tags.extend(match["tag"] for match in _TAG.finditer(visible))
        for match in _WIKILINK.finditer(visible):
            note.links.append(parse_link(match["body"], embed=bool(match["embed"]), line=line))
        block = _BLOCK.search(visible)
        if block:
            note.blocks[block["id"]] = line
        task = _TASK.match(visible)
        if task:
            note.tasks.append(Task(task["text"].strip(), task["mark"] != " ", line))
    seen: dict[str, str] = {}
    for tag in tags:
        seen.setdefault(tag.lower(), tag)
    note.tags = list(seen.values())
    return note
