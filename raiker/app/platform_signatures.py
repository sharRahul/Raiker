"""Check a built installer's platform signature against Raiker's own pins.

IN-3. ``signing.applied`` in a build's record says the release workflow *meant*
to sign it. This is the check that it did, and with the identity the
repository publishes in ``desktop/signing/identities.json`` — not merely with
some certificate or key that happened to be in the environment.

- **Windows.** ``Get-AuthenticodeSignature`` must name the pinned signer
  (certificate thumbprint). A CA-issued certificate must also verify as
  ``Valid``. The beta's certificate is self-signed (2026-11-07, owner's
  decision until a CA certificate exists), so Windows reports its chain as
  untrusted: that one status is accepted, and only when the pin itself says
  ``self_signed``. ``HashMismatch`` and ``NotSigned`` are always refusals, which
  is what makes a self-signed signature still worth having: it detects any
  change to the file after it was signed.
- **Linux.** Each detached ``.asc`` must verify with ``gpg`` against a keyring
  holding only the pinned public key, and the signing fingerprint must be the
  pinned one.
- **Release key.** The Ed25519 key that signs manifests and the channel index
  must derive the pinned public key, so a rotated secret without an updated
  pin fails the release instead of shipping a key installed Raiker does not
  know.

    python -m raiker.app.platform_signatures windows <file>...
    python -m raiker.app.platform_signatures linux <file>...
    python -m raiker.app.platform_signatures release-key
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Where the public halves are published, relative to the repository root.
IDENTITIES = Path(__file__).resolve().parents[2] / "desktop" / "signing" / "identities.json"

#: What ``Get-AuthenticodeSignature`` reports for a signature whose chain ends
#: in a root this machine does not trust: a self-signed certificate.
UNTRUSTED_ROOT_STATUS = "UnknownError"

_AUTHENTICODE = r"""
$s = Get-AuthenticodeSignature -LiteralPath $env:RAIKER_SIGNED_FILE
[pscustomobject]@{
  status = [string]$s.Status
  message = [string]$s.StatusMessage
  thumbprint = [string]$s.SignerCertificate.Thumbprint
  subject = [string]$s.SignerCertificate.Subject
  timestamped = [bool]($null -ne $s.TimeStamperCertificate)
} | ConvertTo-Json -Compress
""".strip()

Runner = Callable[..., subprocess.CompletedProcess[str]]


class SignatureRefused(RuntimeError):
    """A file is unsigned, signed by someone else, or altered since signing."""


@dataclass(frozen=True)
class Verdict:
    path: str
    detail: str

    def line(self) -> str:
        return f"PASS {self.path}: {self.detail}"


def load_identities(path: Path = IDENTITIES) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def judge_authenticode(report: dict[str, Any], pin: dict[str, Any]) -> str:
    """The verdict for one ``Get-AuthenticodeSignature`` report, or a refusal."""
    status = str(report.get("status", ""))
    thumbprint = str(report.get("thumbprint", "")).upper()
    if status in {"NotSigned", ""}:
        raise SignatureRefused("not signed")
    if status == "HashMismatch":
        raise SignatureRefused("changed after it was signed (HashMismatch)")
    if thumbprint != str(pin["thumbprint_sha1"]).upper():
        raise SignatureRefused(f"signed by {report.get('subject') or 'an unknown signer'}, not the pinned publisher")
    if status == "Valid":
        trust = "trusted by Windows"
    elif status == UNTRUSTED_ROOT_STATUS and pin.get("self_signed") is True:
        trust = "self-signed; Windows does not trust the publisher"
    else:
        raise SignatureRefused(f"Authenticode status {status}: {report.get('message', '')}".strip())
    stamped = "timestamped" if report.get("timestamped") else "not timestamped"
    return f"Authenticode by the pinned publisher ({trust}, {stamped})"


def verify_windows(files: Sequence[Path], pin: dict[str, Any], *, runner: Runner = subprocess.run) -> list[Verdict]:
    verdicts: list[Verdict] = []
    for file in files:
        completed = runner(  # noqa: S603 - fixed argv; the file is an argument, not script text
            # The path travels in the environment: `-Command` joins further
            # arguments into the script text, so `$args` would be empty.
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _AUTHENTICODE],
            env={**os.environ, "RAIKER_SIGNED_FILE": str(file.resolve())},
            capture_output=True, text=True, timeout=60, check=False,
        )
        try:
            report = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise SignatureRefused(f"{file.name}: the signature could not be read") from exc
        try:
            verdicts.append(Verdict(file.name, judge_authenticode(report, pin)))
        except SignatureRefused as refusal:
            raise SignatureRefused(f"{file.name}: {refusal}") from None
    return verdicts


def judge_gpg_status(status_lines: str, fingerprint: str) -> str:
    """The verdict from ``gpg --status-fd`` output, or a refusal."""
    for line in status_lines.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[:2] == ["[GNUPG:]", "VALIDSIG"]:
            if parts[2].upper() == fingerprint.upper():
                return f"detached signature by {parts[2]}"
            raise SignatureRefused(f"signed by {parts[2]}, not the pinned key")
    if "[GNUPG:] BADSIG" in status_lines:
        raise SignatureRefused("changed after it was signed (BADSIG)")
    raise SignatureRefused("no valid signature by the pinned key")


def verify_linux(
    files: Sequence[Path], pin: dict[str, Any], key_dir: Path, *, runner: Runner = subprocess.run
) -> list[Verdict]:
    gpg = shutil.which("gpg") or "gpg"
    verdicts: list[Verdict] = []
    with tempfile.TemporaryDirectory(prefix="raiker-gpg-") as home:
        os.chmod(home, 0o700)
        imported = runner(  # noqa: S603 - fixed argv
            [gpg, "--homedir", home, "--batch", "--import", str(key_dir / pin["key_file"])],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if imported.returncode != 0:
            raise SignatureRefused("the pinned Linux key could not be imported")
        for file in files:
            signature = file.with_name(file.name + ".asc")
            if not signature.is_file():
                raise SignatureRefused(f"{file.name}: no detached signature beside it")
            completed = runner(  # noqa: S603 - fixed argv
                [gpg, "--homedir", home, "--batch", "--status-fd", "1", "--verify", str(signature), str(file)],
                capture_output=True, text=True, timeout=120, check=False,
            )
            try:
                verdicts.append(Verdict(file.name, judge_gpg_status(completed.stdout, str(pin["fingerprint"]))))
            except SignatureRefused as refusal:
                raise SignatureRefused(f"{file.name}: {refusal}") from None
    return verdicts


def verify_release_key(pinned_hex: str, environ: dict[str, str] | None = None) -> Verdict:
    from raiker.app.release import public_key_of

    env = os.environ if environ is None else environ
    raw = env.get("RAIKER_RELEASE_SIGNING_KEY", "").strip()
    if not raw:
        raise SignatureRefused("RAIKER_RELEASE_SIGNING_KEY is not configured")
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        raise SignatureRefused("RAIKER_RELEASE_SIGNING_KEY is not hex") from None
    if len(key) != 32:
        raise SignatureRefused("RAIKER_RELEASE_SIGNING_KEY is not a 32-byte Ed25519 seed")
    derived = public_key_of(key).hex()
    if derived != pinned_hex.strip().lower():
        raise SignatureRefused("the release signing key does not match the pinned public key")
    return Verdict("release key", f"derives the pinned public key {derived[:16]}...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("platform", choices=["windows", "linux", "release-key"])
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--identities", type=Path, default=IDENTITIES)
    parser.add_argument("--report", type=Path, default=None, help="Also write the verdicts here.")
    args = parser.parse_args(argv)
    identities = load_identities(args.identities)
    key_dir = args.identities.parent
    try:
        if args.platform == "release-key":
            pinned = (key_dir / identities["release"]["public_key_file"]).read_text(encoding="utf-8")
            verdicts = [verify_release_key(pinned)]
        elif not args.files:
            raise SignatureRefused("no files to check")
        elif args.platform == "windows":
            verdicts = verify_windows(args.files, identities["windows"])
        else:
            verdicts = verify_linux(args.files, identities["linux"], key_dir)
    except SignatureRefused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 1
    lines = [verdict.line() for verdict in verdicts]
    print("\n".join(lines))
    if args.report is not None:
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
