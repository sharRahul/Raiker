from __future__ import annotations

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import AgentEvent, ClientMetadata


def make_event(
    *,
    session_id: str,
    turn_id: str | None,
    event_type: str,
    actor: str,
    payload: dict[str, object] | None = None,
    client: ClientMetadata | None = None,
    parent_event_id: str | None = None,
) -> AgentEvent:
    event_payload: dict[str, object] = dict(payload or {})
    if client is not None:
        event_payload.setdefault(
            "client",
            {
                "type": client.type,
                "name": client.name,
                "version": client.version,
                "interface_status": client.interface_status,
            },
        )
    return AgentEvent(
        event_id=new_id("evt_"),
        timestamp=utc_now(),
        session_id=session_id,
        turn_id=turn_id,
        event_type=event_type,
        actor=actor,
        payload=event_payload,
        parent_event_id=parent_event_id,
    )
