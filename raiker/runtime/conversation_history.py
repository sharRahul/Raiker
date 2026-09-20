"""Prior turns of a conversation, rebuilt for the model.

Before this existed, every turn was sent to the provider as a single-shot
request: the transcript rendered on screen but the model never saw it, so asking
a follow-up produced "this is the first message in our current session".

The persisted ``turns`` rows are the conversation record — ``prompt_text`` is
what the user said, ``summary`` is what Raiker replied — and they are the same
rows the Chat view hydrates from, so what the model sees and what the user sees
come from one source.

Two things this module must never do quietly, because both look exactly like an
ordinary first turn from inside the model:

* **GCR-35** — return *no* history because the newest exchange alone is larger
  than the whole budget. The budget exists to drop the oldest context first; an
  exchange that cannot fit is elided to fit rather than taking every older
  exchange down with it.
* **GCR-36** — return *no* history because the transcript could not be read. A
  storage failure is a different fact from an empty conversation, and it leaves
  here as :class:`ConversationHistoryUnavailable` so the caller can say so.
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

# Written into an exchange that had to be cut down to fit. The model is told the
# text is incomplete rather than left to read a sentence that stops mid-word as
# though that were what was said.
_ELISION = "\n[… {dropped} characters elided to fit the conversation budget …]\n"


class ConversationHistoryUnavailable(RuntimeError):
    """The transcript could not be read, which is not the same as empty.

    ``reason`` is a stable code the caller can record and show. Raised instead
    of returning ``[]`` so a storage failure cannot reach the model disguised as
    a conversation that never happened.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def history_char_budget(context_window_tokens: int | None) -> int:
    """How many characters of prior conversation may be replayed."""
    if not context_window_tokens or context_window_tokens <= 0:
        return _DEFAULT_HISTORY_CHARS
    return int(context_window_tokens * _HISTORY_BUDGET_FRACTION * _CHARS_PER_TOKEN)


def elide_to_fit(text: str, allowance: int) -> str:
    """*text* cut to *allowance* characters, saying how much was taken out.

    The head and the tail both survive: an oversized prompt is usually a pasted
    document with the actual instruction at the end, and an oversized reply
    usually answers at the start. Keeping only one end would reliably lose one
    of the two.
    """
    if allowance <= 0:
        return ""
    if len(text) <= allowance:
        return text
    dropped = len(text) - allowance
    marker = _ELISION.format(dropped=dropped)
    if len(marker) >= allowance:
        # No room to explain the cut; a bare truncation is all that fits.
        return text[:allowance]
    # The marker is itself part of the allowance, so it displaces text too.
    remaining = allowance - len(marker)
    dropped = len(text) - remaining
    marker = _ELISION.format(dropped=dropped)
    remaining = max(allowance - len(marker), 0)
    head = remaining // 2
    tail = remaining - head
    return text[:head] + marker + (text[len(text) - tail :] if tail else "")


def fit_exchange(prompt: str, reply: str, budget: int) -> tuple[str, str]:
    """One exchange cut down to *budget* characters, both halves surviving.

    Each side is offered half the budget; whatever one side does not use is
    handed to the other, so a short question with an enormous answer keeps the
    question whole.
    """
    half = budget // 2
    prompt_allowance = half if len(prompt) > half else len(prompt)
    reply_allowance = budget - prompt_allowance
    if len(reply) < reply_allowance:
        prompt_allowance = budget - len(reply)
        reply_allowance = len(reply)
    return elide_to_fit(prompt, prompt_allowance), elide_to_fit(reply, reply_allowance)


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
    recent context is what a follow-up question depends on. When the newest
    exchange *alone* is over the budget it is elided down to it rather than
    dropped, because dropping it drops everything (GCR-35).

    Raises :class:`ConversationHistoryUnavailable` when the transcript cannot be
    read at all (GCR-36).
    """
    if store is None or not session_id:
        return []
    try:
        rows = store.list_turns(session_id, limit=max_turns)
    except Exception as exc:  # noqa: BLE001 — every read failure is one condition
        raise ConversationHistoryUnavailable(
            f"conversation_history_unreadable:{type(exc).__name__}"
        ) from exc

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
            if kept:
                # Something newer already fits; stopping here is the oldest-first
                # drop the budget is for, and it leaves no gap in the middle.
                break
            # GCR-35 — this is the newest exchange and it does not fit on its
            # own. Breaking would send the model a conversation it can see on
            # screen and cannot read, so it is cut down to the budget instead.
            prompt, reply = fit_exchange(prompt, reply, char_budget)
            if not prompt and not reply:
                break
            kept.append((prompt, reply))
            break
        kept.append((prompt, reply))
        used += cost
    kept.reverse()

    messages: list[ModelMessage] = []
    for prompt, reply in kept:
        messages.append(ModelMessage(role="user", content=prompt))
        messages.append(ModelMessage(role="assistant", content=reply))
    return messages
