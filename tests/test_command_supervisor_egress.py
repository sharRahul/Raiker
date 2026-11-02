"""A supervised background run holds its own download proxy.

The proxy used to live in Raiker, so a background run with downloads on could
not go to the detached supervisor: a restart of Raiker would have taken its
network away mid-run. The supervisor now starts the proxy, writes its fields
into the run's policy before the runner reads it, keeps the credential out of
output, and reports refused hosts when the run ends.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.execution.commands import supervisor
from raiker.execution.commands.egress_runtime import PROXY_VARIABLES


def _specification(policy_path: Path) -> dict[str, Any]:
    return {
        "egress": {
            "run_id": "cmd_supervised",
            "owner_principal_id": "owner_1",
            "domains": ["pypi.org"],
        },
        "policy_path": str(policy_path),
        "policy": {"workspace_root": "/copy", "network": "none"},
    }


def test_the_supervisor_starts_the_proxy_and_writes_it_into_the_policy(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    environment: dict[str, str] = {"PATH": "/usr/bin"}
    egress = supervisor._start_egress(_specification(policy_path), environment, 30)
    try:
        assert egress is not None
        written = json.loads(policy_path.read_text(encoding="utf-8"))
        assert written["workspace_root"] == "/copy"
        assert str(written["network"]).startswith("proxy:127.0.0.1:")
        assert all(name in environment for name in PROXY_VARIABLES)
        assert environment["PATH"] == "/usr/bin"
    finally:
        assert egress is not None
        egress.close()


def test_without_downloads_nothing_is_started_or_written(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    specification = {**_specification(policy_path), "egress": None}
    assert supervisor._start_egress(specification, {}, 30) is None
    assert not policy_path.exists()


class _Egress:
    def close(self) -> list[str]:
        return ["example.com:443"]


def test_refused_hosts_are_journalled_when_the_run_ends(tmp_path: Path) -> None:
    from raiker.execution.commands.supervisor_protocol import SupervisorCodec

    run = supervisor.CommandSupervisor(
        socket_path=tmp_path / "s.sock",
        journal_path=tmp_path / "run.journal",
        codec=SupervisorCodec(b"k" * 32),
        argv=["true"],
        cwd=tmp_path,
        environment={},
        deadline_seconds=5,
        pty=False,
        egress=_Egress(),
    )
    run._close_egress()
    text = " ".join(str(record.get("text", "")) for record in run.journal.read_after(0, 10))
    assert "example.com:443" in text
