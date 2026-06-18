from __future__ import annotations

import re
from enum import StrEnum


class MemorySensitivity(StrEnum):
    PUBLIC = "public"
    PROJECT = "project"
    PERSONAL = "personal"
    SECRET_LIKE = "secret_like"
    CREDENTIAL_LIKE = "credential_like"
    UNKNOWN = "unknown"


CREDENTIAL_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bbearer\s+[a-z0-9._\-]{16,}", re.IGNORECASE),
    re.compile(r"\b(password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", re.IGNORECASE),
    re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s:@]+:[^\s@]+@[^\s]+"),
)
SECRET_PATTERNS = (
    re.compile(r"\b[A-Za-z0-9_\-]{40,}\b"),
    re.compile(r"\bsecret\b", re.IGNORECASE),
)
PERSONAL_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(phone|address|ssn|personal)\b", re.IGNORECASE),
)
PROJECT_PATTERNS = (re.compile(r"\b(project|repo|workspace|raiker)\b", re.IGNORECASE),)
PUBLIC_PATTERNS = (re.compile(r"\b(public|documentation|docs|readme)\b", re.IGNORECASE),)


def classify_memory_sensitivity(text: str) -> MemorySensitivity:
    value = text.strip()
    if not value:
        return MemorySensitivity.UNKNOWN
    if any(pattern.search(value) for pattern in CREDENTIAL_PATTERNS):
        return MemorySensitivity.CREDENTIAL_LIKE
    if any(pattern.search(value) for pattern in SECRET_PATTERNS):
        return MemorySensitivity.SECRET_LIKE
    if any(pattern.search(value) for pattern in PERSONAL_PATTERNS):
        return MemorySensitivity.PERSONAL
    if any(pattern.search(value) for pattern in PROJECT_PATTERNS):
        return MemorySensitivity.PROJECT
    if any(pattern.search(value) for pattern in PUBLIC_PATTERNS):
        return MemorySensitivity.PUBLIC
    return MemorySensitivity.UNKNOWN


def semantic_write_policy_decision(sensitivity: str) -> tuple[bool, list[str]]:
    reasons = ["phase3_semantic_vector_writes_disabled", "no_embeddings_created"]
    if sensitivity in {
        MemorySensitivity.SECRET_LIKE.value,
        MemorySensitivity.CREDENTIAL_LIKE.value,
    }:
        reasons.append("secret_or_credential_like_candidate_blocked")
    return False, reasons
