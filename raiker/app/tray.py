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
        import pystray  # type: ignore[import-not-found]
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

    image = Image.new("RGBA", (64, 64), "#14213d")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 56, 56), radius=12, fill="#f4b942")
    draw.line((22, 19, 22, 45, 42, 45), fill="#14213d", width=7)

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
    for _ in range(20):
        try:
            response = httpx.post(
                f"{base_url}/api/tray/session", json={"secret": secret}, timeout=1
            )
            if response.is_success:
                token = response.json().get("token")
                return str(token) if token else None
        except httpx.HTTPError:
            pass
        threading.Event().wait(0.25)
    return None

