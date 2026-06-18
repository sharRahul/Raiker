from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    available: bool
    enabled_for_runtime: bool
    detail: str


def check_local_provider(provider: str) -> ProviderHealth:
    if provider != "ollama":
        return ProviderHealth(provider, False, False, "unsupported_local_provider")
    binary = shutil.which("ollama")
    if binary is None:
        return ProviderHealth(provider, False, False, "ollama_binary_not_found")
    proc = subprocess.run(
        [binary, "--version"], check=False, capture_output=True, text=True, timeout=5
    )
    return ProviderHealth(
        provider, proc.returncode == 0, False, (proc.stdout or proc.stderr).strip()
    )
