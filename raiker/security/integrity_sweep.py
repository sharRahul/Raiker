"""Metadata-only ZT-4 integrity checks, run through scheduled routines."""

from __future__ import annotations

import json
from typing import Any

from raiker.api.sessions import ApiSessionStore
from raiker.events.integrity import verify_session_events
from raiker.models.endpoint_policy import model_egress_allowlist
from raiker.runtime.executors.sandbox import (
    channel_egress_allowlist,
    connector_egress_allowlist,
)
from raiker.storage.sqlite import SQLiteStore

_BASELINE_KEY = "integrity_sweep_baseline"


class IntegritySweep:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    def _posture(self, principal_id: str) -> dict[str, object]:
        return {
            "gates": {
                str(row["capability"]): str(row["state"])
                for row in self._store.list_principal_capability_gate_states(principal_id)
            },
            "decision_modes": self._store.list_principal_capability_decision_modes(principal_id),
            "egress_allowlists": {
                "model": sorted(model_egress_allowlist()),
                "connector": sorted(connector_egress_allowlist()),
                "channel": sorted(channel_egress_allowlist()),
            },
        }

    def _baseline(self, principal_id: str, posture: dict[str, object]) -> dict[str, object]:
        row = self._store.get_user_settings(principal_id)
        try:
            settings: dict[str, Any] = json.loads(str(row["settings_json"])) if row else {}
        except (TypeError, ValueError):
            settings = {}
        baseline = settings.get(_BASELINE_KEY)
        if isinstance(baseline, dict):
            return baseline
        settings[_BASELINE_KEY] = posture
        from raiker.contracts.ids import utc_now

        self._store.put_user_settings(principal_id, json.dumps(settings, sort_keys=True), utc_now())
        return posture

    def run(self, principal_id: str) -> dict[str, object]:
        posture = self._posture(principal_id)
        baseline = self._baseline(principal_id, posture)
        deviations: list[dict[str, object]] = []
        for field, kind in (("gates", "gate_mode_drift"), ("decision_modes", "gate_mode_drift"),
                            ("egress_allowlists", "egress_allowlist_drift")):
            if baseline.get(field) != posture.get(field):
                deviations.append({"kind": kind, "field": field})
        for session_row in self._store.list_sessions(limit=100_000, include_archived=True):
            verification = verify_session_events(self._store, str(session_row["session_id"]))
            if verification["failed"] or not verification["chain_intact"]:
                deviations.append({"kind": "event_chain", "session_id": session_row["session_id"]})
        for row in ApiSessionStore(self._store.paths.workspace_root).list_sessions():
            api_session = ApiSessionStore(self._store.paths.workspace_root).get_by_session_id(
                str(row["session_id"])
            )
            if api_session is not None and (api_session.revoked or api_session.is_expired()):
                deviations.append({"kind": "session_invalid", "session_id": api_session.session_id})
        if deviations:
            from raiker.notify.approval_notifier import notify_integrity_deviation

            notify_integrity_deviation(self._store, principal_id, len(deviations))
        return {"principal_id": principal_id, "deviations": deviations}
