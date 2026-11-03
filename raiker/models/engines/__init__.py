"""Engines Raiker installs and runs itself: model servers and speech engines.

Voice spec §10. The llama.cpp work (PR #245) built the pieces every managed
engine needs — hardware detection, a verified download, safe unpacking, a
contained process with a log and a pid file, orphan reaping. Speech engines
reuse those same functions rather than copies of them; this package is where a
second engine reaches them, plus the one thing that is genuinely shared state:
the :class:`~raiker.models.engines.resources.ResourceLedger`.
"""

from raiker.models.engines.resources import Reservation, ResourceLedger, ledger_for
from raiker.models.llama_cpp.hardware import HardwareProfile, detect, host_arch, host_os
from raiker.models.llama_cpp.installer import extract_archive
from raiker.models.llama_cpp.process import read_log_tail, spawn

__all__ = [
    "HardwareProfile",
    "Reservation",
    "ResourceLedger",
    "detect",
    "extract_archive",
    "host_arch",
    "host_os",
    "ledger_for",
    "read_log_tail",
    "spawn",
]
