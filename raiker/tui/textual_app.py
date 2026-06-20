from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from rich.style import Style
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Input, Static

from raiker.contracts.streaming import ERROR, FINAL, LIFECYCLE, TEXT_DELTA, TOOL, StreamEvent
from raiker.tui.status_bar import StatusBarRenderer, StatusContext
from raiker.tui.theme import ROSE_PINE, RaikerTheme
from raiker.tui.welcome import logo_lines

if TYPE_CHECKING:
    from raiker.contracts.models import PromptEnvelope

_WELCOME_TIPS: tuple[str, ...] = (
    "Type a prompt and press Enter to start a turn.",
    "/commands to browse slash commands. /quit exits.",
    "? prefix asks a side question.",
)
_EXIT_COMMANDS = frozenset({"/q", "/quit", "/exit"})
_PALETTE_COMMANDS = frozenset({"/commands", "/palette"})


def _welcome_text(theme: RaikerTheme) -> Text:
    t = theme
    logo = "\n".join(logo_lines(type("pf", (), {"unicode": True})()))
    text = Text()
    text.append(logo + "\n\n", style=Style(color=t.primary, bold=True))
    text.append("Raiker Terminal\n\n", style=Style(color=t.accent, bold=True))
    for tip in _WELCOME_TIPS:
        text.append(f"  {tip}\n", style=Style(color=t.muted))
    return text


class StatusBar(Static):
    tick: reactive[int] = reactive(0)  # type: ignore[assignment]

    def __init__(self, theme: RaikerTheme) -> None:
        super().__init__()
        self._theme = theme
        self._renderer: StatusBarRenderer | None = None
        self._ctx = StatusContext(state="READY")
        self._clock_fmt: str = ""

    def on_mount(self) -> None:
        self._renderer = StatusBarRenderer(theme=self._theme)
        self.set_interval(1.0, self._tick_clock)
        self.set_interval(0.2, self._tick_spinner)
        self._refresh()

    def update_context(self, ctx: StatusContext) -> None:
        self._ctx = ctx
        self._refresh()

    def _tick_clock(self) -> None:
        self._clock_fmt = time.strftime("%H:%M")
        if self._ctx.state == "RUNNING":
            self._ctx.turn_elapsed += 1.0
        self._refresh()

    def _tick_spinner(self) -> None:
        self.tick += 1

    def watch_tick(self, value: int) -> None:
        if self._ctx.state == "RUNNING":
            self._refresh()

    def _refresh(self) -> None:
        renderer = self._renderer
        if renderer is None:
            return
        w = self.size.width if self._is_mounted else None
        text = renderer.render_status_line(
            self._ctx, tick=self.tick, clock=self._clock_fmt, compact=False, width=w
        )
        self.update(text)


class UserMessage(Static):
    def __init__(self, text: str, theme: RaikerTheme) -> None:
        super().__init__()
        self._text = text
        self._theme = theme
        self._plain_text = f"> {text}"

    def on_mount(self) -> None:
        t = self._theme
        content = Text()
        content.append("> ", style=Style(color=t.user_text, bold=True))
        content.append(self._text, style=Style(color=t.text))
        self.update(content)


class AssistantMessage(Static):
    def __init__(self, theme: RaikerTheme, initial: str = "") -> None:
        super().__init__()
        self._theme = theme
        self._parts: list[str] = [initial] if initial else []
        self._plain_text = initial

    def append_delta(self, text: str) -> None:
        self._parts.append(text)
        self._plain_text = self._plain_text + text
        self._render_content()

    def set_text(self, text: str) -> None:
        self._parts = [text]
        self._plain_text = text
        self._render_content()

    def _render_content(self) -> None:
        t = self._theme
        full = "".join(self._parts)
        content = Text(full, style=Style(color=t.assistant_text))
        self.update(content)


class ToolCallBlock(Static):
    def __init__(
        self, name: str, status: str = "running", theme: RaikerTheme | None = None
    ) -> None:
        super().__init__()
        self._name = name
        self._status = status
        self._theme = theme or ROSE_PINE

    def on_mount(self) -> None:
        self._render_tool()

    def _render_tool(self) -> None:
        t = self._theme
        s = self._status
        glyph = "⠋" if s == "running" else "✓" if s == "completed" else "✗"
        if s == "running":
            status_label = "Running\u2026"
        elif s == "completed":
            status_label = "Completed"
        else:
            status_label = "Failed"
        text = Text(f"  {glyph} {self._name} \u2014 {status_label}", style=Style(color=t.tool_text))
        self.update(text)


