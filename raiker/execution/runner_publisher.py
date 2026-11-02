"""Whether the installed native runner carries Raiker's publisher signature.

The package's digest file sits beside the runner, so it detects corruption
but not replacement: whoever can swap the binary can swap the digest. A
platform code signature cannot be swapped that way. When the runner is signed
by the publisher pinned *here*, in Raiker's own code (never in a file shipped
next to the binary), the runner's trust is reported as
``publisher_verified``; otherwise it stays ``package_relative_integrity``.

The pins are empty until the owner has release credentials: a build signed
with them fills in the certificate's subject and the SHA-256 of its public
key, and from then on an unsigned or differently signed runner is reported
for what it is.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from raiker.execution.native_artifacts import NativeTrustPosture

#: Authenticode signer subject and SHA-256 of its public key (SPKI), per
#: release certificate. Empty: no release certificate exists yet.
WINDOWS_PUBLISHER_PINS: tuple[tuple[str, str], ...] = ()

_CACHE: dict[tuple[str, int, int], str] = {}


def runner_trust(
    binary: Path,
    *,
    pins: tuple[tuple[str, str], ...] | None = None,
    verify: Callable[..., object] | None = None,
) -> str:
    """The trust posture to report for the runner at *binary*."""
    pins = WINDOWS_PUBLISHER_PINS if pins is None else pins
    fallback = NativeTrustPosture.PACKAGE_RELATIVE.value
    if not pins or (sys.platform != "win32" and verify is None):
        return fallback
    try:
        stat = binary.stat()
    except OSError:
        return fallback
    key = (str(binary), stat.st_size, stat.st_mtime_ns)
    if key in _CACHE:
        return _CACHE[key]
    if verify is None:
        from raiker.execution.windows_authenticode import verify_windows_authenticode

        verify = verify_windows_authenticode
    answer = fallback
    for publisher, spki in pins:
        try:
            verify(binary, expected_publisher=publisher, expected_leaf_spki_sha256=spki)
        except Exception:  # noqa: BLE001 — any failed check is simply not this publisher
            continue
        answer = NativeTrustPosture.PUBLISHER_VERIFIED.value
        break
    _CACHE[key] = answer
    return answer
