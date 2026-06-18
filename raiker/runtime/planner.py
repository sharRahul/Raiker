from __future__ import annotations

from dataclasses import dataclass

from raiker.contracts.ids import new_id
from raiker.runtime.classifier import Classification


@dataclass(frozen=True)
class PlanResult:
    required: bool
    event_type: str
    payload: dict[str, object]


class SimplePlanner:
    def create_or_skip(self, classification: Classification) -> PlanResult:
        if classification.requires_plan:
            return PlanResult(
                required=True,
                event_type="plan_created",
                payload={
                    "plan_id": new_id("task_"),
                    "summary": "Review policy, request approval where required, and avoid hidden execution.",
                    "steps": [
                        {
                            "step_id": "step_1",
                            "description": "Create policy-reviewed action proposal.",
                            "risk_level": classification.risk_level,
                        }
                    ],
                    "requires_approval": classification.intent
                    in {"local_action_request", "code_change_request"},
                },
            )
        return PlanResult(
            required=False,
            event_type="plan_skipped",
            payload={
                "reason": "single_safe_turn_or_read_only_query",
                "intent": classification.intent,
            },
        )
