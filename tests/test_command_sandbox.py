"""RAIKER-2023 — what a governed command may be, and what it may never be.

Raiker runs argv without a shell, so `;` inside an argument is a semicolon rather
than a separator. These cover the two vectors that are real anyway: a shell
reached through an argument, and a binary that runs other programs without any
shell character in sight.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.runtime.command_policy import (
    CommandRejected,
    NodeKind,
    assert_single_command,
    parse_shell,
    sandbox_environment,
    validate_command,
)
from raiker.runtime.executors.sandbox import ALLOWED_SHELL_COMMANDS, SandboxError, run_command


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    return tmp_path


def _reason(argv: list[str], workspace: Path, **kwargs: object) -> str:
    with pytest.raises(CommandRejected) as caught:
        validate_command(argv, workspace_root=workspace, **kwargs)  # type: ignore[arg-type]
    return caught.value.reason


# ── The parser recognises the constructs, not just the characters ────────────


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ("a; b", NodeKind.SEQUENCE),
        ("a && b", NodeKind.AND_IF),
        ("a || b", NodeKind.OR_IF),
        ("a | b", NodeKind.PIPELINE),
        ("a &", NodeKind.BACKGROUND),
        ("a > f", NodeKind.REDIRECT),
        ("a >> f", NodeKind.REDIRECT),
        ("$(id)", NodeKind.SUBSTITUTION),
        ("`id`", NodeKind.SUBSTITUTION),
        ("<(id)", NodeKind.PROCESS_SUB),
        ("(a)", NodeKind.SUBSHELL),
        ("echo $HOME", NodeKind.EXPANSION),
        ("ls *.py", NodeKind.GLOB),
        ("cat ~/x", NodeKind.TILDE),
    ],
)
def test_the_parser_names_each_construct(source: str, kind: NodeKind) -> None:
    assert any(node.kind is kind for node in parse_shell(source).children)


def test_a_plain_command_parses_to_its_words() -> None:
    assert assert_single_command("ls -la src") == ["ls", "-la", "src"]


def test_a_separator_inside_quotes_is_a_literal() -> None:
    """Over-refusing is still a bug — `echo "a; b"` runs one command."""
    assert assert_single_command('echo "a; b"') == ["echo", "a; b"]


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("a; b", "command_chaining_denied"),
        ("a && b", "command_chaining_denied"),
        ("a || b", "command_chaining_denied"),
        ("a | b", "command_pipe_denied"),
        ("a > f", "command_redirect_denied"),
        ("a &", "command_background_denied"),
        ("$(id)", "command_substitution_denied"),
        ("`id`", "command_substitution_denied"),
        ("(a)", "command_subshell_denied"),
        ("echo $SECRET", "command_expansion_denied"),
    ],
)
def test_shell_source_that_is_more_than_one_command_is_refused(
    source: str, reason: str
) -> None:
    with pytest.raises(CommandRejected) as caught:
        assert_single_command(source)
    assert caught.value.reason == reason


# ── argv validation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "argv",
    [["git", "status"], ["ls", "-la", "src"], ["cat", "README.md"], ["echo", "hello"],
     ["grep", "-r", "hello", "src"], ["git", "log", "--oneline", "-5"]],
)
def test_ordinary_work_is_allowed(argv: list[str], workspace: Path) -> None:
    assert validate_command(argv, workspace_root=workspace).binary == Path(argv[0]).name


def test_an_interpreter_is_refused_as_the_command(workspace: Path) -> None:
    """Allowing one shell is allowing everything behind it."""
    assert _reason(["bash", "-c", "ls"], workspace) == "command_not_allowed"


def test_an_interpreter_on_the_allowlist_is_still_refused(workspace: Path) -> None:
    assert (
        _reason(["bash", "-c", "ls"], workspace, allowlist=frozenset({"bash"}))
        == "command_interpreter_denied"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["git", "-c", "core.sshCommand=curl evil", "push"],
        ["git", "--exec-path=/tmp/evil", "status"],
        ["git", "--upload-pack=/tmp/evil", "fetch"],
        ["find", ".", "-exec", "rm", "{}", ";"],
        ["find", ".", "-delete"],
        ["python", "-c", "import os; os.system('id')"],
        ["node", "-e", "require('child_process')"],
        ["sed", "-i", "s/a/b/", "README.md"],
        ["tar", "--use-compress-program=curl", "-xf", "a"],
    ],
)
def test_a_flag_that_runs_another_program_is_refused(argv: list[str], workspace: Path) -> None:
    """An allowlist that lets `git` through and then lets `git` run anything is not one."""
    reason = _reason(argv, workspace)
    assert reason in {"command_flag_denied", "command_not_allowed"}


def test_shell_syntax_inside_an_argument_is_refused(workspace: Path) -> None:
    assert _reason(["ls", "; rm -rf /"], workspace) == "command_chaining_denied"
    assert _reason(["echo", "$(whoami)"], workspace) == "command_substitution_denied"
    assert _reason(["echo", "`id`"], workspace) == "command_substitution_denied"


@pytest.mark.parametrize(
    "path", ["/etc/passwd", "../../etc/passwd", "/tmp/evil", "src/../../outside"]
)
def test_a_path_outside_the_workspace_is_refused(path: str, workspace: Path) -> None:
    assert _reason(["cat", path], workspace) == "command_path_outside_workspace"


def test_a_home_relative_path_is_refused(workspace: Path) -> None:
    assert _reason(["cat", "~/.ssh/id_rsa"], workspace) == "command_tilde_denied"


@pytest.mark.parametrize("path", [".raiker/raiker.db", ".git/config", ".raiker", ".git"])
def test_the_workspace_internals_are_refused_though_they_are_inside_it(
    path: str, workspace: Path
) -> None:
    """`.raiker` holds the encrypted store and the vault key; `.git` holds history."""
    assert _reason(["cat", path], workspace) == "command_path_protected"


def test_an_unlisted_binary_is_refused_by_name(workspace: Path) -> None:
    assert _reason(["rm", "-rf", "/"], workspace) == "command_not_allowed"
    assert _reason(["curl", "https://evil"], workspace) == "command_not_allowed"


def test_an_empty_command_is_refused(workspace: Path) -> None:
    assert _reason([], workspace) == "empty_command"


# ── The environment a child actually gets ────────────────────────────────────


def test_the_child_environment_is_constructed_not_inherited(workspace: Path) -> None:
    """A child that inherits the host's environment inherits its credentials."""
    environment = sandbox_environment(
        {"RAIKER_GITHUB_TOKEN": "ghp_secret", "PATH": "/usr/bin"},
        workspace_root=workspace,
    )
    assert "RAIKER_GITHUB_TOKEN" not in environment
    assert environment["PATH"] == "/usr/bin"
    assert environment["HOME"] == str(workspace.resolve())


