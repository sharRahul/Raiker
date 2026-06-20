from __future__ import annotations

import json
from typing import Any


class SkillCandidateStore:
    def __init__(self) -> None:
        self._candidates: list[dict[str, Any]] = []

    def propose(self, name: str, description: str, source_workflow: dict[str, Any], suggested_tools: list[str], provenance: str, created_by: str = "system") -> dict[str, Any]:
        from raiker.contracts.ids import new_id, utc_now
        candidate = {
            "candidate_id": new_id("skc_"),
            "name": name,
            "description": description,
            "source_workflow_json": json.dumps(source_workflow, sort_keys=True),
            "suggested_tools_json": json.dumps(suggested_tools, sort_keys=True),
            "provenance": provenance,
            "status": "proposed",
            "created_by": created_by,
            "created_at": utc_now(),
        }
        self._candidates.append(candidate)
        return candidate

    def list_candidates(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        if status_filter:
            return [c for c in self._candidates if c["status"] == status_filter]
        return list(self._candidates)

    def review(self, candidate_id: str, new_status: str) -> dict[str, Any] | None:
        for c in self._candidates:
            if c["candidate_id"] == candidate_id:
                c["status"] = new_status
                return c
        return None

    def clear(self) -> None:
        self._candidates.clear()

    @staticmethod
    def generate_from_pattern(pattern_name: str, tool_sequence: list[str], file_types: list[str], frequency: int) -> dict[str, Any]:
        workflow = {
            "pattern": pattern_name,
            "tool_sequence": tool_sequence,
            "file_types": file_types,
            "frequency": frequency,
        }
        return {
            "name": f"{pattern_name.lower().replace(' ', '_')}_skill",
            "description": f"Automated {pattern_name} workflow based on {frequency} observed repetitions",
            "workflow": workflow,
            "suggested_tools": tool_sequence,
        }
