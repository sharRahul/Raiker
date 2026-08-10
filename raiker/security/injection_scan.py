"""Deterministic prompt-injection scanning over untrusted context (BUG-81).

``docs/OWASP_GENAI_SECURITY_MAPPING.md`` states that Raiker must support
prompt-injection scanning hooks, and until this module none existed:
``raiker/runtime/classifier.py`` is an intent router, not a detector, and nothing
evaluated content at the point it entered the model's context.

What this is, and is not
------------------------
This is **detection and provenance**, not prevention. The structural controls do
the real work and are already in place — external content is framed as untrusted
data and never as instruction, and hijacked intent still has to cross a
deny-by-default tool gate. What was missing is the *advisory signal*: the owner
was never told that a fetched page or an attachment contained something shaped
like an injection attempt, so an attempt the gate correctly refused left no trace
naming its source.

So the refusal path stays the tool gate. A finding here never blocks a turn; it
raises a redacted ``security_findings`` row attributed to the exact source
document or URL, in the same vocabulary as :mod:`raiker.security.mcp_monitor`,
and it survives in the audit trail whether or not the model acted on it.

Every rule is a deterministic, explainable pattern with a stated name. There is
deliberately **no** probabilistic model-based filtering: the reference
architecture Raiker is measured against is explicit that prompt-level defence is
not a control surface, and a classifier that is right most of the time would
turn an advisory signal into a false assurance.

The redaction invariant holds as everywhere else: a finding records the rule
that matched, how many times, and the source's own locator — never the matched
text, and never the document.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.security.mcp_monitor import SecurityFinding

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

__all__ = [
    "INJECTION_RULES",
    "InjectionScanner",
    "InjectionSignal",
    "scan_untrusted_text",
]

SCANNER_SOURCE = "injection_scanner"

# How much of one source is scanned. A document larger than this is scanned at
# its head and tail: an injection payload is placed where a model will read it,
# and scanning a whole book to find one is not worth a turn's latency.
_SCAN_WINDOW_CHARS = 40_000

# Characters that carry no meaning for a reader but do for a tokenizer. Their
# presence in prose is the signal; the count is what the finding records.
_INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")


@dataclass(frozen=True)
class InjectionSignal:
    """One rule that matched, with a count. Never the text that matched."""

    rule: str
    description: str
    severity: str
    matches: int


@dataclass(frozen=True)
class _Rule:
    name: str
    description: str
    severity: str
    pattern: re.Pattern[str]


def _rule(name: str, description: str, severity: str, pattern: str) -> _Rule:
    return _Rule(name, description, severity, re.compile(pattern, re.IGNORECASE))


# Each rule names the *shape* of a known injection technique. They are ordered
# from the most-reported to the most specific, and every one of them is a phrase
# a legitimate document can also contain — which is exactly why a hit is a
# finding for the owner to read, not a refusal.
INJECTION_RULES: tuple[_Rule, ...] = (
    _rule(
        "instruction_override",
        "Text tries to cancel earlier instructions.",
        "high",
        r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b"
        r"(previous|prior|earlier|above|all)\b[^.\n]{0,20}\b(instruction|prompt|rule|direction)",
    ),
    _rule(
        "role_impersonation",
        "Text impersonates a system or developer turn.",
        "high",
        r"(^|\n)\s*(system|developer|assistant)\s*:\s|\byou are now\b|\bnew (system )?prompt\b",
    ),
    _rule(
        "secret_solicitation",
        "Text asks for credentials, keys, or the system prompt.",
        "high",
        r"\b(reveal|print|show|output|repeat|disclose)\b[^.\n]{0,40}\b"
        r"(system prompt|instructions|api[ _-]?key|token|password|secret|credential)",
    ),
    _rule(
        "exfiltration_request",
        "Text asks for content to be sent to an outside address.",
        "high",
        r"\b(send|post|upload|forward|exfiltrat\w*|transmit)\b[^.\n]{0,50}"
        r"(https?://|@[\w.-]+\.\w{2,}|\bwebhook\b)",
    ),
    _rule(
        "tool_coercion",
        "Text instructs the agent to run a tool or command.",
        "medium",
        r"\b(run|execute|invoke|call)\b[^.\n]{0,30}\b"
        r"(command|shell|tool|function|script|curl|wget|rm -rf)\b",
    ),
    _rule(
        "approval_bypass",
        "Text asks the agent to skip approval or act without asking.",
        "high",
        r"\b(without|skip|bypass|no need for|do not ask for)\b[^.\n]{0,30}\b"
        r"(approval|permission|confirmation|asking the user|the owner)",
    ),
    _rule(
        "hidden_instructions",
        "Instructions are hidden in a comment or marked not to be shown.",
        "medium",
        r"<!--[^>]{0,200}\b(ignore|instruction|prompt|system)\b|"
        r"\bdo not (show|tell|mention)\b[^.\n]{0,30}\b(user|owner|human)\b",
    ),
)


def scan_untrusted_text(text: str) -> list[InjectionSignal]:
    """Every rule that matches *text*, with counts. Deterministic and total.

    Returns an empty list for empty input and for text that matches nothing, so
    a caller can treat "no signals" as the normal case without a special branch.
    """
    if not text:
        return []
    window = (
        text
        if len(text) <= _SCAN_WINDOW_CHARS
        else text[: _SCAN_WINDOW_CHARS // 2] + "\n" + text[-(_SCAN_WINDOW_CHARS // 2) :]
    )
    signals = [
        InjectionSignal(
            rule=rule.name,
            description=rule.description,
            severity=rule.severity,
            matches=matches,
        )
        for rule in INJECTION_RULES
        if (matches := len(rule.pattern.findall(window))) > 0
    ]
    invisible = len(_INVISIBLE.findall(window))
    if invisible:
        signals.append(
            InjectionSignal(
                rule="invisible_characters",
                description="Text contains characters a reader cannot see but a model reads.",
                severity="medium",
                matches=invisible,
            )
        )
    return signals


class InjectionScanner:
    """Raises a redacted finding for untrusted context that looks like an attempt.

    Owner-scoped: every finding, notification and event is keyed by the owner
    whose turn read the content. One finding per source per scan — a page that
    trips four rules is one finding naming four rules, not four notifications.
    """

    def __init__(
        self,
        store: SQLiteStore,
        *,
        writer: EventLogWriter | None = None,
        notify: bool = True,
    ) -> None:
        self._store = store
        self._writer = writer or EventLogWriter(store)
        self._notify = notify

    def scan(
        self,
        principal_id: str,
        *,
        text: str,
        source_kind: str,
        locator: str,
        title: str = "",
        session_id: str = "",
        turn_id: str | None = None,
    ) -> SecurityFinding | None:
        """Scan one untrusted source; return the finding raised, if any."""
        signals = scan_untrusted_text(text)
        if not signals:
            return None
        severity = "high" if any(s.severity == "high" for s in signals) else "medium"
        name = title or locator or source_kind
        rules = sorted({signal.rule for signal in signals})
        detail: dict[str, Any] = {
            "source_kind": source_kind,
            "source_locator": locator[:500],
            "rules": rules,
            "matches": {signal.rule: signal.matches for signal in signals},
            "scanned_chars": min(len(text), _SCAN_WINDOW_CHARS),
        }
        summary = (
            f"Content from '{name}' contains text shaped like a prompt-injection attempt "
            f"({', '.join(rules)}). It was used as data, never as instructions."
        )
        finding_id = self._store.insert_security_finding(
            principal_id=principal_id,
            source=SCANNER_SOURCE,
            severity=severity,
            code="prompt_injection_suspected",
            summary=summary,
            redacted_detail=detail,
            subject_id=locator[:500] or source_kind,
        )
        self._writer.append(
            make_event(
                session_id=session_id or "security",
                turn_id=turn_id,
                event_type="prompt_injection_suspected",
                actor=SCANNER_SOURCE,
                payload={
                    "finding_id": finding_id,
                    "severity": severity,
                    **detail,
                },
            )
        )
        if self._notify:
            self._store.insert_notification(
                principal_id=principal_id,
                kind="anomaly",
                title="Suspicious content in a source this turn read",
                body=summary,
                finding_id=finding_id,
                subject_id=locator[:500] or source_kind,
            )
        return SecurityFinding(
            code="prompt_injection_suspected",
            severity=severity,
            summary=summary,
            detail=detail,
            finding_id=finding_id,
        )
