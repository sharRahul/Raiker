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
    # Checkpoint pre-image capture manifest entry (Workstream B / B1).
    "ckcap_",
    "task_",
    # One row of per-turn token accounting in the model usage ledger.
    "usage_",
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
    "apv_",
    "mem_",
    "obs_",
    "pur_",
    "mev_",
    "ent_",
    "rel_",
    "mjob_",
    "mla_",
    "mng_",
    "usr_",
    "rl_",
    "ura_",
    "aex_",
    "plr_",
    "htr_",
    "bud_",
    "ret_",
    "bkm_",
    "chn_",
    "chr_",
    "sba_",
    "team_",
    "rex_",
    "exb_",
    "dsk_",
    "web_",
    "mob_",
    "plgex_",
    "plgrt_",
    "rem_",
    "cal_",
    "eml_",
    "gix_",
    "smw_",
    "ide_",
    "vec_",
    "sym_",
    "dep_",
    "pg_",
    "skc_",
    "ra_",
    "rm_",
    "rtn_",
    "att_",
    "proj_",
    "cwi_",
    "cinv_",
    "mcp_",
    # Monitored MCP connections (Phase B): a redacted per-session monitoring row
    # and a redacted security finding.
    "mses_",
    "find_",
    "cred_",
    # Monitored MCP connections (Phase C): an owner-facing notification.
    "ntf_",
    # Scoped standing approval grants (Workstream F / F3).
    "grn_",
    # Build workspace repository references: a workspace-contained local folder
    # or a GitHub `owner/repo` coordinate. A reference holds no credential and
    # grants no capability.
    "repo_",
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
