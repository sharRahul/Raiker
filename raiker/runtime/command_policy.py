"""What a governed command may be, decided before anything runs.

Raiker launches commands as an argv list with no shell, so the classic
``rm -rf /; curl evil`` string injection has nowhere to land — ``;`` inside an
argv element is a semicolon, not a separator. That is worth stating plainly
because it means this module is **not** guarding against the thing people expect
it to guard against. It guards against the two that are real:

1. **A shell reached by argument.** ``["bash", "-c", "a && b"]`` is a perfectly
   ordinary argv list, and the string inside it *is* interpreted. So any argument
   that will be read as shell source is parsed here, with a real parser, and
   anything that is not a single simple command is refused — chaining (``;``,
   ``&&``, ``||``), pipes, redirection, background, subshells, command
   substitution, and variable expansion all included.
2. **A binary that is a shell in disguise.** ``git -c core.sshCommand=…``,
   ``find -exec``, ``ssh host cmd`` and their relatives run arbitrary programs
   without a shell character anywhere in sight. A per-binary flag policy refuses
   those, because an allowlist that lets `git` through and then lets `git` run
   anything is not an allowlist.

On top of both, every argument that looks like a path is resolved and required to
stay inside the workspace, so an allowed command cannot be pointed at ``/etc`` or
at the workspace's own ``.raiker`` and ``.git`` internals.
"""
from __future__ import annotations

import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

ALLOWED_SHELL_COMMANDS: frozenset[str] = frozenset({
    "ls", "cat", "head", "tail", "echo", "pwd", "which",
    "git", "python", "pip", "node", "npm",
    "diff", "grep", "find", "sort", "wc", "uniq",
})


