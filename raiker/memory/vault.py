"""A memory vault: Raiker's memory as linked Markdown any tool can read.

Obsidian's insight is that plain Markdown files with wikilinks and properties
are a database every tool already speaks: Claude Code, Hermes Agent and a
person in Obsidian can all read, link and edit them with no integration at all.
Hindsight's is that memory is atomic facts plus the entities that connect them.
The vault is both, kept in step with Raiker's governed store:

* ``Raiker Memory.md`` — the index: every topic and every entity, linked.
* ``Topics/<Topic>.md`` — one note per kind of memory; each fact is one list
  item ending in a block id (``^mem-…``), so it can be linked and edited.
* ``Projects/<Project>.md`` — project memories and lessons, one note per project.
* ``Entities/<Name>.md`` — a person, place or thing, with each relationship
  Raiker approved and a link back to the fact that is its evidence. Facts link
  the entities they name as ``[[Name]]``, so Obsidian's backlinks and graph
  traverse the memory the way Raiker's graph leg does.
* ``Inbox.md`` — the one place another tool adds a memory: a list item there
  is taken in on the next sync (through the same auto-keep rules as Chat) and
  moved to its topic.

Two-way, with the store in charge. Editing a fact's text in the vault edits the
memory; deleting its line archives it (restorable in Memory, never a silent
purge). Unknown files and anything outside a list item are left alone, so the
vault can hold the owner's own notes too. Secrets are masked exactly as in the
readable mirror (MM-3); secret- and credential-like memories are left out.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore

MANIFEST = ".raiker-vault.json"
INDEX = "Raiker Memory.md"
INBOX = "Inbox.md"
VAULT_ROLE = "vault_note"
_HIDDEN = frozenset({"secret_like", "credential_like"})
_TOPICS = {
    "preference": "Preferences", "personal": "About you", "fact": "Facts",
    "project": "Projects", "procedure": "Ways of working", "lesson": "Lessons",
    "check_fix": "Lessons", "relationship": "People and relationships",
    "summary": "Summaries",
}
_FACT_LINE = re.compile(r"^\s*[-*]\s+(?P<text>.*?)\s+\^(?P<block>mem-[A-Za-z0-9-]+)\s*$")
_INBOX_LINE = re.compile(r"^\s*[-*]\s+(?!\[[ xX]\]\s*$)(?P<text>\S.*?)\s*$")
_UNSAFE_NAME = re.compile(r'[\\/:*?"<>|#^\[\]]+')


@dataclass(frozen=True)
class VaultSync:
    written: int = 0
    edited: int = 0
    archived: int = 0
    added: int = 0


def block_id(memory_id: str) -> str:
    """An Obsidian block id: letters, digits and hyphens only."""
    return "mem-" + re.sub(r"[^A-Za-z0-9]", "-", memory_id.removeprefix("mem_"))


def note_name(name: str) -> str:
    cleaned = _UNSAFE_NAME.sub(" ", name).strip().strip(".")
    return re.sub(r"\s+", " ", cleaned)[:80] or "Untitled"


def _properties(**values: Any) -> str:
    lines = ["---"]
    for key, value in values.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {json.dumps(item, ensure_ascii=False)}" for item in value)
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def _linked(text: str, entities: list[str]) -> str:
    """The fact with each entity it names as a wikilink, longest names first."""
    for name in sorted(entities, key=len, reverse=True):
        pattern = re.compile(rf"(?<!\[\[)\b{re.escape(name)}\b(?!\]\])", re.IGNORECASE)

        def link(match: re.Match[str], target: str = name) -> str:
            shown = match.group(0)
            return f"[[{target}]]" if shown == target else f"[[{target}|{shown}]]"

        text = pattern.sub(link, text, count=1)
    return text


def _unlinked(text: str) -> str:
    """Back to plain words: ``[[Name|shown]]`` → ``shown``, ``[[Name]]`` → ``Name``."""
    return re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]|\[\[([^\]]+)\]\]", lambda m: m.group(2) or m.group(3), text)


def _write(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)
    return True


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _project_names(store: SQLiteStore) -> dict[str, str]:
    try:
        rows = store._rows("SELECT project_id, name FROM projects")  # noqa: SLF001
    except Exception:  # noqa: BLE001 — no projects table means no project names
        return {}
    return {str(row["project_id"]): str(row["name"]) for row in rows}


def _mask(text: str) -> str:
    from raiker.context.redaction import redact_text

    return redact_text(text)[0]


def export_vault(store: SQLiteStore, vault: Path, *, owner_principal_id: str) -> tuple[int, dict[str, Any]]:
    """Write the vault from the store; returns (files written, manifest)."""
    memories = [
        row for row in store.list_approved_memory(
            limit=5_000, include_search_disabled=True, owner_principal_id=owner_principal_id
        )
        if str(row.get("sensitivity") or "") not in _HIDDEN
    ]
    relationships = store.list_memory_relationships(owner_principal_id)
    entities = sorted({str(r["subject_name"]) for r in relationships} | {str(r["object_name"]) for r in relationships})
    projects = _project_names(store)
    notes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in memories:
        scope = str(row.get("scope") or "")
        if scope.startswith("project:"):
            project_id = scope.split(":", 1)[1]
            notes[f"Projects/{note_name(projects.get(project_id, project_id))}.md"].append(row)
        else:
            topic = _TOPICS.get(str(row.get("memory_type") or ""), "Other memories")
            notes[f"Topics/{note_name(topic)}.md"].append(row)

    manifest: dict[str, Any] = {"version": 1, "owner": owner_principal_id, "facts": {}}
    written = 0
    now = utc_now()
    for relative, rows in sorted(notes.items()):
        title = Path(relative).stem
        lines = [
            _properties(
                type="raiker-memory", topic=title, source_agent="raiker", updated=now,
                tags=["raiker/memory", f"raiker/{note_name(title).lower().replace(' ', '-')}"],
            ),
            "",
            f"# {title}",
            "",
        ]
        for row in sorted(rows, key=lambda item: str(item.get("created_at") or "")):
            text = _mask(str(row.get("text") or "").replace("\n", " ").strip())
            block = block_id(str(row["memory_id"]))
            lines.append(f"- {_linked(text, entities)} ^{block}")
            manifest["facts"][block] = {
                "memory_id": str(row["memory_id"]), "file": relative, "checksum": _checksum(text),
            }
        written += _write(vault / relative, "\n".join(lines) + "\n")

    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relationship in relationships:
        by_entity[str(relationship["subject_name"])].append(relationship)
        by_entity[str(relationship["object_name"])].append(relationship)
    facts = manifest["facts"]
    for name in entities:
        lines = [
            _properties(type="raiker-entity", source_agent="raiker", updated=now, tags=["raiker/entity"]),
            "", f"# {name}", "",
        ]
        for relationship in by_entity[name]:
            block = block_id(str(relationship["evidence_memory_id"]))
            evidence = facts.get(block)
            source = f" — [[{Path(evidence['file']).stem}#^{block}|evidence]]" if evidence else ""
            lines.append(
                f"- [[{relationship['subject_name']}]] {relationship['predicate']} "
                f"[[{relationship['object_name']}]]{source}"
            )
        written += _write(vault / "Entities" / f"{note_name(name)}.md", "\n".join(lines) + "\n")

    index = [
        _properties(type="raiker-memory-index", source_agent="raiker", updated=now, tags=["raiker/memory"]),
        "", "# Raiker Memory", "",
        "What Raiker remembers, as linked notes. Edit a fact to correct it; delete its line "
        "to archive it. Add new memories to [[Inbox]].", "",
        "## Topics", "", *(f"- [[{Path(path).stem}]]" for path in sorted(notes)), "",
        "## Entities", "", *(f"- [[{name}]]" for name in entities), "",
    ]
    written += _write(vault / INDEX, "\n".join(index))
    if not (vault / INBOX).exists():
        written += _write(
            vault / INBOX,
            _properties(type="raiker-inbox", source_agent="raiker", tags=["raiker/inbox"])
            + "\n\n# Inbox\n\nAdd one memory per list item. Raiker takes them in on its next sync.\n\n",
        )
    _write(vault / MANIFEST, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return written, manifest


def _read_manifest(vault: Path) -> dict[str, Any]:
    try:
        data = json.loads((vault / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _vault_facts(vault: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in vault.rglob("*.md"):
        if any(part.startswith(".") for part in path.relative_to(vault).parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in content.splitlines():
            match = _FACT_LINE.match(line)
            if match:
                found[match["block"]] = _unlinked(match["text"]).strip()
    return found


def _take_inbox(vault: Path) -> list[str]:
    path = vault / INBOX
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    body_started = False
    kept: list[str] = []
    taken: list[str] = []
    in_properties = content.startswith("---")
    for index, line in enumerate(content.splitlines()):
        if in_properties:
            kept.append(line)
            if index > 0 and line.strip() == "---":
                in_properties = False
            continue
        body_started = body_started or bool(line.strip())
        match = _INBOX_LINE.match(line)
        if match and not _FACT_LINE.match(line):
            taken.append(_unlinked(match["text"]).strip())
            continue
        kept.append(line)
    if taken:
        _write(path, "\n".join(kept).rstrip() + "\n\n")
    return [text for text in taken if text]


def sync_vault(
    store: SQLiteStore, vault: str | Path, *, workspace_root: str | Path, owner_principal_id: str
) -> VaultSync:
    """Take in what changed in the vault, then write it back from the store."""
    from raiker.memory.store import get_memory, set_memory_archived, update_memory

    root = Path(vault).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(root)
    edited = archived = added = 0
    if manifest.get("owner") == owner_principal_id:
        present = _vault_facts(root)
        for block, known in dict(manifest.get("facts") or {}).items():
            memory_id = str(known.get("memory_id") or "")
            entry = get_memory(memory_id, workspace_root=workspace_root, owner_principal_id=owner_principal_id)
            if entry is None:
                continue
            if block not in present:
                set_memory_archived(
                    memory_id, archived=True, workspace_root=workspace_root, store=store,
                    owner_principal_id=owner_principal_id,
                )
                store.record_memory_lifecycle_event(
                    memory_id, "archive", owner_principal_id, {"source": "vault", "reason": "line_deleted"}
                )
                archived += 1
                continue
            text = present[block]
            if _checksum(text) != known.get("checksum") and text and text != entry.text:
                if "[REDACTED" in text:
                    continue  # never write a mask back over the owner's words
                update_memory(
                    memory_id, workspace_root=workspace_root, text=text, store=store,
                    owner_principal_id=owner_principal_id,
                )
                store.record_memory_lifecycle_event(memory_id, "edit", owner_principal_id, {"source": "vault"})
                edited += 1
    added = _take_into_memory(store, root, workspace_root=workspace_root, owner_principal_id=owner_principal_id)
    written, _ = export_vault(store, root, owner_principal_id=owner_principal_id)
    return VaultSync(written=written, edited=edited, archived=archived, added=added)


def _take_into_memory(
    store: SQLiteStore, vault: Path, *, workspace_root: str | Path, owner_principal_id: str
) -> int:
    from raiker.memory.auto_keep import auto_keep_turn
    from raiker.memory.candidates import MemoryCandidate

    texts = _take_inbox(vault)
    if not texts:
        return 0
    turn = "vault_" + utc_now().replace(":", "").replace("-", "")
    for index, text in enumerate(texts):
        material = f"{owner_principal_id}\0{turn}\0{index}\0{text}"
        from raiker.memory.policy import classify_memory_sensitivity

        store.insert_memory_candidate(
            MemoryCandidate(
                candidate_id="memcand_" + hashlib.sha256(material.encode()).hexdigest()[:24],
                source_event_id="evt_vault", memory_type="fact", scope="user", text=text[:2_000],
                sensitivity=classify_memory_sensitivity(text).value, confidence=0.9,
                decision="deferred", created_at=utc_now(), source_session_id="vault",
                source_turn_id=turn, source_role=VAULT_ROLE,
                extractor_version=f"vault-inbox-v1#{index}",
            ),
            owner_principal_id=owner_principal_id,
        )
    summary = auto_keep_turn(
        store, workspace_root=workspace_root, owner_principal_id=owner_principal_id,
        session_id="vault", turn_id=turn,
    )
    return len(summary.kept)
