from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    intent: str
    confidence: float
    requires_tools: bool
    requires_plan: bool
    risk_level: str
    notes: str


class SimpleClassifier:
    def classify(self, prompt: str) -> Classification:
        text = prompt.strip().lower()
        if text.startswith("!") or any(
            term in text for term in ("run command", "execute command", "shell", "terminal command")
        ):
            return Classification(
                intent="local_action_request",
                confidence=0.9,
                requires_tools=True,
                requires_plan=True,
                risk_level="high",
                notes="Local machine action requested; approval required in Phase 1.",
            )
        if "list files" in text or "show files" in text or "list directory" in text:
            return Classification(
                intent="filesystem_query",
                confidence=0.86,
                requires_tools=True,
                requires_plan=False,
                risk_level="medium",
                notes="User asked to list files.",
            )
        if any(term in text for term in ("research", "investigate", "decompose")):
            return Classification(
                intent="research_request",
                confidence=0.75,
                requires_tools=True,
                requires_plan=True,
                risk_level="low",
                notes="Decomposable read-only research can use a bounded subagent.",
            )
        if (
            text.startswith("read file")
            or text.startswith("read ")
            or "grep" in text
            or "search" in text
        ):
            return Classification(
                intent="filesystem_query",
                confidence=0.75,
                requires_tools=True,
                requires_plan=False,
                risk_level="medium",
                notes="User asked for a workspace read/search.",
            )
        if "change code" in text or "edit file" in text or "write file" in text:
            return Classification(
                intent="code_change_request",
                confidence=0.7,
                requires_tools=True,
                requires_plan=True,
                risk_level="high",
                notes="Code/file change request is phase-scheduled for approval-gated write support.",
            )
        return Classification(
            intent="chat",
            confidence=0.9,
            requires_tools=False,
            requires_plan=False,
            risk_level="low",
            notes="Simple chat path.",
        )