class CommandRejected(ValueError):
    """A proposed command that will not be run, and the reason code why."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}:{detail}" if detail else reason)
        self.reason = reason
        self.detail = detail

    @property
    def reason_code(self) -> str:
        return f"{self.reason}:{self.detail}" if self.detail else self.reason


class NodeKind(StrEnum):
    """The shell constructs this parser can recognise.

    Only ``COMMAND`` is ever executable. Every other kind exists so a refusal can
    name what was found rather than saying "invalid", which is the difference
    between a message the owner can act on and one they cannot.
    """

    COMMAND = "command"
    SEQUENCE = "sequence"        # a ; b
    AND_IF = "and_if"            # a && b
    OR_IF = "or_if"              # a || b
    PIPELINE = "pipeline"        # a | b
    BACKGROUND = "background"    # a &
    REDIRECT = "redirect"        # a > b, a < b, a >> b, a 2>&1
    SUBSHELL = "subshell"        # ( a )
    GROUP = "group"              # { a; }
    SUBSTITUTION = "substitution"  # $(a) or `a`
    EXPANSION = "expansion"      # $VAR, ${VAR}
    GLOB = "glob"                # *, ?, [abc]
    TILDE = "tilde"              # ~
    PROCESS_SUB = "process_sub"  # <(a), >(a)


@dataclass
class ShellNode:
    """One node of the parsed command line."""

    kind: NodeKind
    text: str = ""
    words: list[str] = field(default_factory=list)
    children: list[ShellNode] = field(default_factory=list)

    def walk(self) -> list[ShellNode]:
        nodes = [self]
        for child in self.children:
            nodes.extend(child.walk())
        return nodes


#: Operators that split or redirect a command line. Order matters: the two-character
#: forms have to be recognised before their single-character prefixes.
_OPERATORS: tuple[tuple[str, NodeKind], ...] = (
    ("&&", NodeKind.AND_IF),
    ("||", NodeKind.OR_IF),
    (">>", NodeKind.REDIRECT),
    ("<<", NodeKind.REDIRECT),
    (";", NodeKind.SEQUENCE),
    ("|", NodeKind.PIPELINE),
    ("&", NodeKind.BACKGROUND),
    (">", NodeKind.REDIRECT),
    ("<", NodeKind.REDIRECT),
    ("\n", NodeKind.SEQUENCE),
)


def parse_shell(source: str) -> ShellNode:
    """Parse shell source into a tree of what it would actually do.

    A hand-written scanner rather than ``shlex``: ``shlex`` tokenises and would
    happily hand back ``["a", ";", "b"]`` as three words, which loses the very
    distinction this has to make. Quoting state is tracked because ``";"`` inside
    quotes is a literal and must not be reported as chaining — over-refusing is
    still a bug, it is just a quieter one.
    """
    root = ShellNode(NodeKind.COMMAND, text=source)
    current: list[str] = []
    word: list[str] = []
    index = 0
    quote: str | None = None
    length = len(source)

    def flush_word() -> None:
        if word:
            current.append("".join(word))
            word.clear()

    while index < length:
        char = source[index]

        if char == "\\" and quote != "'":
            word.append(source[index : index + 2])
            index += 2
            continue

        if quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
            index += 1
            continue

        if char in "'\"":
            quote = char
            index += 1
            continue

        # Command substitution and process substitution: whole constructs, so the
        # inner command is captured for the message rather than silently dropped.
        if source.startswith("$(", index) or char == "`":
            close = ")" if char == "$" else "`"
            end = source.find(close, index + (2 if char == "$" else 1))
            body = source[index + (2 if char == "$" else 1) : end if end != -1 else length]
            root.children.append(ShellNode(NodeKind.SUBSTITUTION, text=body.strip()))
            index = (end + 1) if end != -1 else length
            continue
        if source.startswith("<(", index) or source.startswith(">(", index):
            end = source.find(")", index + 2)
            root.children.append(
                ShellNode(NodeKind.PROCESS_SUB, text=source[index + 2 : end if end != -1 else length])
            )
            index = (end + 1) if end != -1 else length
            continue

        if char == "$":
            match = re.match(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", source[index:])
            if match:
                root.children.append(ShellNode(NodeKind.EXPANSION, text=match.group(1)))
                index += match.end()
                continue

        if char == "(":
            root.children.append(ShellNode(NodeKind.SUBSHELL, text="("))
            index += 1
            continue
        if char == "{" and (index == 0 or source[index - 1].isspace()):
            root.children.append(ShellNode(NodeKind.GROUP, text="{"))
            index += 1
            continue

        matched = False
        for token, kind in _OPERATORS:
            if source.startswith(token, index):
                flush_word()
                root.children.append(ShellNode(kind, text=token))
                index += len(token)
                matched = True
                break
        if matched:
            continue

        if char.isspace():
            flush_word()
            index += 1
            continue

        if char in "*?[":
            root.children.append(ShellNode(NodeKind.GLOB, text=char))
        if char == "~" and not word:
            root.children.append(ShellNode(NodeKind.TILDE, text="~"))

        word.append(char)
        index += 1

    flush_word()
    root.words = current
    return root


#: Every construct that means "this is more than one command", with the reason
#: code each is refused under.
_FORBIDDEN: dict[NodeKind, str] = {
    NodeKind.SEQUENCE: "command_chaining_denied",
    NodeKind.AND_IF: "command_chaining_denied",
    NodeKind.OR_IF: "command_chaining_denied",
    NodeKind.PIPELINE: "command_pipe_denied",
    NodeKind.BACKGROUND: "command_background_denied",
    NodeKind.REDIRECT: "command_redirect_denied",
    NodeKind.SUBSHELL: "command_subshell_denied",
    NodeKind.GROUP: "command_group_denied",
    NodeKind.SUBSTITUTION: "command_substitution_denied",
    NodeKind.PROCESS_SUB: "command_process_substitution_denied",
    NodeKind.EXPANSION: "command_expansion_denied",
    NodeKind.GLOB: "command_glob_denied",
    NodeKind.TILDE: "command_tilde_denied",
}


def assert_single_command(source: str) -> list[str]:
    """Return the words of *source*, or refuse it for being more than one command."""
    tree = parse_shell(source)
    for node in tree.children:
        reason = _FORBIDDEN.get(node.kind)
        if reason:
            raise CommandRejected(reason, node.text.strip()[:80])
    if not tree.words:
        raise CommandRejected("empty_command")
    return tree.words


# ── Binaries, and what each may be asked to do ───────────────────────────────

#: Programs whose entire purpose is to run another program. Refused as the
#: command itself, because allowing one is allowing everything behind it.
INTERPRETERS: frozenset[str] = frozenset({
    "bash", "sh", "zsh", "dash", "ksh", "csh", "tcsh", "fish", "busybox",
    "env", "eval", "exec", "xargs", "nice", "nohup", "setsid", "timeout",
    "watch", "script", "expect", "perl", "ruby", "php", "lua",
    "ssh", "scp", "sftp", "rsync", "telnet", "nc", "ncat", "netcat", "socat",
    "curl", "wget", "sudo", "su", "doas", "chroot", "unshare", "docker",
    "podman", "kubectl", "systemctl", "launchctl", "at", "crontab", "make",
})

#: Flags that turn an otherwise-safe binary into a way to run something else.
#: Matched against the argument's text before any ``=``, so ``-c=x`` is caught
#: alongside ``-c x``.
_DANGEROUS_FLAGS: dict[str, frozenset[str]] = {
    "git": frozenset({
        # `-c` sets arbitrary config for one command, including
        # `core.sshCommand` / `core.pager` / `credential.helper`, each of which
        # executes a program of the caller's choosing.
        "-c", "--exec-path", "--upload-pack", "--receive-pack", "--exec",
        "-u", "--upload-archive",
    }),
    "python": frozenset({"-c", "-m"}),
    "python3": frozenset({"-c", "-m"}),
    "node": frozenset({"-e", "--eval", "-p", "--print", "--require", "-r"}),
    "npm": frozenset({"--ignore-scripts=false"}),
    "find": frozenset({"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprintf"}),
    "grep": frozenset({"-f", "--file"}),
    "sort": frozenset({"--compress-program", "-o"}),
    "tar": frozenset({"--to-command", "--use-compress-program", "-I"}),
    "awk": frozenset({"-f"}),
    "sed": frozenset({"-i", "--in-place", "-f", "--file", "-s"}),
}

#: Programs a governed shell action may name. Everything else is refused by name
#: rather than by behaviour, so the refusal is legible.
DEFAULT_ALLOWED_BINARIES: frozenset[str] = frozenset({
    "ls", "cat", "head", "tail", "echo", "pwd", "which", "stat", "file",
    "git", "python", "python3", "pip", "node", "npm", "npx",
    "diff", "grep", "rg", "find", "sort", "wc", "uniq", "cut", "tr", "sed", "awk",
    "date", "true", "false", "basename", "dirname", "realpath", "md5sum", "sha256sum",
})

#: Names that look like a path and must therefore stay in the workspace.
#: Any separator at all counts, plus a leading dot. An earlier form required a
#: leading `/`, `~` or `./`, which let the plain relative path `.raiker/raiker.db`
#: — the encrypted store and the vault key — through unchecked.
_PATHISH = re.compile(r"[/\\]|^~|^\.")


@dataclass(frozen=True)
class SafeCommand:
    """A command that passed every check, ready to hand to the executor."""

    argv: tuple[str, ...]
    binary: str
    workspace_root: Path

    @property
    def display(self) -> str:
        return " ".join(self.argv)


def validate_command(
    command: Sequence[str],
    *,
    workspace_root: str | Path,
    allowlist: frozenset[str] | None = None,
    allow_interpreters: bool = False,
) -> SafeCommand:
    """Decide one argv list, or raise :class:`CommandRejected` saying why not.

    The order is deliberate — cheapest and most legible refusal first:

    1. non-empty, and the binary is on the allowlist;
    2. the binary is not itself an interpreter;
    3. no argument carries shell syntax, and no argument that *will* be read as
       shell source (a ``-c`` payload) is more than one simple command;
    4. no per-binary flag that would run another program;
    5. every path-looking argument resolves inside the workspace.
    """
    argv = [str(part) for part in command]
    if not argv or not argv[0].strip():
        raise CommandRejected("empty_command")

    root = Path(workspace_root).resolve()
    permitted = allowlist if allowlist is not None else DEFAULT_ALLOWED_BINARIES
    binary = Path(argv[0]).name.lower()
    if binary.endswith(".exe"):
        binary = binary[:-4]

    if binary not in permitted:
        raise CommandRejected("command_not_allowed", binary)
    if binary in INTERPRETERS and not allow_interpreters:
        raise CommandRejected("command_interpreter_denied", binary)

    # An absolute or relative path to the binary must itself be inside the
    # workspace; a bare name is resolved by PATH and is covered by the allowlist.
    if "/" in argv[0] or "\\" in argv[0]:
        _assert_contained(argv[0], root, "command_binary_outside_workspace")

    dangerous = _DANGEROUS_FLAGS.get(binary, frozenset())
    for index, argument in enumerate(argv[1:], start=1):
        flag = argument.split("=", 1)[0]
        if flag in dangerous:
            raise CommandRejected("command_flag_denied", f"{binary} {flag}")

        # `-c` and friends carry shell (or interpreter) source. Parse it, and
        # refuse it for the same reasons any other command line is refused.
        if argv[index - 1] in {"-c", "--command", "-e", "--eval"} or flag in {"-c", "--command"}:
            assert_single_command(argument)

        _assert_no_shell_syntax(argument)
        if _PATHISH.search(argument) and not argument.startswith("-"):
            _assert_contained(argument, root, "command_path_outside_workspace")

    return SafeCommand(tuple(argv), binary, root)


def _assert_no_shell_syntax(argument: str) -> None:
    """Refuse an argument carrying syntax that only means something to a shell.

    Nothing here is exploitable on its own — Raiker runs argv without a shell —
    but an argument shaped like a chained command is a model trying to reach one,
    and that is worth refusing loudly rather than passing through as a literal.
    """
    tree = parse_shell(argument)
    for node in tree.children:
        if node.kind in {
            NodeKind.SUBSTITUTION,
            NodeKind.PROCESS_SUB,
            NodeKind.AND_IF,
            NodeKind.OR_IF,
            NodeKind.PIPELINE,
            NodeKind.SEQUENCE,
            NodeKind.BACKGROUND,
        }:
            raise CommandRejected(
                _FORBIDDEN.get(node.kind, "command_syntax_denied"), argument[:80]
            )


def _assert_contained(value: str, root: Path, reason: str) -> None:
    """Refuse a path that leaves the workspace, or reaches its private internals."""
    if value.startswith("~"):
        raise CommandRejected("command_tilde_denied", value[:80])
    candidate = Path(value)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        raise CommandRejected(reason, value[:80]) from None
    # `.raiker` holds the encrypted store and the vault key; `.git` holds history
    # no file-level checkpoint rewinds. Both are inside the workspace and neither
    # is workspace *content*.
    head = relative.parts[0] if relative.parts else ""
    if head in {".raiker", ".git"}:
        raise CommandRejected("command_path_protected", head)


#: Variables carried through from the host. None of them is a credential, and
#: every one of them turns a working command into a confusing failure if it is
#: dropped: a corporate TLS trust store, a proxy an air-gapped network requires,
#: or the certificate bundle an HTTPS push verifies against. Stripping the
#: environment is about not leaking *secrets*, not about breaking TLS.
_PASSTHROUGH = (
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
    "GIT_SSL_CAINFO", "GIT_SSL_CAPATH",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "no_proxy",
    "SYSTEMROOT", "COMSPEC",  # Windows: sockets and process creation need them
)


def sandbox_environment(
    base: dict[str, str] | None = None, *, workspace_root: str | Path, extra: dict[str, str] | None = None
) -> dict[str, str]:
    """The environment a governed command runs with: minimal, and nothing inherited.

    A child that inherits the host's environment inherits every credential the
    host holds — including the one this runtime is careful to lend for a single
    command. So the child gets a constructed environment instead, and anything
    it needs is passed in explicitly by the caller that decided it should have it.
    """
    root = str(Path(workspace_root).resolve())
    source = base if base is not None else os.environ
    environment = {
        "PATH": source.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": root,
        "PWD": root,
        "TMPDIR": source.get("TMPDIR", "/tmp"),
        "LANG": source.get("LANG", "C.UTF-8"),
        "LC_ALL": source.get("LC_ALL", "C.UTF-8"),
        # Keep git from reading the user's global config, which can carry
        # `credential.helper` and `core.sshCommand` — the same escape the `-c`
        # flag policy above refuses on the command line.
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "",
    }
    environment.update(
        {name: source[name] for name in _PASSTHROUGH if source.get(name)}
    )
    environment.update(extra or {})
    return environment


def portable_command(command: Sequence[str]) -> Sequence[str]:
    """Adapt the narrow governed read surface to native Windows."""
    if os.name != "nt" or not command:
        return command
    if command[0].lower() == "echo":
        writer = "import sys;sys.stdout.write(' '.join(sys.argv[1:])+'\\n')"
        return (sys.executable, "-c", writer, *command[1:])
    if command[0].lower() != "cat":
        return command
    reader = (
        "import pathlib,sys;"
        "out=sys.stdout.buffer;"
        "[out.write(pathlib.Path(name).read_bytes()) for name in sys.argv[1:]]"
    )
    return (sys.executable, "-c", reader, *command[1:])
