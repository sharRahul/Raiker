from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class RaikerTheme:
    primary: str = "#8a5cf5"
    accent: str = "#c4a7e7"
    surface: str = "#1a1a2e"
    background: str = "#0f0f1a"
    text: str = "#e0def4"
    muted: str = "#6e6a86"
    border: str = "#3c3860"
    success: str = "#9ccfd8"
    error: str = "#eb6f92"
    warn: str = "#f6c177"
    status_good: str = "#9ccfd8"
    status_warn: str = "#f6c177"
    status_bad: str = "#ebbcba"
    status_critical: str = "#eb6f92"
    user_text: str = "#c4a7e7"
    assistant_text: str = "#e0def4"
    tool_text: str = "#6e6a86"
    code_bg: str = "#191926"
    label: str = "#908caa"

    THEMES: ClassVar[dict[str, RaikerTheme]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)


ROSE_PINE: RaikerTheme = RaikerTheme(
    primary="#8a5cf5",
    accent="#c4a7e7",
    surface="#1a1a2e",
    background="#0f0f1a",
    text="#e0def4",
    muted="#6e6a86",
    border="#3c3860",
    success="#9ccfd8",
    error="#eb6f92",
    warn="#f6c177",
    status_good="#9ccfd8",
    status_warn="#f6c177",
    status_bad="#ebbcba",
    status_critical="#eb6f92",
    user_text="#c4a7e7",
    assistant_text="#e0def4",
    tool_text="#6e6a86",
    code_bg="#191926",
    label="#908caa",
)

MONOCHROME: RaikerTheme = RaikerTheme(
    primary="#ffffff",
    accent="#cccccc",
    surface="#000000",
    background="#000000",
    text="#ffffff",
    muted="#888888",
    border="#555555",
    success="#ffffff",
    error="#ffffff",
    warn="#ffffff",
    status_good="#ffffff",
    status_warn="#ffffff",
    status_bad="#ffffff",
    status_critical="#ffffff",
    user_text="#ffffff",
    assistant_text="#ffffff",
    tool_text="#888888",
    code_bg="#111111",
    label="#aaaaaa",
)


def detect_theme(unicode: bool = True, color: bool = True) -> RaikerTheme:
    if not color:
        return MONOCHROME
    return ROSE_PINE
