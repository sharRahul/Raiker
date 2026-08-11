"""Prior turns of a conversation, rebuilt for the model.

Before this existed, every turn was sent to the provider as a single-shot
request: the transcript rendered on screen but the model never saw it, so asking
a follow-up produced "this is the first message in our current session".

The persisted ``turns`` rows are the conversation record — ``prompt_text`` is
what the user said, ``summary`` is what Raiker replied — and they are the same
rows the Chat view hydrates from, so what the model sees and what the user sees
come from one source.
"""

from __future__ import annotations

from typing import Any

from raiker.models.contracts import ModelMessage

# Roughly four characters per token. Deliberately coarse: this bounds how much
# history is replayed, and erring small costs a little recall while erring large
# costs a hard provider rejection mid-conversation.
_CHARS_PER_TOKEN = 4

# Share of a known context window history may occupy. The rest is left for the
# system prompt, workspace context, retrieved context, the new prompt, and the
# reply itself.
_HISTORY_BUDGET_FRACTION = 0.5

# Used when the model's capacity is unknown. Small enough to be safe against the
# most modest local model, since guessing high would break the turn outright.
_DEFAULT_HISTORY_CHARS = 24_000


def history_char_budget(context_window_tokens: int | None) -> int:
    """How many characters of prior conversation may be replayed."""
    if not context_window_tokens or context_window_tokens <= 0:
        return _DEFAULT_HISTORY_CHARS
    return int(context_window_tokens * _HISTORY_BUDGET_FRACTION * _CHARS_PER_TOKEN)


def conversation_messages(
    store: Any,
    session_id: str,
    *,
    exclude_turn_id: str | None = None,
    char_budget: int = _DEFAULT_HISTORY_CHARS,
    max_turns: int = 50,
) -> list[ModelMessage]:
    """Prior completed exchanges for *session_id*, oldest first.

    Only exchanges that actually completed are replayed — a turn with no reply
    (still running, failed, or awaiting approval) would otherwise put a user
    message into the transcript that the model never answered, which reads to it
    as an unanswered question and skews the next reply.

    When the budget cannot fit everything, the **oldest** exchanges are dropped:
    recent context is what a follow-up question depends on.
    """
    if store is None or not session_id:
        return []
    try:
        rows = store.list_turns(session_id, limit=max_turns)
    except Exception:  # noqa: BLE001 — history is best effort, never fatal
        return []

    exchanges: list[tuple[str, str]] = []
    for row in rows:
        if exclude_turn_id and str(row.get("turn_id") or "") == exclude_turn_id:
            continue
        if str(row.get("status") or "") != "completed":
            continue
        prompt = str(row.get("prompt_text") or "").strip()
        reply = str(row.get("summary") or "").strip()
        if not prompt or not reply:
            continue
        exchanges.append((prompt, reply))

    # Walk newest → oldest so the budget keeps the most recent context, then
    # restore chronological order for the provider.
    kept: list[tuple[str, str]] = []
    used = 0
    for prompt, reply in reversed(exchanges):
        cost = len(prompt) + len(reply)
        if used + cost > char_budget:
            break
        kept.append((prompt, reply))
        used += cost
    kept.reverse()

    messages: list[ModelMessage] = []
    for prompt, reply in kept:
        messages.append(ModelMessage(role="user", content=prompt))
        messages.append(ModelMessage(role="assistant", content=reply))
    return messages