class Transcript(VerticalScroll):
    DEFAULT_CSS = """
    Transcript {
        height: 1fr;
        width: 1fr;
        overflow-y: scroll;
        padding: 0 1;
    }
    """

    def __init__(self, theme: RaikerTheme) -> None:
        super().__init__()
        self._theme = theme


class HistoryInput(Input):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._history: list[str] = []
        self._history_index: int = -1

    def add_to_history(self, text: str) -> None:
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
        self._history_index = len(self._history)

    def action_history_up(self) -> None:
        if not self._history:
            return
        if self._history_index > 0:
            self._history_index -= 1
            self.value = self._history[self._history_index]
            self.cursor_position = len(self.value)

    def action_history_down(self) -> None:
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.value = self._history[self._history_index]
            self.cursor_position = len(self.value)
        else:
            self._history_index = len(self._history)
            self.value = ""
            self.cursor_position = 0


class RaikerTextualApp(App):
    TITLE = "Raiker"
    CSS = """
    Screen {
        background: $surface;
    }
    StatusBar {
        dock: top;
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    #input-row {
        dock: bottom;
        height: 3;
        padding: 0 1;
        background: $surface;
    }
    #prompt-prefix {
        width: 2;
        height: 3;
        content-align: left middle;
    }
    HistoryInput {
        height: 3;
        border: none;
        padding: 0;
        background: $surface;
    }
    HistoryInput:focus {
        border: none;
    }
    """
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+p", "command_palette", "Commands", show=True),
        Binding("up", "history_up", "History up", show=False),
        Binding("down", "history_down", "History down", show=False),
    ]

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        profile: object | None = None,
        streaming_gateway: object | None = None,
        slash_handler: object | None = None,
    ) -> None:
        super().__init__()
        self.workspace_root = Path(workspace_root)
        self._streaming_gateway = streaming_gateway
        self._slash_handler = slash_handler
        self._show_welcome = True
        self._busy = False
        self._stream_msg: AssistantMessage | None = None
        self._theme: RaikerTheme = ROSE_PINE

    def compose(self) -> ComposeResult:
        yield StatusBar(self._theme)
        yield Transcript(self._theme)
        with Horizontal(id="input-row"):
            yield Static("\u276f ", id="prompt-prefix")
            placeholder = "Type a prompt, /command, or ? side question..."
            yield HistoryInput(placeholder=placeholder, id="prompt-input")

    def on_mount(self) -> None:
        self._render_welcome()
        self.query_one("#prompt-input", HistoryInput).focus()
        self._status_bar = self.query_one(StatusBar)

    def _render_welcome(self) -> None:
        transcript = self.query_one(Transcript)
        welcome = _welcome_text(self._theme)
        transcript.mount(Static(welcome, id="welcome"))

    def _transcript_text(self) -> str:
        lines: list[str] = []
        for child in self.query_one(Transcript).children:
            text = getattr(child, "_plain_text", None)
            if text is not None:
                lines.append(text)
                continue
            cache = getattr(child, "_render_cache", None)
            if cache is None or not hasattr(cache, "lines"):
                continue
            for strip in cache.lines:
                texts = (getattr(seg, "text", "") for seg in getattr(strip, "_segments", ()))
                seg_text = "".join(texts)
                lines.append(seg_text)
        return "\n".join(lines)

    def action_history_up(self) -> None:
        self.query_one(HistoryInput).action_history_up()

    def action_history_down(self) -> None:
        self.query_one(HistoryInput).action_history_down()

    def action_command_palette(self) -> None:
        from raiker.tui.accessibility import TerminalProfile
        from raiker.tui.command_palette import palette_lines

        profile = TerminalProfile(interactive=True)
        lines = "\n".join(palette_lines(profile))
        t = self._theme
        self._add_transcript(Static(Text("[Commands]\n" + lines, style=Style(color=t.muted))))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        if not line:
            return
        event.input.value = ""
        inp = self.query_one(HistoryInput)
        inp.add_to_history(line)
        if line in _EXIT_COMMANDS:
            self.exit()
            return
        if line in _PALETTE_COMMANDS:
            self.action_command_palette()
            return
        if self._show_welcome:
            welcome = self.query_one("#welcome")
            if welcome:
                welcome.remove()
            self._show_welcome = False
        if line.startswith("/"):
            self._handle_slash(line)
            return
        if line.startswith("?"):
            self._handle_side_question(line[1:].strip())
            return
        self._handle_prompt(line)

    def _handle_slash(self, command: str) -> None:
        self._add_user(command)
        if self._slash_handler is not None:
            result = self._slash_handler(command, workspace_root=self.workspace_root)
        else:
            from raiker.cli.commands import handle_slash_command
            result = handle_slash_command(command, workspace_root=self.workspace_root)
        self._add_assistant(result)

    def _handle_side_question(self, question: str) -> None:
        self._add_user(f"? {question}")
        if self._slash_handler is not None:
            result = self._slash_handler(question, workspace_root=self.workspace_root)
        else:
            from raiker.cli.commands import submit_terminal_prompt
            result = submit_terminal_prompt(question, workspace_root=self.workspace_root)
        self._add_assistant(result, side=True)

    def _handle_prompt(self, prompt: str) -> None:
        self._add_user(prompt)
        if self._busy:
            self._add_transcript(Static(Text("(busy \u2014 queued)")))
            return
        self._set_busy(True)
        self._stream_turn(prompt)

    def _add_user(self, text: str) -> None:
        self._add_transcript(UserMessage(text, self._theme))

    def _add_assistant(self, text: str, *, side: bool = False) -> None:
        prefix = "(side) " if side else ""
        full = f"{prefix}{text}"
        msg = AssistantMessage(self._theme)
        msg.set_text(full)
        self._add_transcript(msg)

    def _add_transcript(self, widget: Static) -> None:
        transcript = self.query_one(Transcript)
        transcript.mount(widget)
        transcript.scroll_end(animate=False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        ctx = StatusContext(state="RUNNING" if busy else "READY")
        self._status_bar.update_context(ctx)

    @work(exclusive=True, name="raiker-stream")
    async def _stream_turn(self, prompt: str) -> None:
        from raiker.cli.commands import build_prompt_envelope
        gateway = self._streaming_gateway
        if gateway is None:
            from raiker.gateway.agent_gateway import AgentGateway
            gateway = AgentGateway(self.workspace_root)
        envelope = build_prompt_envelope(prompt)

        msg = AssistantMessage(self._theme)
        self._add_transcript(msg)
        self._stream_msg = msg
        ctx = StatusContext(state="RUNNING")
        self._status_bar.update_context(ctx)

        try:
            events = self._iter_events(gateway, envelope)
            async for event in events:
                if event.kind == TEXT_DELTA and event.text:
                    msg.append_delta(event.text)
                elif event.kind == FINAL and event.response is not None:
                    msg.set_text(event.response.message)
                elif event.kind == LIFECYCLE:
                    state = "RUNNING" if event.event_type else "READY"
                    self._status_bar.update_context(StatusContext(state=state))
                elif event.kind == TOOL:
                    name = event.payload.get("name", str(event.payload))
                    status = event.payload.get("status", "running")
                    tb = ToolCallBlock(str(name), str(status), self._theme)
                    self._add_transcript(tb)
                elif event.kind == ERROR:
                    err_text = f"Error: {event.text}"
                    self._add_transcript(Static(
                        Text(err_text, style=Style(color=self._theme.error))
                    ))
        except Exception as exc:
            err_msg = f"Stream error: {type(exc).__name__}: {exc}"
            self._add_transcript(Static(
                Text(err_msg, style=Style(color=self._theme.error))
            ))
        finally:
            self._stream_msg = None
            self._set_busy(False)

    async def _iter_events(
        self, gateway: object, envelope: PromptEnvelope
    ) -> AsyncIterator[StreamEvent]:
        stream = gateway.astream_prompt(envelope)
        async for event in stream:
            yield event


def run_textual_tui(
    *,
    workspace_root: str | Path = ".",
    profile: object | None = None,
) -> int:
    if profile is None:
        from raiker.tui.accessibility import TerminalProfile
        profile = TerminalProfile(interactive=True)
    app = RaikerTextualApp(workspace_root=workspace_root, profile=profile)
    app.run()
    return 0
