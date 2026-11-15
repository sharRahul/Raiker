"""ADR-0005 — composer personas: owner-scoped records the `@` menu offers.

Every write is an authenticated, human-only owner action, never a model tool.
A persona's tool ceiling is validated against known families, so a stored
persona can only ever narrow a turn (see ``raiker/personas.py``).
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, status

from raiker import personas
from raiker.api.dependencies import authenticate, refusal, require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import PersonaRequest, serialize_dto
from raiker.api.wire.personas import PersonaFamily, PersonaList, PersonaRemoved, PersonaView
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _caller(request: Request, *, human: bool) -> tuple[SQLiteStore, str]:
    _session, principal = authenticate(request)
    if human:
        require_human(principal)
    store = SQLiteStore(_ws(request))
    user_id = store.principal_user_id(principal.principal_id)
    if not user_id:
        raise refusal(status.HTTP_403_FORBIDDEN, "persona_user_unknown")
    return store, user_id


def _view(persona: personas.Persona) -> PersonaView:
    return cast(PersonaView, persona.public())


def _saved(action: Any) -> personas.Persona | None:
    try:
        return cast("personas.Persona | None", action())
    except personas.PersonaError as exc:
        code = exc.code
        status_code = (
            status.HTTP_409_CONFLICT if code in {"persona_name_taken", "too_many_personas"}
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise refusal(status_code, code) from None


@router.get("/api/personas")
async def list_personas(request: Request) -> dict[str, Any]:
    """The owner's personas, by name, and the families a ceiling may keep."""
    store, user_id = _caller(request, human=False)
    answer: PersonaList = {
        "personas": [_view(persona) for persona in personas.list_personas(store, user_id)],
        "families": [
            cast(PersonaFamily, {"family": name, "label": personas.FAMILY_LABELS[name]})
            for name in personas.FAMILIES
        ],
    }
    return serialize_dto(answer)


@router.post("/api/personas", status_code=status.HTTP_201_CREATED)
async def create_persona(body: PersonaRequest, request: Request) -> dict[str, Any]:
    """Add a persona. Its name must be free on this account."""
    store, user_id = _caller(request, human=True)
    created = _saved(lambda: personas.create_persona(store, user_id, body.model_dump()))
    assert created is not None
    answer: PersonaView = _view(created)
    return serialize_dto(answer)


@router.put("/api/personas/{persona_id}")
async def update_persona(persona_id: str, body: PersonaRequest, request: Request) -> dict[str, Any]:
    """Replace a persona. Turns it already answered keep the instructions' hash they ran with."""
    store, user_id = _caller(request, human=True)
    updated = _saved(lambda: personas.update_persona(store, user_id, persona_id, body.model_dump()))
    if updated is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_persona")
    answer: PersonaView = _view(updated)
    return serialize_dto(answer)


@router.delete("/api/personas/{persona_id}")
async def delete_persona(persona_id: str, request: Request) -> dict[str, Any]:
    """Remove a persona. Past turns keep their record of it."""
    store, user_id = _caller(request, human=True)
    if not personas.delete_persona(store, user_id, persona_id):
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_persona")
    answer: PersonaRemoved = {"ok": True, "persona_id": persona_id}
    return serialize_dto(answer)
