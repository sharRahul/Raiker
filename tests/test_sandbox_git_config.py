"""A workspace-homed process must not read the workspace as Git global config."""

import subprocess
from pathlib import Path

from raiker.runtime.command_policy import sandbox_environment


def test_workspace_gitconfig_is_not_global_configuration(tmp_path: Path) -> None:
    (tmp_path / ".gitconfig").write_text("[raiker-test]\n value = injected\n", encoding="utf-8")
    env = sandbox_environment(
        workspace_root=tmp_path,
        extra={"GIT_CONFIG_GLOBAL": str(tmp_path / ".gitconfig"), "GIT_CONFIG_NOSYSTEM": "0"},
    )
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    result = subprocess.run(
        ["git", "config", "--global", "--get", "raiker-test.value"],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "injected" not in result.stdout
