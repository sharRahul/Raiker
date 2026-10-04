"""Whether a local model *service* is running on this machine, asked over loopback.

:mod:`raiker.models.local_presence` answers "is the runtime installed" from a PATH
lookup, and that is the wrong question for Ollama. The desktop app on Windows and
macOS runs the service without putting ``ollama`` on the PATH of the process that
started Raiker, and a service started from a container or another account is not
on it either — so a machine whose Ollama was serving two models was reported as
having none, and the only Ollama model any surface could name was the one the
profile shipped with.

The owner decided (2026-10-04) that Raiker should always check: when Ollama is
running here it is available, the owner chooses one of the models it serves,
and Raiker keeps checking that the service and the chosen model are still there.
This module is the check.

* **Loopback only.** The probe refuses any endpoint that is not this machine
  (:func:`service_root`). Reaching a private-network or hosted endpoint is a
  governed egress decision with its own gate; a liveness read must never become
  a way around it.
* **Nothing is adopted.** A running service is *offered*. Which model answers is
  the owner's selection, stored by the selection route; this module reads a
  catalogue and never writes a choice. That is the line FIXED-357 drew for a
  signed-in Codex account, applied here.
* **Bounded and cached.** One GET with a short timeout, never through a proxy,
  and the answer stands for :data:`LIVENESS_TTL_SECONDS` so a page that reads
  the model view repeatedly costs one request per window, not one per read.
  The cache is per process and keyed by endpoint: whether a service answers on
  this machine is not a fact about any one workspace or owner.
"""

from __future__ import annotations

import ipaddress
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

import httpx

from raiker.contracts.ids import utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: How long a liveness answer stands. Short, because the point is to notice a
#: service that was started or stopped; long enough that the Models page, the
#: composer and the readiness line reading it in one render share one request.
LIVENESS_TTL_SECONDS = 10.0

#: A loopback service either answers at once or is not there. A longer wait
#: would only hold a page read on a socket nothing is listening on.
PROBE_TIMEOUT_SECONDS = 1.5

#: The catalogue path each watched runtime publishes, relative to its root.
CATALOGUE_PATHS: dict[str, str] = {"ollama": "/api/tags"}

#: The runtimes this module knows how to ask. Others keep PATH detection only.
WATCHED_RUNTIMES: frozenset[str] = frozenset(CATALOGUE_PATHS)

_LOOPBACK_NAMES = {"localhost"}


@dataclass(frozen=True)
class ServiceLiveness:
    """One answer to "is this service running, and what does it serve"."""

    runtime: str
    endpoint: str
    running: bool
    models: tuple[str, ...]
    checked_at: str


def service_root(endpoint: str) -> str | None:
    """The service root of a loopback endpoint, or ``None`` for anything else.

    Profiles name the OpenAI-compatible path (``…:11434/v1``); the native
    catalogue lives at the root, so the ``/v1`` suffix is dropped. Any host that
    is not this machine — a private address, a hostname, ``0.0.0.0`` used as a
    destination — is refused: this module must never probe off-machine.
    """
    parsed = urlsplit(endpoint.strip())
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").strip("[]").lower()
    if not host:
        return None
    if host not in _LOOPBACK_NAMES and not host.endswith(".localhost"):
        try:
            if not ipaddress.ip_address(host).is_loopback:
                return None
        except ValueError:
            return None
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[: -len("/v1")]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _catalogue(payload: object) -> tuple[str, ...] | None:
    """The model names an ``/api/tags`` answer lists, or ``None`` if it is not one."""
    if not isinstance(payload, dict):
        return None
    entries = payload.get("models")
    if not isinstance(entries, list):
        return None
    names: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("model")
        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())
    return tuple(names)


def probe(runtime: str, endpoint: str, *, timeout: float = PROBE_TIMEOUT_SECONDS) -> ServiceLiveness:
    """Ask ``runtime`` at ``endpoint`` whether it is running. Uncached.

    Any failure — refused, timed out, an answer that is not a catalogue — is
    ``running=False``. A service that answers with something other than its own
    catalogue is not the service the profile names.
    """
    root = service_root(endpoint)
    path = CATALOGUE_PATHS.get(runtime)
    if root is None or path is None:
        return ServiceLiveness(runtime, endpoint, False, (), utc_now())
    try:
        # `trust_env=False`: a loopback request must never be handed to an HTTP
        # proxy, which would either refuse it or — worse — answer for it.
        with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
            response = client.get(f"{root}{path}")
        models = _catalogue(response.json()) if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        models = None
    return ServiceLiveness(
        runtime, endpoint, models is not None, models or (), utc_now()
    )


_cache: dict[tuple[str, str], tuple[float, ServiceLiveness]] = {}
_lock = threading.Lock()


def liveness(
    runtime: str, endpoint: str, *, force: bool = False, now: float | None = None
) -> ServiceLiveness | None:
    """The cached liveness of ``runtime`` at ``endpoint``, probing when stale.

    ``None`` when this module cannot ask: an unwatched runtime, or an endpoint
    that is not on this machine. Callers treat ``None`` as "not known" and fall
    back to whatever else they know — never as "not running".
    """
    if runtime not in WATCHED_RUNTIMES or service_root(endpoint) is None:
        return None
    key = (runtime, endpoint)
    clock = time.monotonic() if now is None else now
    with _lock:
        held = _cache.get(key)
    if not force and held is not None and clock - held[0] < LIVENESS_TTL_SECONDS:
        return held[1]
    answer = probe(runtime, endpoint)
    with _lock:
        _cache[key] = (clock, answer)
    return answer


def forget() -> None:
    """Drop every cached answer. For tests, and for an owner pressing Detect."""
    with _lock:
        _cache.clear()


def owner_services(
    store: SQLiteStore, owner_principal_id: str | None, *, force: bool = False
) -> dict[str, ServiceLiveness]:
    """Liveness of every watched runtime, at the endpoint this owner reaches it on.

    One answer per runtime: the first published profile for it decides the
    endpoint, with the owner's saved connection taking precedence exactly as a
    turn would. A runtime whose endpoint is off-machine is left out rather than
    reported as stopped.
    """
    from raiker.models.connections import get_model_connection
    from raiker.models.readiness import effective_endpoint
    from raiker.models.registry import ModelProfileRegistry

    answers: dict[str, ServiceLiveness] = {}
    for profile in ModelProfileRegistry.load().list_profiles():
        if profile.provider not in WATCHED_RUNTIMES or profile.provider in answers:
            continue
        if bool(profile.raw.get("test_only", False)):
            continue
        connection = (
            get_model_connection(store, owner_principal_id, profile.profile_id)
            if owner_principal_id
            else None
        )
        answer = liveness(profile.provider, effective_endpoint(profile, connection), force=force)
        if answer is not None:
            answers[profile.provider] = answer
    return answers
