"""Run an executor as ``RuntimeAuthority.route_action`` runs it (CR-03).

An executor test that calls ``execute`` directly is standing in for the router,
which has already applied the gate, the decision mode and the approval. Since
CR-03 the services behind the executors skip those only for the router's live
dispatch token, so a test that means "as routed" says so here, and a test that
calls ``execute`` bare is testing the direct path — which now governs.
"""
from __future__ import annotations

from typing import Any

from raiker.runtime.authority.routed import routed_dispatch


def execute_as_routed(executor: Any, action: Any, principal: Any) -> Any:
    with routed_dispatch(executor.capability, action.action_id):
        return executor.execute(action, principal)
