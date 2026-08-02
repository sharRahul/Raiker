"""Asking the channel, and taking what it offers.

BUG-44. :mod:`raiker.app.installation` decides what an installation *is* and
:mod:`raiker.app.update` decides what may be installed; this is the small piece
that moves bytes between them. It is separate so that every decision either side
is testable without a network, and so the one function that does egress is one
function.

Two properties matter more than the code. **Raiker asks nobody by default** — a
check needs a channel the owner pinned, and without one no request is made.
And **the fetch is never trusted**: the index is verified against the pinned
public key before its contents are read, the artifact is verified against a
signed manifest before it is extracted, and download size is bounded so a
channel cannot fill an owner's disk by answering a status check.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from raiker.app.installation import (
    ChannelConfig,
    Installation,
    UpdateStatus,
    artifact_url,
    detect_installation,
    read_channel_config,
    recovery_root,
    update_status,
)
from raiker.app.update import UpdateError, UpdateResult, apply_signed_update

#: A generous ceiling for a desktop application bundle. Its job is to stop an
#: unbounded response, not to be a size policy.
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 20.0

#: One URL in, its bytes out. Injectable so the whole channel path is testable
#: without a network and without a fake HTTP server.
Fetcher = Callable[[str, int], bytes]


def https_fetcher(timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Fetcher:
    def fetch(url: str, limit: int) -> bytes:
        import httpx

        with httpx.stream("GET", url, timeout=timeout, follow_redirects=False) as response:
            response.raise_for_status()
            payload = bytearray()
            for chunk in response.iter_bytes():
                payload.extend(chunk)
                if len(payload) > limit:
                    raise UpdateError("channel_response_too_large")
            return bytes(payload)

    return fetch


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def check_for_update(
    workspace_root: str | Path,
    *,
    installation: Installation | None = None,
    fetch: Fetcher | None = None,
) -> UpdateStatus:
    """Ask the configured channel once, and report what it said.

    Every local refusal — a source checkout, an unsigned build, no channel —
    is reached before any request, so the common case makes no request at all.
    """
    install = installation or detect_installation()
    config = read_channel_config(workspace_root)
    local = update_status(workspace_root, installation=install)
    if config is None or local.state in {"source_checkout", "unsigned_build"}:
        return local

    fetcher = fetch or https_fetcher()
    try:
        index = fetcher(config.url, MAX_METADATA_BYTES)
        signature = fetcher(config.url + ".sig", MAX_METADATA_BYTES)
    except Exception:  # noqa: BLE001 - every transport failure is one answer
        # Including UpdateError: an oversized response and a refused connection
        # are the same thing to the owner — the channel could not be read, and
        # nothing about this installation changed.
        return UpdateStatus(
            state="unreachable",
            message=(
                "The update channel could not be reached. Nothing was "
                "downloaded and nothing about this installation changed."
            ),
            installation=install,
            channel=config,
            available=None,
            recovery=local.recovery,
            checked_at=_now(),
        )
    return update_status(
        workspace_root,
        installation=install,
        fetched_index=(index, signature),
        checked_at=_now(),
    )


def download_and_apply(
    workspace_root: str | Path,
    *,
    status: UpdateStatus,
    config: ChannelConfig,
    install_root: str | Path,
    fetch: Fetcher | None = None,
) -> UpdateResult:
    """Fetch the offered release and hand it to the verifying installer.

    Nothing here decides whether the update is acceptable — that was
    :func:`raiker.app.update.select_update` — and nothing here writes into the
    installation: :func:`raiker.app.update.apply_signed_update` re-verifies the
    manifest and digest, copies the current version to its recovery point, and
    does the swap by rename.
    """
    if status.available is None:
        raise UpdateError("no_update_available")
    fetcher = fetch or https_fetcher()
    offered = status.available
    with TemporaryDirectory(prefix="raiker-update-") as staging:
        directory = Path(staging)
        downloads = {
            offered.artifact: MAX_ARTIFACT_BYTES,
            offered.manifest: MAX_METADATA_BYTES,
            offered.signature: MAX_METADATA_BYTES,
        }
        for name, limit in downloads.items():
            (directory / name).write_bytes(fetcher(artifact_url(config, name), limit))
        return apply_signed_update(
            bundle=directory / offered.artifact,
            manifest=directory / offered.manifest,
            signature=directory / offered.signature,
            public_key=config.public_key,
            install_root=install_root,
            recovery_root=recovery_root(workspace_root),
        )
