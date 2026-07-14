from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from raiker.events.query import EventViewer
from raiker.storage.sqlite import SQLiteStore
from raiker.trace.models import (
    ModelCallSpan,
    PhaseSpan,
    ToolCallSpan,
    TurnTrace,
)

PHASE_NAMES: dict[str, str] = {
    "RECEIVED": "receive",
    "NORMALISED": "classify",
    "CLASSIFIED": "gather",
    "CONTEXT_READY": "plan",
    "PLAN_READY": "review",
    "PLAN_SKIPPED": "review",
    "POLICY_REVIEWED": "act",
    "EXECUTING": "act",
    "OBSERVING": "verify",
    "VERIFYING": "respond",
    "RESPONDING": "respond",
    "CHECKPOINTING": "finalize",
    "CLOSED": "done",
    "FAILED": "done",
    "CANCELLED": "done",
    "DENIED": "done",
    "PAUSED": "paused",
    "WAITING_FOR_APPROVAL": "wait_approval",
    "WAITING_FOR_USER": "wait_user",
}


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _compute_dur(start: str, end: str) -> float | None:
    s = _parse_ts(start)
    e = _parse_ts(end)
    if s is not None and e is not None:
        return (e - s).total_seconds() * 1000.0
    return None


def _format_duration(ms: float) -> str:
    if ms < 1000.0:
        return f"{ms:.0f}ms"
    return f"{ms / 1000.0:.2f}s"


def format_trace(trace: TurnTrace) -> str:
    lines = [
        f"Turn: {trace.turn_id}",
        f"Session: {trace.session_id}",
        f"Status: {trace.status}",
    ]
    if trace.prompt_preview is not None:
        lines.append(f"Prompt: {trace.prompt_preview}")
    lines.append(f"Duration: {_format_duration(trace.total_duration_ms)}")

    if trace.phases:
        lines.append("")
        lines.append("Phases:")
        for p in trace.phases:
            dur = _format_duration(p.duration_ms) if p.duration_ms is not None else "-"
            lines.append(f"  {p.name:15s} {dur:>8s}  {p.event_count} events")

    if trace.tool_calls:
        lines.append("")
        lines.append("Tool Calls:")
        for tc in trace.tool_calls:
            dur = _format_duration(tc.duration_ms) if tc.duration_ms is not None else "-"
            lines.append(f"  {tc.tool_name:25s} {dur:>8s}  {tc.status}")

    if trace.model_calls:
        lines.append("")
        lines.append("Model Requests:")
        for mc in trace.model_calls:
            dur = _format_duration(mc.duration_ms) if mc.duration_ms is not None else "-"
            tokens = ""
            if mc.prompt_tokens is not None and mc.completion_tokens is not None:
                tokens = f"  {mc.prompt_tokens}+{mc.completion_tokens} tokens"
            elif mc.prompt_tokens is not None:
                tokens = f"  {mc.prompt_tokens} tokens"
            lines.append(f"  {mc.model:25s} {dur:>8s}{tokens}")

    if trace.error is not None:
        lines.append("")
        lines.append(f"Error: {trace.error[:200]}")

    return "\n".join(lines)


