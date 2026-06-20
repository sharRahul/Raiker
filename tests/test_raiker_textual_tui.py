from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from textual.pilot import Pilot

from raiker.contracts.models import AgentResponse, PromptEnvelope
from raiker.contracts.streaming import FINAL, LIFECYCLE, TEXT_DELTA, StreamEvent
from raiker.tui.accessibility import TerminalProfile
from raiker.tui.textual_app import RaikerTextualApp, Transcript


class FakeStreamingGateway:
    def __init__(self, chunks: Sequence[str], *, workspace_root: Path | None = None) -> None:
        self.chunks = list(chunks)
        self.workspace_root = workspace_root or Path(".")
        self.received_prompts: list[str] = []

    async def astream_prompt(self, envelope: PromptEnvelope) -> AsyncIterator[StreamEvent]:
        self.received_prompts.append(envelope.prompt.text)
        for chunk in self.chunks:
            yield StreamEvent(kind=TEXT_DELTA, text=chunk)
        yield StreamEvent(kind=LIFECYCLE, event_type="responding", payload={})
        assembled = "".join(self.chunks)
        yield StreamEvent(
            kind=FINAL,
            response=AgentResponse(
                request_id="req_test",
                session_id="sess_test",
                turn_id="turn_test",
                status="completed",
                message=assembled,
                events_path="events.jsonl",
                checkpoint_path="ckpt.json",
            ),
        )


def _profile() -> TerminalProfile:
    return TerminalProfile(width=120, color=False, unicode=True, interactive=True)


def _capture_transcript(app: RaikerTextualApp) -> str:
    return app._transcript_text()


async def _drain(app: RaikerTextualApp, pilot: Pilot, rounds: int = 30) -> None:
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(0.01)


def test_welcome_screen_renders_with_logo() -> None:
    async def main() -> str:
        app = RaikerTextualApp(workspace_root=Path("."), profile=_profile())
        async with app.run_test() as pilot:
            await pilot.pause()
            return _capture_transcript(app)

    text = asyncio.run(main())
    assert "-----------" in text
    assert "Raiker" in text
    assert "Type a prompt" in text


def test_first_prompt_replaces_welcome_with_transcript() -> None:
    gateway = FakeStreamingGateway(["Hel", "lo", " world"])

    async def main() -> tuple[str, bool]:
        app = RaikerTextualApp(
            workspace_root=Path("."),
            profile=_profile(),
            streaming_gateway=gateway,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            welcome_before = app._show_welcome
            await pilot.press(*list("hello"))
            await pilot.press("enter")
            await _drain(app, pilot)
            welcome_after = app._show_welcome
            text = _capture_transcript(app)
            return text, welcome_before and not welcome_after

    text, transitioned = asyncio.run(main())
    assert transitioned
    assert "hello" in text
    assert "Type a prompt" not in text


def test_streamed_deltas_assemble_into_transcript() -> None:
    chunks = ["Ra", "iker", " streams", " live"]
    gateway = FakeStreamingGateway(chunks)

    async def main() -> tuple[str, list[str]]:
        app = RaikerTextualApp(
            workspace_root=Path("."),
            profile=_profile(),
            streaming_gateway=gateway,
        )
        async with app.run_test() as pilot:
            await pilot.press(*list("prompt"))
            await pilot.press("enter")
            await _drain(app, pilot)
            return _capture_transcript(app), gateway.received_prompts

    text, received = asyncio.run(main())
    assert received == ["prompt"]
    assert "".join(chunks) in text


def test_quit_exits_cleanly() -> None:
    async def main() -> bool:
        app = RaikerTextualApp(workspace_root=Path("."), profile=_profile())
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*list("quit"))
            await pilot.press("enter")
            await pilot.pause()
            return app.is_running

    still_running = asyncio.run(main())
    assert not still_running


def test_slash_command_routes_through_handler(tmp_path: Path) -> None:
    captured: list[str] = []

    def fake_slash(command: str, *, workspace_root) -> str:
        captured.append(command)
        return f"ran {command}"

    async def main() -> str:
        app = RaikerTextualApp(
            workspace_root=tmp_path,
            profile=_profile(),
            slash_handler=fake_slash,
        )
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*list("status"))
            await pilot.press("enter")
            await pilot.pause()
            return _capture_transcript(app)

    text = asyncio.run(main())
    assert captured == ["/status"]
    assert "ran /status" in text
