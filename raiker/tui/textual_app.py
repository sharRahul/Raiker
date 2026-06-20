"""Native Raiker TUI built on Textual.

A single scrolling transcript (user prompts, streamed assistant replies, inline
collapsible tool blocks), a docked input box at the bottom, and a thin
configurable status bar. A welcome screen with the Raiker cloud logo is shown
until the user's first prompt, then replaced by the transcript.

This shell adds no runtime authority. Prompts route through the existing
``AgentGateway.astream_prompt`` (real provider when configured, safe
``model_unavailable`` result otherwise) and slash commands route through the
existing ``handle_slash_command``. No tool, model, plugin, channel, socket, or
process is opened directly from this module.

The Textual framework is the load-bearing interactive renderer. The plain
line-oriented fallback (``RAIKER_TUI=plain``, ``--prompt``, non-interactive
stdin) lives in ``raiker.tui.app`` and does not use Textual.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Input, RichLog, Static

from raiker.contracts.streaming import FINAL, LIFECYCLE, TEXT_DELTA, StreamEvent
from raiker.tui.accessibility import TerminalProfile, ascii_safe
from raiker.tui.command_palette import render_command_palette
from raiker.tui.status_bar import StatusBarRenderer, StatusContext
from raiker.tui.welcome import WelcomeContent, logo_lines, welcome_left_lines

if TYPE_CHECKING:
    from raiker.contracts.models import PromptEnvelope

_WELCOME_TIPS: tuple[str, ...] = (
    "Type a prompt and press Enter to start a turn.",
    "Use /commands to browse slash commands. /quit exits.",
    "? prefix asks a side question. / prefix runs a slash command.",
    "Runtime execution remains disabled; tool blocks are read-only views.",
)

_PALETTE_COMMANDS = {"/commands", "/palette"}
_EXIT_COMMANDS = {"/q", "/quit", "/exit"}


def _welcome_banner(profile: TerminalProfile) -> str:
    """Render the welcome screen (logo orb + greeting + tips) as one string."""

    content = WelcomeContent(whats_new=_WELCOME_TIPS, returning=False)
    left = welcome_left_lines(content, profile)
    lines = list(left)
    lines.append("")
    lines.append("Tips for getting started")
    for tip in content.whats_new:
        lines.append(f"  {tip}")
    if not profile.unicode:
        lines = [ascii_safe(line) for line in lines]
    return "\n".join(lines)


def _logo_only(profile: TerminalProfile) -> str:
    lines = list(logo_lines(profile))
    if not profile.unicode:
        lines = [ascii_safe(line) for line in lines]
    return "\n".join(lines)


class _Transcript(RichLog):
    """The single scrolling transcript region."""

    DEFAULT_CSS = """
    _Transcript {
        border: round $primary;
        height: 1fr;
        width: 1fr;
        padding: 0 1;
    }
    _Transcript:focus {
        border: round $accent;
    }
    """

    def __init__(self, profile: TerminalProfile) -> None:
        super().__init__(markup=False, highlight=False, wrap=True, auto_scroll=True)
        self.profile = profile


class _StatusBar(Static):
    """Thin docked status/help bar."""

    DEFAULT_CSS = """
    _StatusBar {
        dock: bottom;
        height: 1;
        padding: 0 1;
    }
    """

    def setup(self, profile: TerminalProfile) -> None:
        self.profile = profile
        self.renderer = StatusBarRenderer()
        self._status_context = StatusContext()

    def update_context(self, context: StatusContext) -> None:
        self._status_context = context
        self._refresh()

    def _refresh(self) -> None:
        line = self.renderer.render(
            self._status_context,
            compact=self.profile.narrow,
            width=self.profile.width,
        )
        self.update(ascii_safe(line) if not self.profile.unicode else line)


class _DockedInput(Input):
    """Input box docked just above the status bar."""

    DEFAULT_CSS = """
    _DockedInput {
        dock: bottom;
        height: 3;
        border: round $primary;
        margin: 0;
        padding: 0 1;
    }
    _DockedInput:focus {
        border: round $accent;
    }
    """


class RaikerTextualApp(App):
    """Native Raiker TUI."""

    CSS = """
    #welcome {
        text-align: center;
        padding: 1 2;
        height: 1fr;
        width: 1fr;
    }
    """

    TITLE = "Raiker TUI"
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+p", "toggle_palette", "Commands", show=True),
    ]

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        profile: TerminalProfile | None = None,
        streaming_gateway: object | None = None,
        slash_handler: object | None = None,
    ) -> None:
        super().__init__()
        self.workspace_root = Path(workspace_root)
        self.profile = profile or TerminalProfile(interactive=True)
        self._streaming_gateway = streaming_gateway
        self._slash_handler = slash_handler
        self._show_welcome = True
        self._busy = False

    # -- composition ------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield _Transcript(self.profile)
        yield _DockedInput(placeholder="? side question | / command | prompt", id="prompt-input")
        yield _StatusBar("READY", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._render_welcome()
        self.query_one("#prompt-input", _DockedInput).focus()
        self.query_one(_StatusBar).setup(self.profile)

    # -- welcome ----------------------------------------------------------

    def _render_welcome(self) -> None:
        transcript = self.query_one(_Transcript)
        transcript.clear()
        transcript.write(_logo_only(self.profile))
        transcript.write(_welcome_banner(self.profile))

    # -- input handling ---------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        if not line:
            return
        event.input.value = ""
        if line in _EXIT_COMMANDS:
            self.exit()
            return
        if line in _PALETTE_COMMANDS:
            self._show_palette()
            return
        if self._show_welcome:
            self._show_welcome = False
            self.query_one(_Transcript).clear()
        if line.startswith("/"):
            self._handle_slash(line)
            return
        if line.startswith("?"):
            self._handle_side_question(line[1:].strip())
            return
        self._handle_prompt(line)

    def _handle_slash(self, command: str) -> None:
        self._append_user(command)
        if self._slash_handler is not None:
            result = self._slash_handler(command, workspace_root=self.workspace_root)  # type: ignore[operator]
        else:
            from raiker.cli.commands import handle_slash_command

            result = handle_slash_command(command, workspace_root=self.workspace_root)
        self._append_result(command, result)

    def _handle_side_question(self, question: str) -> None:
        self._append_user(f"? {question}")
        if self._slash_handler is not None:
            result = self._slash_handler(question, workspace_root=self.workspace_root)  # type: ignore[operator]
        else:
            from raiker.cli.commands import submit_terminal_prompt

            result = submit_terminal_prompt(question, workspace_root=self.workspace_root)
        self._append_result(f"side question: {question}", result, side_question=True)

    def _handle_prompt(self, prompt: str) -> None:
        self._append_user(prompt)
        if self._busy:
            self._append_result(prompt, "(busy: a turn is already running)")
            return
        self._set_busy(True)
        self._stream_turn(prompt)

    # -- streaming --------------------------------------------------------

    @work(exclusive=True, name="raiker-stream")
    async def _stream_turn(self, prompt: str) -> None:
        from raiker.cli.commands import build_prompt_envelope

        gateway = self._streaming_gateway
        if gateway is None:
            from raiker.gateway.agent_gateway import AgentGateway

            gateway = AgentGateway(self.workspace_root)
        envelope = build_prompt_envelope(prompt)

        transcript = self.query_one(_Transcript)
        transcript.write(self._assistant_indicator() + "(streaming...)")
        accumulated: list[str] = []

        try:
            events = self._iter_events(gateway, envelope)
            async for event in events:
                if event.kind == TEXT_DELTA and event.text:
                    accumulated.append(event.text)
                elif event.kind == FINAL and event.response is not None:
                    final_text = event.response.message
                    self._append_result(prompt, final_text)
                elif event.kind == LIFECYCLE:
                    self._update_status_from_lifecycle(event)
        except Exception as exc:
            self._append_result(prompt, f"(stream error: {type(exc).__name__})")
        finally:
            self._set_busy(False)

    async def _iter_events(
        self, gateway: object, envelope: PromptEnvelope
    ) -> AsyncIterator[StreamEvent]:
        stream = gateway.astream_prompt(envelope)  # type: ignore[attr-defined]
        async for event in stream:
            yield event

    def _update_status_from_lifecycle(self, event: StreamEvent) -> None:
        status_bar = self.query_one(_StatusBar)
        new_state = "RUNNING" if event.event_type else status_bar._status_context.state  # noqa: SLF001
        status_bar.update_context(StatusContext(state=new_state))

    # -- transcript helpers ----------------------------------------------

    def _append_user(self, text: str) -> None:
        transcript = self.query_one(_Transcript)
        transcript.write(self._user_indicator() + text)

    def _append_result(
        self, title: str, result: str, *, side_question: bool = False
    ) -> None:
        transcript = self.query_one(_Transcript)
        prefix = "  (side) " if side_question else "  "
        lines = result.splitlines() or [result]
        transcript.write(f"{prefix}* {title} — {lines[0]}")
        for extra in lines[1:]:
            transcript.write(f"{prefix}  {extra}")

    def _user_indicator(self) -> str:
        return "> " if self.profile.unicode else "> "

    def _assistant_indicator(self) -> str:
        return "  " if self.profile.unicode else "  "

    # -- palette ----------------------------------------------------------

    def action_toggle_palette(self) -> None:
        self._show_palette()

    def _show_palette(self) -> None:
        transcript = self.query_one(_Transcript)
        transcript.write(render_command_palette(self.profile))

    # -- busy state -------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        status_bar = self.query_one(_StatusBar)
        state = "RUNNING" if busy else "READY"
        status_bar.update_context(StatusContext(state=state))


def run_textual_tui(
    *,
    workspace_root: str | Path = ".",
    profile: TerminalProfile | None = None,
) -> int:
    """Launch the native Raiker Textual TUI. Returns the process exit code."""

    if profile is None:
        profile = TerminalProfile(interactive=True)
    app = RaikerTextualApp(workspace_root=workspace_root, profile=profile)
    app.run()
    return 0