def build_turn_trace(store: SQLiteStore, session_id: str, turn_id: str) -> TurnTrace | None:
    viewer = EventViewer(store)
    rows = viewer.list_events(session_id=session_id, turn_id=turn_id, limit=999)
    if not rows:
        return None

    events: list[dict[str, Any]] = []
    for row in rows:
        payload = viewer.read_event_payload(row["event_id"])
        if payload is not None:
            events.append(payload)

    if not events:
        return None

    events.sort(key=lambda e: e["timestamp"])

    state_changes = [ev for ev in events if ev["event_type"] == "turn_state_changed"]
    states_seen: set[str] = {s.get("payload", {}).get("to", "") for s in state_changes}

    error: str | None = None
    if "FAILED" in states_seen:
        status = "failed"
        for ev in events:
            if ev["event_type"] in ("error_recorded", "runtime_error_recorded"):
                error = str(ev.get("payload", {}).get("error", "")) or str(ev.get("payload", {}))
                break
    elif "DENIED" in states_seen:
        status = "denied"
    elif any(e["event_type"] == "response_created" for e in events):
        status = "completed"
    else:
        status = f"last:{events[-1]['event_type']}"

    first_ts = _parse_ts(events[0]["timestamp"])
    last_ts_dt = _parse_ts(events[-1]["timestamp"])
    total_duration: float = (
        (last_ts_dt - first_ts).total_seconds() * 1000.0
        if first_ts is not None and last_ts_dt is not None
        else 0.0
    )

    prompt_preview: str | None = None
    for ev in events:
        if ev["event_type"] == "prompt_received":
            preview = ev.get("payload", {}).get("preview", "")
            if preview:
                prompt_preview = str(preview)[:120]
            break

    phases: list[PhaseSpan] = []
    for i, change in enumerate(state_changes):
        to_state: str = change.get("payload", {}).get("to", "UNKNOWN")
        pname: str = PHASE_NAMES.get(to_state, to_state.lower())

        started_at = change["timestamp"]
        ended_at: str = (
            state_changes[i + 1]["timestamp"]
            if i + 1 < len(state_changes)
            else events[-1]["timestamp"]
        )
        duration = _compute_dur(started_at, ended_at)

        change_ts = _parse_ts(started_at)
        end_bound = (
            _parse_ts(state_changes[i + 1]["timestamp"])
            if i + 1 < len(state_changes)
            else last_ts_dt
        )
        count = 0
        for ev in events:
            ev_ts = _parse_ts(ev["timestamp"])
            if (
                ev_ts is not None
                and change_ts is not None
                and end_bound is not None
                and ev["event_type"] != "turn_state_changed"
                and change_ts <= ev_ts < end_bound
            ):
                count += 1

        phases.append(
            PhaseSpan(
                name=pname,
                state=to_state,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=duration,
                event_count=count,
            )
        )

    merged: list[PhaseSpan] = []
    for p in phases:
        if merged and merged[-1].name == p.name:
            merged[-1].ended_at = p.ended_at
            merged[-1].event_count += p.event_count
            if p.ended_at is not None:
                merged[-1].duration_ms = _compute_dur(merged[-1].started_at, p.ended_at)
        else:
            merged.append(p)

    tool_starts: dict[str, dict[str, Any]] = {}
    for ev in events:
        if ev["event_type"] == "tool_started":
            aid: str = ev.get("payload", {}).get("action_id", "")
            if aid:
                tool_starts[aid] = ev

    tool_spans: list[ToolCallSpan] = []
    for ev in events:
        et = ev["event_type"]
        pl = ev.get("payload", {})
        if et == "tool_completed" or et == "tool_failed":
            aid = pl.get("action_id", "")
            start = tool_starts.pop(aid, None)
            if start is not None:
                dur = _compute_dur(start["timestamp"], ev["timestamp"])
                is_fail = et == "tool_failed"
                tool_spans.append(
                    ToolCallSpan(
                        tool_name=start.get("payload", {}).get("tool_name", aid),
                        started_at=start["timestamp"],
                        ended_at=ev["timestamp"],
                        duration_ms=dur,
                        status="failed" if is_fail else pl.get("status", "success"),
                        tool_call_id=aid,
                    )
                )

    model_starts: deque[dict[str, Any]] = deque()
    for ev in events:
        if ev["event_type"] == "model_request_started":
            model_starts.append(ev)

    model_spans: list[ModelCallSpan] = []
    for ev in events:
        et = ev["event_type"]
        pl = ev.get("payload", {})
        if et == "model_request_completed":
            if model_starts:
                start = model_starts.popleft()
                dur = _compute_dur(start["timestamp"], ev["timestamp"])
                usage = pl.get("usage", {})
                if not isinstance(usage, dict):
                    usage = {}
                model_spans.append(
                    ModelCallSpan(
                        model=start.get("payload", {}).get("model", ""),
                        started_at=start["timestamp"],
                        ended_at=ev["timestamp"],
                        duration_ms=dur,
                        prompt_tokens=usage.get("input_tokens"),
                        completion_tokens=usage.get("output_tokens"),
                    )
                )
        elif et == "model_request_failed" and model_starts:
            start = model_starts.popleft()
            dur = _compute_dur(start["timestamp"], ev["timestamp"])
            model_spans.append(
                ModelCallSpan(
                    model=start.get("payload", {}).get("model", ""),
                    started_at=start["timestamp"],
                    ended_at=ev["timestamp"],
                    duration_ms=dur,
                )
            )

    return TurnTrace(
        session_id=session_id,
        turn_id=turn_id,
        status=status,
        prompt_preview=prompt_preview,
        total_duration_ms=total_duration,
        phases=merged,
        tool_calls=tool_spans,
        model_calls=model_spans,
        error=error,
    )
