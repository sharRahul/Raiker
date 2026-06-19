from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

_PREFIXES = {
    "req_",
    "sess_",
    "turn_",
    "evt_",
    "act_",
    "tool_",
    "pol_",
    "ckpt_",
    "task_",
    "appr_",
    "memcand_",
    "ver_",
    "graphplan_",
    "ctxb_",
    "ctxi_",
    "ctxs_",
    "vres_",
    "vchk_",
    "rap_",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    if prefix not in _PREFIXES:
        raise ValueError(f"unsupported_id_prefix:{prefix}")
    return f"{prefix}{uuid4().hex}"


def require_prefix(value: str, prefix: str) -> None:
    if not value.startswith(prefix):
        raise ValueError(f"expected_prefix:{prefix}")
