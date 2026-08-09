from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class InstallPlan:
    runtime: str
    action: str
    source_url: str
    argv: tuple[str, ...]
    requires_elevation: bool
    terms_url: str
    redistribution: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuntimeInstallerRegistry:
    """Reviewed official sources; previewing never downloads or executes."""

    def preview(self, runtime: str, *, platform: str) -> InstallPlan:
        platform = platform.lower()
        if runtime == "lm-studio-desktop":
            return InstallPlan(
                runtime=runtime, action="open_vendor_download",
                source_url="https://lmstudio.ai/download",
                argv=(), requires_elevation=False,
                terms_url="https://lmstudio.ai/app-terms", redistribution=False,
            )
        if runtime == "ollama":
            source = (
                "https://ollama.com/download/OllamaSetup.exe"
                if platform == "windows"
                else "https://ollama.com/download"
            )
            return InstallPlan(
                runtime=runtime, action="download_official_installer", source_url=source,
                argv=(), requires_elevation=False,
                terms_url="https://github.com/ollama/ollama/blob/main/LICENSE", redistribution=False,
            )
        if runtime == "llmster":
            source = (
                "https://lmstudio.ai/install.ps1"
                if platform == "windows"
                else "https://lmstudio.ai/install.sh"
            )
            return InstallPlan(
                runtime=runtime, action="review_official_installer", source_url=source,
                argv=(), requires_elevation=False,
                terms_url="https://lmstudio.ai/app-terms", redistribution=False,
            )
        if runtime == "llama.cpp":
            return InstallPlan(
                runtime=runtime, action="download_official_release",
                source_url="https://github.com/ggml-org/llama.cpp/releases/latest",
                argv=(), requires_elevation=False,
                terms_url="https://github.com/ggml-org/llama.cpp/blob/master/LICENSE",
                redistribution=False,
            )
        raise ValueError("unsupported_runtime")