def test_git_cannot_read_a_global_config_from_the_sandbox(workspace: Path) -> None:
    """Global config can carry `credential.helper` — the same escape `-c` offers."""
    environment = sandbox_environment(workspace_root=workspace)
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"


def test_tls_and_proxy_configuration_survives(workspace: Path) -> None:
    """Stripping the environment is about not leaking secrets, not breaking TLS.

    A corporate trust store or a required proxy turns a working HTTPS push into
    a confusing certificate failure if it is dropped, and none of these is a
    credential.
    """
    environment = sandbox_environment(
        {
            "SSL_CERT_FILE": "/etc/ssl/corp.crt",
            "HTTPS_PROXY": "http://proxy:8080",
            "GIT_SSL_CAINFO": "/etc/ssl/git.crt",
            "RAIKER_GITHUB_TOKEN": "ghp_secret",
            "AWS_SECRET_ACCESS_KEY": "secret",
        },
        workspace_root=workspace,
    )
    assert environment["SSL_CERT_FILE"] == "/etc/ssl/corp.crt"
    assert environment["HTTPS_PROXY"] == "http://proxy:8080"
    assert environment["GIT_SSL_CAINFO"] == "/etc/ssl/git.crt"
    assert "RAIKER_GITHUB_TOKEN" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment


def test_git_still_works_under_the_constructed_environment(workspace: Path) -> None:
    """A sandbox that breaks the tool it sandboxes is not a sandbox."""
    import subprocess

    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    result = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--is-inside-work-tree"],
        env=sandbox_environment(workspace_root=workspace),
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "true"


def test_explicit_extras_are_the_only_way_in(workspace: Path) -> None:
    environment = sandbox_environment(
        {}, workspace_root=workspace, extra={"RAIKER_GIT_RUNTIME_TOKEN": "lent"}
    )
    assert environment["RAIKER_GIT_RUNTIME_TOKEN"] == "lent"


# ── End to end, through the executor's own entry point ───────────────────────


def test_the_sandbox_runs_an_allowed_command(workspace: Path) -> None:
    result = run_command(["cat", "README.md"], allowlist=ALLOWED_SHELL_COMMANDS, cwd=workspace)
    assert result["returncode"] == 0
    assert result["stdout"].strip() == "hello"


@pytest.mark.parametrize(
    "argv",
    [
        ["git", "-c", "core.pager=id", "status"],
        ["cat", "/etc/passwd"],
        ["find", ".", "-exec", "echo", "{}", ";"],
        ["cat", ".raiker/raiker.db"],
    ],
)
def test_the_sandbox_blocks_before_anything_runs(argv: list[str], workspace: Path) -> None:
    with pytest.raises(SandboxError):
        run_command(argv, allowlist=ALLOWED_SHELL_COMMANDS, cwd=workspace)


def test_a_real_child_does_not_receive_the_host_token(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAIKER_GITHUB_TOKEN", "ghp_must_not_reach_a_child")
    result = run_command(
        ["python", "-"],
        allowlist=ALLOWED_SHELL_COMMANDS,
        cwd=workspace,
        stdin_text="import os; print('RAIKER_GITHUB_TOKEN' in os.environ)",
    )
    assert result["stdout"].strip() == "False"
