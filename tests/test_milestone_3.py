from __future__ import annotations

from raiker.runtime.classifier import SimpleClassifier
from raiker.runtime.planner import SimplePlanner


def test_planner_emits_readonly_subagent_plan_for_research() -> None:
    classification = SimpleClassifier().classify("research the codebase for this task")

    plan = SimplePlanner().create_or_skip(classification)

    assert plan.required is True
    assert plan.payload["steps"] == [
        {
            "step_id": "subagent_plan",
            "action_type": "subagent_plan",
            "description": "Run a bounded read-only research subagent.",
            "risk_level": "low",
        }
    ]
