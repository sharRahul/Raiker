"""Suspending and resuming a turn across an approval (B2).

Before this, the agent loop `break`ed on `needs_approval` and the turn returned.
Even once an approved write really executed (BUG-06 / FIXED-08), the agent
stopped dead at its first write: the owner had to re-prompt, which discarded the
model's working state and re-paid for the whole context. That is the difference
between a proposal generator and an agent.

This module holds the two halves of the fix that are pure data:

* **serialisation** — turning the in-flight `ModelMessage` list into something
  the encrypted store can hold, and back again, without losing tool-call
  identity (a `tool` message is only valid against the `assistant` message whose
  `tool_calls` carry the same `call_id`);
* **the pending-call queue** (ADD-02) — the rest of the model's batch. A batch of
  three mutations used to stop at the first one and drop the other two; the
  queue parks them with the turn so the owner walks the whole batch one decision
  at a time and a refusal skips its own call instead of ending the turn;
* **the resolution outcome** — the tool result the model is handed when the turn
  resumes. Approved-and-executed replays the real executor result; approved but
  not executed, and rejected, are stated honestly so the model reacts to what
  actually happened rather than assuming success.

The stored conversation never leaves the machine through an API response: the
resume endpoints return an `AgentResponse` only.
"""

from __future__ import annotations

import json
from typing import Any

from raiker.models.contracts import ModelImage, ModelMessage, ToolCallProposal

# A turn's parked state is transcript-sized, not archive-sized. A conversation
# that cannot be re-sent to a provider anyway is not worth storing: suspension
# fails closed (the turn simply cannot be resumed) rather than writing a blob
# that would fail at resume time.
MAX_SUSPENDED_MESSAGES_BYTES = 4_000_000


class TurnSuspensionError(ValueError):
    """The parked state is unusable, so the turn cannot be resumed."""


def serialize_messages(messages: list[ModelMessage]) -> str:
    """Serialise the in-flight conversation, preserving tool-call identity."""
    payload: list[dict[str, Any]] = []
    for message in messages:
        entry: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.name is not None:
            entry["name"] = message.name
        if message.tool_call_id is not None:
            entry["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            entry["tool_calls"] = [
                {
                    "call_id": call.call_id,
                    "tool_name": call.tool_name,
                    "arguments": call.arguments,
                }
                for call in message.tool_calls
            ]
        if message.images:
            # Attached images are part of what the model was reasoning about;
            # dropping them would silently change the task on resume.
            entry["images"] = [
                {"media_type": image.media_type, "base64_data": image.base64_data}
                for image in message.images
            ]
        payload.append(entry)
    encoded = json.dumps(payload, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_SUSPENDED_MESSAGES_BYTES:
        raise TurnSuspensionError("suspended_turn_too_large")
    return encoded


def deserialize_messages(raw: str) -> list[ModelMessage]:
    """Rebuild the conversation. Any malformed row fails closed."""
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise TurnSuspensionError("suspended_turn_unreadable") from exc
    if not isinstance(payload, list):
        raise TurnSuspensionError("suspended_turn_unreadable")
    messages: list[ModelMessage] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise TurnSuspensionError("suspended_turn_unreadable")
        raw_calls = entry.get("tool_calls") or []
        raw_images = entry.get("images") or []
        try:
            messages.append(
                ModelMessage(
                    role=str(entry.get("role", "")),
                    content=str(entry.get("content", "")),
                    name=entry.get("name"),
                    tool_call_id=entry.get("tool_call_id"),
                    images=tuple(
                        ModelImage(
                            media_type=str(image.get("media_type", "")),
                            base64_data=str(image.get("base64_data", "")),
                        )
                        for image in raw_images
                    ),
                    tool_calls=tuple(
                        ToolCallProposal(
                            call_id=str(call.get("call_id", "")),
                            tool_name=str(call.get("tool_name", "")),
                            arguments=dict(call.get("arguments") or {}),
                        )
                        for call in raw_calls
                    ),
                )
            )
        except Exception as exc:  # ModelContractError and friends
            raise TurnSuspensionError("suspended_turn_unreadable") from exc
    if not messages:
        raise TurnSuspensionError("suspended_turn_unreadable")
    return messages


def serialize_pending_calls(calls: list[ToolCallProposal]) -> str:
    """Serialise the rest of the model's batch so it survives the pause (ADD-02).

    Only the three fields a call *is* — its id, its tool, and its arguments. A
    queued call is re-validated and re-governed when it is drained, so nothing
    about the earlier decision is carried forward with it; that is the point of
    holding the proposal rather than a half-evaluated action.
    """
    return json.dumps(
        [
            {
                "call_id": call.call_id,
                "tool_name": call.tool_name,
                "arguments": call.arguments,
            }
            for call in calls
        ],
        separators=(",", ":"),
    )


def deserialize_pending_calls(raw: str | None) -> list[ToolCallProposal]:
    """Rebuild the queued calls. An unreadable queue drains to nothing.

    Deliberately softer than :func:`deserialize_messages`: a conversation that
    cannot be rebuilt makes the turn unresumable, but a queue that cannot be
    rebuilt only costs the calls behind the decision the owner already made.
    Failing the whole resume over it would throw away a real approval, so the
    turn continues with an empty queue and the model asks again if it still
    wants them.
    """
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(payload, list):
        return []
    calls: list[ToolCallProposal] = []
    for entry in payload:
        if not isinstance(entry, dict):
            return []
        try:
            calls.append(
                ToolCallProposal(
                    call_id=str(entry.get("call_id", "")),
                    tool_name=str(entry.get("tool_name", "")),
                    arguments=dict(entry.get("arguments") or {}),
                )
            )
        except Exception:  # ModelContractError and friends
            return []
    return calls


def queued_denial_outcome(*, tool_name: str, reasons: list[str]) -> dict[str, Any]:
    """The tool result for a queued call policy refused while draining (ADD-02).

    A denial inside a batch skips its own call and the queue carries on, so the
    model has to be able to tell "this one was refused" apart from "the turn
    ended". Stated as a refusal of *this* call, naming the tool, so the model
    does not read it as a verdict on the calls after it.
    """
    return {
        "status": "denied",
        "executed": False,
        "tool_name": tool_name,
        "reasons": reasons,
        "note": (
            "Policy refused this call, so it did not run. The other calls in this "
            "batch were decided separately — do not assume they were refused too."
        ),
    }


def approval_outcome(
    *,
    approved: bool,
    executed: bool,
    capability: str = "",
    artifacts: dict[str, Any] | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    """The tool result the model is handed when the turn resumes.

    Three genuinely different things happened, and the model has to be able to
    tell them apart — a rejection it must not retry, an approval that ran, and an
    approval that was recorded but deliberately not executed for this capability.
    """
    if not approved:
        return {
            "status": "rejected",
            "executed": False,
            "note": (
                "The owner rejected this action, so it did not run. Do not propose "
                "the same action again; explain the situation or take a different "
                "approach."
            ),
        }
    if executed:
        return {
            "status": "success",
            "executed": True,
            "capability": capability,
            **(artifacts or {}),
            "note": "The owner approved this action and it was executed once.",
        }
    return {
        "status": "not_executed",
        "executed": False,
        "capability": capability,
        **({"reason_code": reason_code} if reason_code else {}),
        "note": (
            "The owner approved this action, but Raiker records approvals for this "
            "capability without performing them, so nothing ran. Do not assume the "
            "effect happened."
        ),
    }
