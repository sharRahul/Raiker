from __future__ import annotations

import threading
import webbrowser
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class TrayMenuState:
    status_label: str
    pause_label: str


def menu_state(host: dict[str, Any]) -> TrayMenuState:
    state = str(host.get("state", "needs attention"))
    labels = {
        "running": "Running",
        "paused": "Paused",
        "needs attention": "Needs attention",
        "stopped": "Stopped",
    }
    return TrayMenuState(labels.get(state, "Needs attention"), "Resume" if state == "paused" else "Pause")


TRAY_ICON_SIZE = (64, 64)


def tray_image(image_module: Any, draw_module: Any) -> Any:
    """The system-tray icon: the shipped icon, or a drawn stand-in.

    The tray used to draw its own rounded rectangle, so the mark in the menu bar
    was not the mark the product ships — a different Raiker in the one place the
    app is visible while it is doing nothing. It now loads
    ``raiker/assets/raiker-icon.png`` through :func:`raiker.assets.icon_path`,
    downsampled to tray size with alpha preserved so it stays legible on a dark
    menu bar. The drawn shape survives only as the fallback for a build whose
    icon is missing: a tray with a placeholder is still a working tray, and
    failing to start one would remove the owner's Pause and Quit.
    """
    from raiker.assets import icon_path

    source = icon_path()
    if source is not None:
        try:
            with image_module.open(source) as handle:
                return handle.convert("RGBA").resize(TRAY_ICON_SIZE, image_module.LANCZOS)
        except (OSError, ValueError):
            pass
    image = image_module.new("RGBA", TRAY_ICON_SIZE, "#14213d")
    draw = draw_module.Draw(image)
    draw.rounded_rectangle((8, 8, 56, 56), radius=12, fill="#f4b942")
    draw.line((22, 19, 22, 45, 42, 45), fill="#14213d", width=7)
    return image


def start_native_tray(base_url: str, bootstrap_secret: str) -> threading.Thread:
    thread = threading.Thread(
        target=_run_native_tray,
        args=(base_url.rstrip("/"), bootstrap_secret),
        name="raiker-native-tray",
        daemon=True,
    )
    thread.start()
    return thread


def _run_native_tray(base_url: str, bootstrap_secret: str) -> None:
    try:
        import pystray  # type: ignore[import-untyped]
        from PIL import Image, ImageDraw
    except ImportError:
        return

    token = _exchange(base_url, bootstrap_secret)
    if token is None:
        return
    headers = {"Authorization": f"Bearer {token}"}

    def host() -> dict[str, Any]:
        try:
            response = httpx.get(f"{base_url}/api/host", headers=headers, timeout=2)
            return response.json() if response.is_success else {"state": "needs attention"}
        except httpx.HTTPError:
            return {"state": "needs attention"}

    def post(path: str, body: dict[str, object] | None = None) -> None:
        with httpx.Client(headers=headers, timeout=3) as client:
            client.post(f"{base_url}{path}", json=body or {})

    image = tray_image(Image, ImageDraw)

    icon: Any = None

    def items() -> tuple[Any, ...]:
        state = menu_state(host())
        return (
            pystray.MenuItem(state.status_label, None, enabled=False),
            pystray.MenuItem("Open Raiker", lambda: webbrowser.open(base_url)),
            pystray.MenuItem(
                state.pause_label,
                lambda: post("/api/host/resume" if state.pause_label == "Resume" else "/api/host/pause"),
            ),
            pystray.MenuItem("Restart", lambda: post("/api/host/restart", {"confirm": True})),
            pystray.MenuItem("Quit", lambda: post("/api/host/quit", {"confirm": True})),
        )

    icon = pystray.Icon("raiker", image, "Raiker", pystray.Menu(items))
    icon.run()


def _exchange(base_url: str, secret: str) -> str | None:
    # On a fresh workspace the host answers 409 until the owner completes the
    # setup wizard. This daemon thread lives only as long as the host, so keep
    # waiting instead of silently removing the tray five seconds into first run.
    while True:
        try:
            response = httpx.post(
                f"{base_url}/api/tray/session", json={"secret": secret}, timeout=1
            )
            if response.is_success:
                token = response.json().get("token")
                return str(token) if token else None
        except httpx.HTTPError:
            pass
        threading.Event().wait(0.5)
