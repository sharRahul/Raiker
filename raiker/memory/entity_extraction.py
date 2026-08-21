"""Conservative, evidence-bound relationship extraction for approved memory."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from raiker.context.redaction import redact_text
from raiker.contracts.ids import new_id, utc_now
from raiker.memory.candidates import MemoryCandidate
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.storage.sqlite import SQLiteStore

EXTRACTOR_VERSION = "memory-entity-rules-v1"
MAX_CANDIDATES_PER_SOURCE = 5

_ENTITY = r"[A-Za-z0-9][A-Za-z0-9 _.'-]{0,78}[A-Za-z0-9]"


@dataclass(frozen=True)
class ExtractedRelationship:
    subject_name: str
    subject_type: str
    predicate: str
    object_name: str
    object_type: str
    confidence: float
    extractor_version: str = EXTRACTOR_VERSION


@dataclass(frozen=True)
class ExtractionSummary:
    scanned: int = 1
    proposed: int = 0
    skipped: int = 0
    already_present: int = 0


@dataclass(frozen=True)
class _Rule:
    predicate: str
    pattern: re.Pattern[str]
    subject_type: str
    object_type: str
    confidence: float
    strip_object_article: bool = False


def _rule(
    predicate: str,
    phrase: str,
    subject_type: str,
    object_type: str,
    confidence: float,
    *,
    strip_object_article: bool = False,
) -> _Rule:
    return _Rule(
        predicate,
        re.compile(rf"^(?P<subject>{_ENTITY})\s+{phrase}\s+(?P<object>{_ENTITY})$", re.I),
        subject_type,
        object_type,
        confidence,
        strip_object_article,
    )


_RULES = (
    _rule("married_to", r"is\s+married\s+to", "person", "person", 0.99),
    _rule("located_in", r"is\s+located\s+in", "entity", "location", 0.98),
    _rule("part_of", r"is\s+part\s+of", "entity", "entity", 0.98),
    _rule("works_on", r"works\s+on", "person", "project", 0.97),
    _rule("prefers", r"prefers", "person", "preference", 0.96),
    _rule("uses", r"uses", "entity", "tool", 0.96),
    _rule("is_a", r"is", "entity", "class", 0.94, strip_object_article=True),
)


def _clean(value: str) -> str:
    return " ".join(value.strip(" \t\r\n,;:").split())


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def extract_relationship_candidates(text: str) -> tuple[ExtractedRelationship, ...]:
    """Extract only explicit versioned predicates; ambiguity yields nothing."""

    _redacted, redaction_changed = redact_text(text)
    if redaction_changed or classify_memory_sensitivity(text) in {
        MemorySensitivity.SECRET_LIKE,
        MemorySensitivity.CREDENTIAL_LIKE,
    }:
        return ()
    extracted: list[ExtractedRelationship] = []
    seen: set[tuple[str, str, str]] = set()
    sentences = (_clean(item) for item in re.findall(r"[^.!?\n]+", text))
    for sentence in sentences:
        if not sentence:
            continue
        for rule in _RULES:
            matched = rule.pattern.fullmatch(sentence)
            if matched is None:
                continue
            subject = _clean(matched.group("subject"))
            object_name = _clean(matched.group("object"))
            if rule.strip_object_article:
                object_name = re.sub(r"^(?:a|an)\s+", "", object_name, flags=re.I)
            if not subject or not object_name or _normalized(subject) == _normalized(object_name):
                break
            key = (_normalized(subject), rule.predicate, _normalized(object_name))
            if key not in seen:
                seen.add(key)
                extracted.append(
                    ExtractedRelationship(
                        subject,
                        rule.subject_type,
                        rule.predicate,
                        object_name,
                        rule.object_type,
                        rule.confidence,
                    )
                )
            break
        if len(extracted) >= MAX_CANDIDATES_PER_SOURCE:
            break
    return tuple(extracted)


def propose_memory_relationships(
    store: SQLiteStore, memory_id: str, owner_principal_id: str
) -> ExtractionSummary:
    """Queue idempotent owner review candidates from one approved memory."""

    memory = store.get_active_approved_memory(
        memory_id, owner_principal_id=owner_principal_id
    )
    if memory is None:
        return ExtractionSummary(scanned=0, skipped=1)
    extracted = extract_relationship_candidates(str(memory["text"]))
    proposed = 0
    existing = 0
    for relation in extracted:
        created = store.create_memory_relationship_candidate(
            new_id("memcand_"),
            owner_principal_id=owner_principal_id,
            subject_name=relation.subject_name,
            subject_type=relation.subject_type,
            predicate=relation.predicate,
            object_name=relation.object_name,
            object_type=relation.object_type,
            evidence_memory_id=memory_id,
            confidence=relation.confidence,
            extractor_version=relation.extractor_version,
        )
        proposed += int(created)
        existing += int(not created)
    return ExtractionSummary(
        proposed=proposed,
        skipped=int(not extracted),
        already_present=existing,
    )


def propose_completed_turn_memories(
    store: SQLiteStore,
    *,
    owner_principal_id: str,
    session_id: str,
    turn_id: str,
    source_event_id: str,
    user_text: str,
    assistant_text: str,
) -> ExtractionSummary:
    """Create deferred, role-provenanced proposals from one completed turn."""

    proposed = 0
    skipped = 0
    already = 0
    for role, raw_text in (("user", user_text), ("assistant", assistant_text)):
        text = raw_text.strip()[:8_000]
        if not text or not extract_relationship_candidates(text):
            skipped += 1
            continue
        material = f"{owner_principal_id}\0{turn_id}\0{role}\0{EXTRACTOR_VERSION}"
        candidate_id = "memcand_" + hashlib.sha256(material.encode()).hexdigest()[:24]
        sensitivity = classify_memory_sensitivity(text).value
        created = store.insert_memory_candidate(
            MemoryCandidate(
                candidate_id=candidate_id,
                source_event_id=source_event_id,
                memory_type="project",
                scope="project",
                text=text,
                sensitivity=sensitivity,
                confidence=0.9,
                decision="deferred",
                created_at=utc_now(),
                source_session_id=session_id,
                source_turn_id=turn_id,
                source_role=role,
                extractor_version=EXTRACTOR_VERSION,
            ),
            owner_principal_id=owner_principal_id,
        )
        proposed += int(created)
        already += int(not created)
    return ExtractionSummary(
        scanned=2,
        proposed=proposed,
        skipped=skipped,
        already_present=already,
    )
