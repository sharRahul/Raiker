"""IN-3 — a signed build is checked against the identities the repository pins."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from raiker.app import platform_signatures as ps
from raiker.app.release import public_key_of
from raiker.execution import windows_authenticode

PIN = {"thumbprint_sha1": "ABC123", "self_signed": True}


def _report(status: str, thumbprint: str = "abc123", **extra: Any) -> dict[str, Any]:
    return {"status": status, "thumbprint": thumbprint, "subject": "CN=Someone", "timestamped": True, **extra}


def test_self_signed_pin_accepts_only_the_untrusted_root_status() -> None:
    assert "self-signed" in ps.judge_authenticode(_report("UnknownError"), PIN)
    assert "trusted by Windows" in ps.judge_authenticode(_report("Valid"), PIN)
    with pytest.raises(ps.SignatureRefused, match="UnknownError"):
        ps.judge_authenticode(_report("UnknownError"), {**PIN, "self_signed": False})


@pytest.mark.parametrize(
    ("report", "reason"),
    [
        (_report("NotSigned", ""), "not signed"),
        (_report("HashMismatch"), "changed after it was signed"),
        (_report("Valid", "FFFF"), "not the pinned publisher"),
        (_report("NotTrusted"), "NotTrusted"),
    ],
)
def test_authenticode_refusals(report: dict[str, Any], reason: str) -> None:
    with pytest.raises(ps.SignatureRefused, match=reason):
        ps.judge_authenticode(report, PIN)


def test_gpg_status_must_name_the_pinned_fingerprint() -> None:
    good = "[GNUPG:] GOODSIG 25F9 Raiker\n[GNUPG:] VALIDSIG 6B31334382D46C56AFE125CA25F9767FF2DDACF1 2026-11-07"
    assert "6B3133" in ps.judge_gpg_status(good, "6b31334382d46c56afe125ca25f9767ff2ddacf1")
    with pytest.raises(ps.SignatureRefused, match="not the pinned key"):
        ps.judge_gpg_status(good, "0000")
    with pytest.raises(ps.SignatureRefused, match="BADSIG"):
        ps.judge_gpg_status("[GNUPG:] BADSIG 25F9 Raiker", "0000")
    with pytest.raises(ps.SignatureRefused, match="no valid signature"):
        ps.judge_gpg_status("", "0000")


def test_release_key_must_derive_the_pinned_public_key() -> None:
    seed = bytes(range(32))
    pinned = public_key_of(seed).hex()
    assert ps.verify_release_key(pinned, {"RAIKER_RELEASE_SIGNING_KEY": seed.hex()}).path == "release key"
    with pytest.raises(ps.SignatureRefused, match="does not match"):
        ps.verify_release_key(pinned, {"RAIKER_RELEASE_SIGNING_KEY": bytes(32).hex()})
    with pytest.raises(ps.SignatureRefused, match="not configured"):
        ps.verify_release_key(pinned, {})


def test_published_identities_are_consistent() -> None:
    identities = ps.load_identities()
    folder = ps.IDENTITIES.parent
    assert len(identities["windows"]["thumbprint_sha1"]) == 40
    assert (folder / identities["linux"]["key_file"]).read_text().startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----")
    assert len(bytes.fromhex((folder / identities["release"]["public_key_file"]).read_text().strip())) == 32
    # Only public halves are ever committed.
    for file in folder.iterdir():
        assert "PRIVATE" not in file.read_text(encoding="utf-8").upper().replace("PRIVATE HALVES", "")


def _capturing_runner(seen: dict[str, Any], stdout: str) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen["argv"] = argv
        seen["env"] = kwargs.get("env") or {}
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    return run


def test_both_authenticode_readers_pass_the_path_in_the_environment(tmp_path: Path) -> None:
    # `powershell -Command <script> <path>` folds <path> into the script text,
    # so `$args[0]` is null. Found 2026-11-07 when the first real signature was read.
    artifact = tmp_path / "app.exe"
    artifact.write_bytes(b"x")
    seen: dict[str, Any] = {}
    ps.verify_windows([artifact], PIN, runner=_capturing_runner(seen, json.dumps(_report("UnknownError"))))
    assert seen["argv"][-1] == ps._AUTHENTICODE
    assert seen["env"]["RAIKER_SIGNED_FILE"] == str(artifact.resolve())

    seen.clear()
    with pytest.raises(windows_authenticode.AuthenticodeError):
        windows_authenticode.verify_windows_authenticode(
            artifact, expected_publisher="CN=x", expected_leaf_spki_sha256="0",
            runner=_capturing_runner(seen, json.dumps({"status": "UnknownError"})),
        )
    assert seen["argv"][-1] == windows_authenticode._SCRIPT
    assert seen["env"]["RAIKER_SIGNED_FILE"] == str(artifact.resolve())


def test_the_child_powershell_does_not_inherit_a_module_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """From a pwsh step, PowerShell 7's PSModulePath broke 5.1's signature cmdlet."""
    artifact = tmp_path / "app.exe"
    artifact.write_bytes(b"x")
    monkeypatch.setenv("PSModulePath", r"C:\Program Files\PowerShell\Modules")
    env = ps.powershell_environment(artifact)
    assert not any(key.upper() == "PSMODULEPATH" for key in env)
    seen: dict[str, Any] = {}
    with pytest.raises(ps.SignatureRefused, match="could not be read"):
        ps.verify_windows([artifact], PIN, runner=_capturing_runner(seen, json.dumps({"status": ""})))
